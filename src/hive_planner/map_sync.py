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
    src_root = paths.root / "src"
    if not src_root.exists():
        return []
    modules: list[str] = []
    for pkg_dir in sorted(p for p in src_root.iterdir() if p.is_dir()):
        for py_file in sorted(pkg_dir.rglob("*.py")):
            if py_file.name == "__init__.py":
                continue
            modules.append(py_file.relative_to(paths.root).as_posix())
    return modules


def import_module_to_src_path(import_module: str, repo_root: Path | None = None) -> str | None:
    if not import_module or not import_module.startswith("hive_planner"):
        return None
    parts = import_module.split(".")
    direct = Path("src", *parts).with_suffix(".py")
    package_init = Path("src", *parts) / "__init__.py"
    if repo_root is None:
        return direct.as_posix()
    if (repo_root / direct).is_file():
        return direct.as_posix()
    if (repo_root / package_init).is_file():
        return package_init.as_posix()
    return None


def _imports_in_test_file(test_path: Path, repo_root: Path) -> set[str]:
    try:
        tree = ast.parse(test_path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if not node.module:
                continue
            if node.module == "hive_planner":
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    src_path = import_module_to_src_path(
                        f"hive_planner.{alias.name}",
                        repo_root=repo_root,
                    )
                    if src_path:
                        modules.add(src_path)
            else:
                if not node.module.startswith("hive_planner"):
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    sub_path = import_module_to_src_path(
                        f"{node.module}.{alias.name}",
                        repo_root=repo_root,
                    )
                    if sub_path:
                        modules.add(sub_path)
                        continue
                    src_path = import_module_to_src_path(node.module, repo_root=repo_root)
                    if src_path:
                        modules.add(src_path)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if not alias.name.startswith("hive_planner"):
                    continue
                src_path = import_module_to_src_path(alias.name, repo_root=repo_root)
                if src_path:
                    modules.add(src_path)
    return modules


def discover_test_mappings(paths: RepoPaths) -> dict[str, set[str]]:
    tests_root = paths.root / "tests"
    mapping: dict[str, set[str]] = {}
    if not tests_root.exists():
        return mapping
    for test_file in sorted(tests_root.rglob("test_*.py")):
        rel_test = test_file.relative_to(paths.root).as_posix()
        for src_module in _imports_in_test_file(test_file, paths.root):
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
            lines = text[3:end].strip().splitlines()
            first = lines[0].strip() if lines else ""
            if first:
                return first[:80]
    return module_path.stem.replace("_", " ")


def _escape_table_cell(text: str) -> str:
    return text.replace("|", "\\|")


def _parse_project_map(content: str) -> tuple[list[str], dict[str, tuple[str, str]], list[str]]:
    header: list[str] = []
    footer: list[str] = []
    rows: dict[str, tuple[str, str]] = {}
    in_table = False
    table_seen = False
    for line in content.splitlines():
        if line.startswith("| Module |"):
            in_table = True
            table_seen = True
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
        if table_seen and not in_table:
            footer.append(line)
        elif not table_seen:
            header.append(line)
    return header, rows, footer


def _parse_test_map(content: str) -> tuple[list[str], dict[str, set[str]], list[str]]:
    header: list[str] = []
    footer: list[str] = []
    rows: dict[str, set[str]] = {}
    in_table = False
    table_seen = False
    for line in content.splitlines():
        if line.startswith("| Source module |"):
            in_table = True
            table_seen = True
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
        if table_seen and not in_table:
            footer.append(line)
        elif not table_seen:
            header.append(line)
    return header, rows, footer


def _render_project_map(
    header_lines: list[str],
    rows: dict[str, tuple[str, str]],
    footer_lines: list[str] | None = None,
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
        body.append(
            f"| `{module}` | {_escape_table_cell(role)} | {_escape_table_cell(deps)} |"
        )
    if footer_lines:
        if body and body[-1].strip():
            body.append("")
        body.extend(footer_lines)
    return "\n".join(body).rstrip() + "\n"


def _render_test_map(
    header_lines: list[str],
    rows: dict[str, set[str]],
    footer_lines: list[str] | None = None,
) -> str:
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
        body.append(f"| `{module}` | {_escape_table_cell(tests)} |")
    if footer_lines:
        if body and body[-1].strip():
            body.append("")
        body.extend(footer_lines)
    return "\n".join(body).rstrip() + "\n"


def sync_impact_maps(paths: RepoPaths, *, dry_run: bool = False) -> MapSyncReport:
    report = MapSyncReport(dry_run=dry_run)
    change_dir = paths.root / "docs" / "change-impact"
    project_path = change_dir / "project-map.md"
    test_path = change_dir / "test-map.md"

    src_modules = discover_src_modules(paths)
    test_mappings = discover_test_mappings(paths)

    project_header, project_rows, project_footer = _parse_project_map(
        project_path.read_text(encoding="utf-8") if project_path.exists() else "# Project Map\n"
    )
    discovered_src = set(src_modules)
    # Non-src manuals + existing src/** rows not rediscovered (other packages / orphans).
    merged_project: dict[str, tuple[str, str]] = {
        k: v
        for k, v in project_rows.items()
        if not k.startswith("src/") or k not in discovered_src
    }

    for module in src_modules:
        existing = project_rows.get(module)
        if existing:
            merged_project[module] = existing
            continue
        module_path = paths.root / module
        role = _module_role(module_path)
        merged_project[module] = (role, "(auto-sync)")
        report.project_added.append(module)

    test_header, test_rows, test_footer = _parse_test_map(
        test_path.read_text(encoding="utf-8") if test_path.exists() else "# Test Map\n"
    )
    merged_tests: dict[str, set[str]] = {
        k: set(v)
        for k, v in test_rows.items()
        if k.startswith("src/") and k not in discovered_src
    }
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
        project_path.write_text(
            _render_project_map(project_header, merged_project, project_footer),
            encoding="utf-8",
        )
        test_path.write_text(
            _render_test_map(test_header, merged_tests, test_footer),
            encoding="utf-8",
        )

    return report
