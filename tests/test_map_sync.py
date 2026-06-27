from __future__ import annotations

import textwrap
from pathlib import Path

from hive_planner.config import RepoPaths
from hive_planner.map_sync import (
    discover_src_modules,
    discover_test_mappings,
    import_module_to_src_path,
    sync_impact_maps,
)


def _write_src_module(paths: RepoPaths, rel: str, body: str) -> None:
    target = paths.root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def _write_test(paths: RepoPaths, name: str, body: str) -> None:
    target = paths.root / "tests" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(body), encoding="utf-8")


def _write_project_map(paths: RepoPaths, content: str) -> None:
    ci = paths.root / "docs" / "change-impact"
    ci.mkdir(parents=True, exist_ok=True)
    (ci / "project-map.md").write_text(content, encoding="utf-8")


def _write_test_map(paths: RepoPaths, content: str) -> None:
    ci = paths.root / "docs" / "change-impact"
    ci.mkdir(parents=True, exist_ok=True)
    (ci / "test-map.md").write_text(content, encoding="utf-8")


def test_import_module_to_src_path() -> None:
    assert import_module_to_src_path("hive_planner.emitter") == "src/hive_planner/emitter.py"
    assert import_module_to_src_path("hive_planner.normalizers.pdf") == "src/hive_planner/normalizers/pdf.py"
    assert import_module_to_src_path("other.mod") is None


def test_discover_src_modules(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _write_src_module(paths, "src/hive_planner/foo.py", '"""Foo module."""\n')
    _write_src_module(paths, "src/hive_planner/bar/__init__.py", "")
    _write_src_module(paths, "src/hive_planner/bar/baz.py", "x = 1\n")
    modules = discover_src_modules(paths)
    assert "src/hive_planner/foo.py" in modules
    assert "src/hive_planner/bar/baz.py" in modules
    assert "src/hive_planner/bar/__init__.py" not in modules


def test_discover_test_mappings(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _write_test(
        paths,
        "test_sample.py",
        """
        from hive_planner.emitter import select_chunks
        from hive_planner import config
        """,
    )
    mapping = discover_test_mappings(paths)
    assert "tests/test_sample.py" in mapping["src/hive_planner/emitter.py"]
    assert "tests/test_sample.py" in mapping["src/hive_planner/config.py"]


def test_sync_dry_run_does_not_write(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _write_src_module(paths, "src/hive_planner/newmod.py", "pass\n")
    _write_project_map(
        paths,
        "# Project Map\n\n| Module | Role | Spec / Delta deps |\n|--------|------|-------------------|\n",
    )
    _write_test_map(
        paths,
        "# Test Map\n\n| Source module | Tests |\n|---------------|-------|\n",
    )
    report = sync_impact_maps(paths, dry_run=True)
    assert "src/hive_planner/newmod.py" in report.project_added
    assert not (paths.root / "docs" / "change-impact" / "project-map.md").read_text().count("newmod")


def test_sync_preserves_manual_project_rows(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _write_src_module(paths, "src/hive_planner/emitter.py", '"""Auto role."""\n')
    _write_project_map(
        paths,
        "# Project Map\n\n"
        "| Module | Role | Spec / Delta deps |\n"
        "|--------|------|-------------------|\n"
        "| `docs/delta/*.md` | Primary planning truth | `context.delta` |\n"
        "| `src/hive_planner/emitter.py` | Curated emitter role | `context.cartridge` |\n",
    )
    _write_test_map(
        paths,
        "# Test Map\n\n| Source module | Tests |\n|---------------|-------|\n"
        "| `src/hive_planner/emitter.py` | `tests/test_manual.py` |\n",
    )
    sync_impact_maps(paths)
    content = (paths.root / "docs" / "change-impact" / "project-map.md").read_text(encoding="utf-8")
    assert "Primary planning truth" in content
    assert "Curated emitter role" in content
    assert "Auto role" not in content


def test_sync_merges_test_imports(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _write_src_module(paths, "src/hive_planner/emitter.py", "pass\n")
    _write_test(paths, "test_auto.py", "from hive_planner.emitter import select_chunks\n")
    _write_test_map(
        paths,
        "# Test Map\n\n| Source module | Tests |\n|---------------|-------|\n"
        "| `src/hive_planner/emitter.py` | `tests/test_manual.py` |\n",
    )
    _write_project_map(
        paths,
        "# Project Map\n\n| Module | Role | Spec / Delta deps |\n|--------|------|-------------------|\n",
    )
    sync_impact_maps(paths)
    test_map = (paths.root / "docs" / "change-impact" / "test-map.md").read_text(encoding="utf-8")
    assert "`tests/test_manual.py`" in test_map
    assert "`tests/test_auto.py`" in test_map


def test_sync_adds_missing_src_module(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _write_src_module(paths, "src/hive_planner/discovery.py", '"""Discovery helpers."""\n')
    _write_project_map(
        paths,
        "# Project Map\n\n| Module | Role | Spec / Delta deps |\n|--------|------|-------------------|\n",
    )
    _write_test_map(
        paths,
        "# Test Map\n\n| Source module | Tests |\n|---------------|-------|\n",
    )
    report = sync_impact_maps(paths)
    assert "src/hive_planner/discovery.py" in report.project_added
    project_map = (paths.root / "docs" / "change-impact" / "project-map.md").read_text(encoding="utf-8")
    assert "Discovery helpers" in project_map


def test_sync_preserves_footer_after_table(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _write_src_module(paths, "src/hive_planner/foo.py", "pass\n")
    _write_project_map(
        paths,
        "# Project Map\n\n"
        "| Module | Role | Spec / Delta deps |\n"
        "|--------|------|-------------------|\n\n"
        "## How to edit\n\n"
        "Keep manual rows above auto-sync.\n",
    )
    _write_test_map(
        paths,
        "# Test Map\n\n| Source module | Tests |\n|---------------|-------|\n",
    )
    sync_impact_maps(paths)
    content = (paths.root / "docs" / "change-impact" / "project-map.md").read_text(encoding="utf-8")
    assert "Keep manual rows above auto-sync" in content
    assert "src/hive_planner/foo.py" in content


def test_sync_escapes_pipe_in_table_cells(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _write_src_module(paths, "src/hive_planner/piped.py", '"""Role | with pipe."""\n')
    _write_project_map(
        paths,
        "# Project Map\n\n| Module | Role | Spec / Delta deps |\n|--------|------|-------------------|\n",
    )
    _write_test_map(
        paths,
        "# Test Map\n\n| Source module | Tests |\n|---------------|-------|\n",
    )
    sync_impact_maps(paths)
    content = (paths.root / "docs" / "change-impact" / "project-map.md").read_text(encoding="utf-8")
    assert "Role \\| with pipe" in content


def test_discover_test_mappings_in_subdirs(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    nested = paths.root / "tests" / "integration"
    nested.mkdir(parents=True)
    (nested / "test_nested.py").write_text(
        "from hive_planner.config import RepoPaths\n",
        encoding="utf-8",
    )
    mapping = discover_test_mappings(paths)
    assert "tests/integration/test_nested.py" in mapping["src/hive_planner/config.py"]
