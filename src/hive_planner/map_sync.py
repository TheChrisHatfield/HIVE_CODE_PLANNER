from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.config import RepoPaths

TABLE_ROW_RE = re.compile(r"^\| `([^`]+)` \| (.+) \|$")
PROJECT_ROW_RE = re.compile(r"^\| `([^`]+)` \| (.+) \| (.+) \|$")


@dataclass
class MapSyncReport:
    project_added: list[str] = field(default_factory=list)
    project_updated: list[str] = field(default_factory=list)
    test_added: list[str] = field(default_factory=list)
    test_updated: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "project_added": self.project_added,
            "project_updated": self.project_updated,
            "test_added": self.test_added,
            "test_updated": self.test_updated,
            "warnings": self.warnings,
        }


def discover_src_modules(paths: RepoPaths) -> list[str]:
    src_root = paths.root / "src" / "hive_planner"
    if not src_root.exists():
        return []
    modules: list[str] = []
    for py_file in sorted(src_root.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        modules.append(py_file.relative_to(paths.root).as_posix())
    return modules


def import_module_to_src_path(import_module: str) -> str | None:
    if not import_module or not import_module.startswith("hive_planner"):
        return None
    parts = import_module.split(".")
    candidate = Path("src", *parts).with_suffix(".py")
    return candidate.as_posix()


def _imports_in_test_file(test_path: Path) -> set[str]:
    try:
        tree = ast.parse(test_path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "hive_planner":
                for alias in node.names:
                    src_path = import_module_to_src_path(f"hive_planner.{alias.name}")
                    if src_path:
                        modules.add(src_path)
            else:
                src_path = import_module_to_src_path(node.module)
                if src_path:
                    modules.add(src_path)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                src_path = import_module_to_src_path(alias.name)
                if src_path:
                    modules.add(src_path)
    return modules


def discover_test_mappings(paths: RepoPaths) -> dict[str, set[str]]:
    tests_root = paths.root / "tests"
    mapping: dict[str, set[str]] = {}
    if not tests_root.exists():
        return mapping
    for test_file in sorted(tests_root.glob("test_*.py")):
        rel_test = test_file.relative_to(paths.root).as_posix()
        for src_module in _imports_in_test_file(test_file):
            mapping.setdefault(src_module, set()).add(rel_test)
    return mapping


def _module_role(module_path: Path) -> str:
    try:
        text = module_path.read_text(encoding="utf-8")
    except OSError:
        return module_path.stem.replace("_", " ")
    if text.startswith('"""') or text.startswith("'''"):
        quote = text[0:3]
        end = text.find(quote, 3)
        if end != -1:
            first = text[3:end].strip().splitlines()[0].strip()
            if first:
                return first[:80]
    return module_path.stem.replace("_", " ")


def _parse_project_map(content: str) -> tuple[list[str], dict[str, tuple[str, str]]]:
    header: list[str] = []
    rows: dict[str, tuple[str, str]] = {}
    in_table = False
    for line in content.splitlines():
        if line.startswith("| Module |"):
            in_table = True
            continue
        if line.startswith("|--------"):
            continue
        if in_table:
            match = PROJECT_ROW_RE.match(line)
            if match:
                module, role, deps = match.group(1), match.group(2), match.group(3)
                rows[module] = (role, deps)
                continue
            in_table = False
        if not rows and not in_table:
            header.append(line)
    return header, rows


def _parse_test_map(content: str) -> tuple[list[str], dict[str, set[str]]]:
    header: list[str] = []
    rows: dict[str, set[str]] = {}
    in_table = False
    for line in content.splitlines():
        if line.startswith("| Source module |"):
            in_table = True
            continue
        if line.startswith("|---------------"):
            continue
        if in_table:
            match = TABLE_ROW_RE.match(line)
            if match:
                module = match.group(1)
                tests = [t.strip().strip("`") for t in match.group(2).split(",")]
                rows[module] = {t for t in tests if t}
                continue
            in_table = False
        if not rows and not in_table:
            header.append(line)
    return header, rows


def _render_project_map(
    header_lines: list[str],
    rows: dict[str, tuple[str, str]],
) -> str:
    body = list(header_lines)
    if body and body[-1].strip():
        body.append("")
    body.extend(
        [
            "| Module | Role | Spec / Delta deps |",
            "|--------|------|-------------------|",
        ]
    )
    for module in sorted(rows):
        role, deps = rows[module]
        body.append(f"| `{module}` | {role} | {deps} |")
    return "\n".join(body).rstrip() + "\n"


def _render_test_map(header_lines: list[str], rows: dict[str, set[str]]) -> str:
    body = list(header_lines)
    if body and body[-1].strip():
        body.append("")
    body.extend(
        [
            "| Source module | Tests |",
            "|---------------|-------|",
        ]
    )
    for module in sorted(rows):
        tests = ", ".join(f"`{t}`" for t in sorted(rows[module]))
        body.append(f"| `{module}` | {tests} |")
    return "\n".join(body).rstrip() + "\n"


def sync_impact_maps(paths: RepoPaths, *, dry_run: bool = False) -> MapSyncReport:
    report = MapSyncReport(dry_run=dry_run)
    change_dir = paths.root / "docs" / "change-impact"
    project_path = change_dir / "project-map.md"
    test_path = change_dir / "test-map.md"

    src_modules = discover_src_modules(paths)
    test_mappings = discover_test_mappings(paths)

    project_header, project_rows = _parse_project_map(
        project_path.read_text(encoding="utf-8") if project_path.exists() else "# Project Map\n"
    )
    manual_project = {k: v for k, v in project_rows.items() if not k.startswith("src/")}
    merged_project: dict[str, tuple[str, str]] = dict(manual_project)

    for module in src_modules:
        existing = project_rows.get(module)
        if existing:
            merged_project[module] = existing
            continue
        module_path = paths.root / module
        role = _module_role(module_path)
        merged_project[module] = (role, "(auto-sync)")
        report.project_added.append(module)

    test_header, test_rows = _parse_test_map(
        test_path.read_text(encoding="utf-8") if test_path.exists() else "# Test Map\n"
    )
    merged_tests: dict[str, set[str]] = {}
    for module in src_modules:
        prior = test_rows.get(module, set())
        discovered = test_mappings.get(module, set())
        combined = prior | discovered
        if not prior and discovered:
            report.test_added.append(module)
        elif discovered - prior:
            report.test_updated.append(module)
        if combined:
            merged_tests[module] = combined

    unmapped = [m for m in src_modules if m not in merged_tests]
    if unmapped:
        suffix = " ..." if len(unmapped) > 5 else ""
        report.warnings.append(
            f"{len(unmapped)} src module(s) have no mapped tests: "
            f"{', '.join(unmapped[:5])}{suffix}"
        )

    if not dry_run:
        change_dir.mkdir(parents=True, exist_ok=True)
        project_path.write_text(_render_project_map(project_header, merged_project), encoding="utf-8")
        test_path.write_text(_render_test_map(test_header, merged_tests), encoding="utf-8")

    return report
