from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hive_planner.ci_handoff import run_ci_check
from hive_planner.config import RepoPaths
from hive_planner.map_sync import sync_impact_maps
from hive_planner.spec_drift import parse_active_feature


def _write_agents(paths: RepoPaths, body: str) -> None:
    (paths.root / "AGENTS.md").write_text(body, encoding="utf-8")


def _write_handoff_artifacts(paths: RepoPaths, feature: str) -> None:
    from hive_planner.rosetta_nav import (
        delta_micro_navigation_block,
        inject_after_header,
        plan_navigation_block,
        spec_navigation_block,
        tasks_navigation_block,
    )

    spec_dir = paths.root / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec.md").write_text(
        inject_after_header("# Spec\n\n", spec_navigation_block(feature)),
        encoding="utf-8",
    )
    (spec_dir / "plan.md").write_text(
        inject_after_header("# Plan\n\n", plan_navigation_block(feature)),
        encoding="utf-8",
    )
    (spec_dir / "tasks.md").write_text(
        inject_after_header("# Tasks\n\n", tasks_navigation_block(feature)),
        encoding="utf-8",
    )
    micro_dir = paths.root / "docs" / "delta" / "20_micro"
    micro_dir.mkdir(parents=True, exist_ok=True)
    (micro_dir / f"{feature}.md").write_text(
        inject_after_header("# Micro\n\n", delta_micro_navigation_block(feature)),
        encoding="utf-8",
    )


def _minimal_agents(feature: str) -> str:
    return "\n".join(
        [
            "# AGENTS",
            "",
            "## Repository root",
            "",
            "x",
            "",
        "## Planning Rosetta Stone",
        "",
        "- hook `planning.rosetta`",
        "",
        "## Startup read order",
            "",
            "x",
            "",
            "## Delta model",
            "",
            "x",
            "",
            "## Active feature",
            "",
            f"**{feature}** — test",
            "",
        ]
    )


def test_ci_check_auto_skips_pytest_in_frozen_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RepoPaths(root=tmp_path)
    _write_agents(paths, _minimal_agents("git-handoff-ci-v1"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    report = run_ci_check(
        paths, skip_pytest=False, check_map_drift=False, check_roadmap=False, check_spec_kit=False
    )

    pytest_step = next(s for s in report.steps if s.name == "pytest")
    assert pytest_step.ok is True
    assert "skipped" in pytest_step.detail


def test_parse_active_feature_from_file(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _write_agents(paths, "# AGENTS\n\n## Active feature\n\n**git-handoff-ci-v1** — complete.\n")
    assert parse_active_feature(paths) == "git-handoff-ci-v1"


def test_ci_check_validates_handoff_artifacts(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _write_agents(paths, _minimal_agents("git-handoff-ci-v1"))
    report = run_ci_check(
        paths, skip_pytest=True, check_map_drift=False, check_roadmap=False, check_spec_kit=True
    )
    handoff = next(s for s in report.steps if s.name == "handoff-artifacts")
    assert not handoff.ok

    _write_handoff_artifacts(paths, "git-handoff-ci-v1")
    report = run_ci_check(
        paths, skip_pytest=True, check_map_drift=False, check_roadmap=False, check_spec_kit=True
    )
    handoff = next(s for s in report.steps if s.name == "handoff-artifacts")
    assert handoff.ok


def test_ci_check_skips_spec_kit_when_disabled(tmp_path: Path) -> None:
    from hive_planner.project_profile import write_project_profile

    paths = RepoPaths(root=tmp_path)
    (paths.root / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    _write_agents(paths, _minimal_agents("none"))
    write_project_profile(
        paths.root,
        profile="minimal",
        project_name="demo",
        agent_handoff_mode="off",
    )
    report = run_ci_check(
        paths,
        skip_pytest=True,
        check_map_drift=False,
        check_roadmap=False,
        check_spec_kit=False,
    )
    handoff = next(s for s in report.steps if s.name == "handoff-artifacts")
    drift = next(s for s in report.steps if s.name == "spec-drift")
    assert handoff.ok is True
    assert "skipped" in handoff.detail
    assert "agent handoff off" in handoff.detail
    assert drift.ok is True
    assert "skipped" in drift.detail


def test_ci_check_detects_map_drift(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    src = paths.root / "src" / "hive_planner"
    src.mkdir(parents=True, exist_ok=True)
    (src / "newmod.py").write_text('"""New."""\n', encoding="utf-8")
    ci = paths.root / "docs" / "change-impact"
    ci.mkdir(parents=True, exist_ok=True)
    (ci / "project-map.md").write_text(
        "# Project Map\n\n| Module | Role | Spec / Delta deps |\n|--------|------|-------------------|\n",
        encoding="utf-8",
    )
    (ci / "test-map.md").write_text(
        "# Test Map\n\n| Source module | Tests |\n|---------------|-------|\n",
        encoding="utf-8",
    )
    _write_agents(paths, _minimal_agents("git-handoff-ci-v1"))
    _write_handoff_artifacts(paths, "git-handoff-ci-v1")

    report = run_ci_check(paths, skip_pytest=True, check_map_drift=True, check_roadmap=False)
    drift = next(s for s in report.steps if s.name == "impact-map-drift")
    assert not drift.ok

    report2 = run_ci_check(paths, skip_pytest=True, check_map_drift=False, check_roadmap=False)
    assert not any(s.name == "impact-map-drift" for s in report2.steps)


def test_render_does_not_duplicate_table_header(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    src = paths.root / "src" / "hive_planner"
    src.mkdir(parents=True, exist_ok=True)
    (src / "sample.py").write_text("pass\n", encoding="utf-8")
    ci = paths.root / "docs" / "change-impact"
    ci.mkdir(parents=True, exist_ok=True)
    (ci / "project-map.md").write_text(
        "# Project Map\n\n| Module | Role | Spec / Delta deps |\n|--------|------|-------------------|\n",
        encoding="utf-8",
    )
    (ci / "test-map.md").write_text(
        "# Test Map\n\n| Source module | Tests |\n|---------------|-------|\n",
        encoding="utf-8",
    )
    sync_impact_maps(paths)
    content = (ci / "project-map.md").read_text(encoding="utf-8")
    assert content.count("| Module | Role | Spec / Delta deps |") == 1
    assert content.count("|--------|------|-------------------|") == 1
