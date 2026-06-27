from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.agents_memory import AgentsMemoryError, lint_agents_md
from hive_planner.bootstrap import BootstrapError, init_project
from hive_planner.call_graph import build_package_graph, secondary_call_targets
from hive_planner.ci_handoff import run_ci_check
from hive_planner.config import RepoPaths, resolve_repo_file_path, validate_feature_id
from hive_planner.impact import ImpactError, build_impact_packet
from hive_planner.map_sync import sync_impact_maps
from hive_planner.spec_drift import check_memory_spec_drift, check_spec_handoff


def test_validate_feature_id_rejects_path_traversal() -> None:
    with pytest.raises(ValueError, match="Invalid feature id"):
        validate_feature_id("..")
    with pytest.raises(ValueError, match="Invalid feature id"):
        validate_feature_id("../evil")


def test_build_impact_packet_rejects_invalid_feature(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    target = tmp_path / "x.py"
    target.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(ImpactError, match="Invalid feature id"):
        build_impact_packet(paths, "..", [target])


def test_build_impact_packet_resolves_files_relative_to_repo_root(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    spec_dir = paths.root / "docs" / "specs" / "change-impact-v1"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    src = paths.root / "src" / "hive_planner" / "sample.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("x = 1\n", encoding="utf-8")

    subdir = paths.root / "nested"
    subdir.mkdir()
    packet = build_impact_packet(
        paths,
        "change-impact-v1",
        [resolve_repo_file_path(paths, Path("src/hive_planner/sample.py"))],
    )
    assert packet.primary[0].path == "src/hive_planner/sample.py"


def test_resolve_repo_file_path_rejects_outside_repo(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    outside = tmp_path.parent / "outside.py"
    outside.write_text("x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inside repo root"):
        resolve_repo_file_path(paths, outside)


def test_spec_drift_missing_candidates_outside_repo_does_not_crash(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    outside = tmp_path.parent / "missing-candidates.md"
    report = check_memory_spec_drift(paths, candidates_path=outside)
    assert any("Candidates file not found" in action for action in report.spec_actions)


def test_check_spec_handoff_rejects_invalid_feature_id(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    report = check_spec_handoff(paths, feature="..")
    assert not report.ok
    assert any("invalid feature id" in item for item in report.missing)


def test_lint_agents_rejects_path_outside_repo(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    outside = tmp_path.parent / "AGENTS.md"
    outside.write_text("# AGENTS\n\n## Repository root\n\nx\n", encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="inside repo root"):
        lint_agents_md(paths, agents_path=outside)


def test_call_graph_indexes_async_functions(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    pkg = paths.root / "src" / "hive_planner"
    pkg.mkdir(parents=True, exist_ok=True)
    target = pkg / "async_target.py"
    caller = pkg / "async_caller.py"
    target.write_text("async def fetch_data() -> None:\n    pass\n", encoding="utf-8")
    caller.write_text(
        "from hive_planner.async_target import fetch_data\n\n"
        "async def main() -> None:\n    await fetch_data()\n",
        encoding="utf-8",
    )

    graph = build_package_graph(paths)
    def_key = "src/hive_planner/async_target.py::fetch_data"
    assert graph.callers.get(def_key) == {"src/hive_planner/async_caller.py"}
    callers = secondary_call_targets(graph, "src/hive_planner/async_target.py")
    assert any(path.endswith("async_caller.py") for path, _ in callers)


def test_init_rejects_multiline_project_name(tmp_path: Path) -> None:
    source_root = tmp_path / "hive-planner"
    kit = source_root / "starter-kit"
    rules = source_root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# Architecture\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# Task Execution\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# Validation\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")
    source = RepoPaths(root=source_root)
    target = tmp_path / "new-app"

    with pytest.raises(BootstrapError, match="line breaks"):
        init_project(source, target, name="Broken\nName", profile="full")


def _write_handoff_artifacts(paths: RepoPaths, feature: str) -> None:
    spec_dir = paths.root / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (spec_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (spec_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    micro_dir = paths.root / "docs" / "delta" / "20_micro"
    micro_dir.mkdir(parents=True, exist_ok=True)
    (micro_dir / f"{feature}.md").write_text("# Micro\n", encoding="utf-8")


def test_ci_check_detects_test_map_updates_as_drift(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    src = paths.root / "src" / "hive_planner"
    src.mkdir(parents=True, exist_ok=True)
    (src / "mapped.py").write_text('"""Mapped module."""\n', encoding="utf-8")
    tests = paths.root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_mapped.py").write_text(
        "from hive_planner import mapped\n\ndef test_mapped():\n    assert mapped\n",
        encoding="utf-8",
    )
    ci = paths.root / "docs" / "change-impact"
    ci.mkdir(parents=True, exist_ok=True)
    (ci / "project-map.md").write_text(
        "# Project Map\n\n| Module | Role | Spec / Delta deps |\n|--------|------|-------------------|\n",
        encoding="utf-8",
    )
    (ci / "test-map.md").write_text(
        "# Test Map\n\n| Source module | Tests |\n|---------------|-------|\n"
        "| `src/hive_planner/mapped.py` | `tests/test_old.py` |\n",
        encoding="utf-8",
    )
    (paths.root / "AGENTS.md").write_text(
        "# AGENTS\n\n## Repository root\n\nx\n\n## Planning Rosetta Stone\n\nx\n\n"
        "## Startup read order\n\nx\n\n## Delta model\n\nx\n\n## Active feature\n\n"
        "**git-handoff-ci-v1** — test\n\n## Durable Workspace Facts\n\n- fact\n",
        encoding="utf-8",
    )
    _write_handoff_artifacts(paths, "git-handoff-ci-v1")

    dry = sync_impact_maps(paths, dry_run=True)
    assert "src/hive_planner/mapped.py" in dry.test_updated

    report = run_ci_check(paths, skip_pytest=True, check_map_drift=True, check_roadmap=False)
    drift = next(s for s in report.steps if s.name == "impact-map-drift")
    assert not drift.ok
