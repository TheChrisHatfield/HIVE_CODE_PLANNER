from __future__ import annotations

from pathlib import Path

from hive_planner.config import RepoPaths
from hive_planner.launcher.service import prepare_linked_project_root, run_project_ci_check
from hive_planner.spec_drift import parse_active_feature


def _agents_none() -> str:
    return "\n".join(
        [
            "# AGENTS.md",
            "",
            "## Planning Rosetta Stone",
            "",
            "- hook `planning.rosetta`",
            "",
            "## Active feature",
            "",
            "**None** — set when Spec Kit work begins.",
            "",
        ]
    )


def _bare_example_feature(project: Path) -> None:
    feature = "example-feature"
    spec_dir = project / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (spec_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (spec_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    micro = project / "docs" / "delta" / "20_micro"
    micro.mkdir(parents=True)
    (micro / f"{feature}.md").write_text("# Micro\n", encoding="utf-8")


def test_ci_check_does_not_set_active_feature_when_spec_gates_fail(tmp_path: Path) -> None:
    project = tmp_path / "legacy-app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    before = _agents_none()
    (project / "AGENTS.md").write_text(before, encoding="utf-8")
    _bare_example_feature(project)

    result = run_project_ci_check(project)

    assert result.get("repair") is None
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == before
    assert parse_active_feature(RepoPaths(root=project)) is None


def test_prepare_linked_root_does_not_set_active_feature_when_spec_gates_fail(tmp_path: Path) -> None:
    project = tmp_path / "app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    before = _agents_none()
    (project / "AGENTS.md").write_text(before, encoding="utf-8")
    _bare_example_feature(project)

    root, repair = prepare_linked_project_root(project)

    assert root == project.resolve()
    assert repair is None
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == before
    assert parse_active_feature(RepoPaths(root=project)) is None
