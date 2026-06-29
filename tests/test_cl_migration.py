from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.agent_handoff import MARKETPLACE_CL_REL
from hive_planner.cl_migration import (
    ci_cl_install_step,
    merge_learned_workspace_facts,
    migrate_marketplace_cl,
)
from hive_planner.config import RepoPaths
from hive_planner.vendor_sync import CL_OVERLAY_REL


def _write_plugin(project: Path, rel: str, name: str) -> None:
    plugin = project / rel / ".cursor-plugin"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(json.dumps({"name": name}) + "\n", encoding="utf-8")
    skill = project / rel / "skills" / "continual-learning"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# skill\n", encoding="utf-8")


def _minimal_agents_with_learned() -> str:
    return "\n".join(
        [
            "# AGENTS.md",
            "",
            "## Repository root",
            "",
            "`root`",
            "",
            "## Planning Rosetta Stone",
            "",
            "- hook",
            "",
            "## Startup read order",
            "",
            "1. rosetta",
            "",
            "## Delta model",
            "",
            "- micro",
            "",
            "## Active feature",
            "",
            "**my-feature**",
            "",
            "## Learned Workspace Facts",
            "",
            "- Run ci-check before handoff.",
            "- Prefer py -3.11 for Hive CLI.",
            "",
            "## Durable Workspace Facts",
            "",
            "- Run ci-check before handoff.",
        ]
    )


def test_merge_learned_workspace_facts_dedupes(tmp_path: Path) -> None:
    text = _minimal_agents_with_learned()
    merged, count = merge_learned_workspace_facts(text)
    assert count == 1
    assert "## Learned Workspace Facts" not in merged
    assert "Prefer py -3.11 for Hive CLI." in merged
    assert merged.count("Run ci-check before handoff.") == 1


def test_run_cl_migrate_failure_includes_structured_keys(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_cl_migrate

    project = tmp_path / "missing"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")

    result = run_cl_migrate(project)
    assert result["ok"] is False
    assert result.get("warnings") or result.get("hints")




def test_migrate_preserves_inferred_unified_handoff_mode(tmp_path: Path) -> None:
    project = tmp_path / "inferred"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    feature = project / "docs" / "specs" / "example-feature"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text("# spec\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(_minimal_agents_with_learned(), encoding="utf-8")
    assert not (project / ".hive" / "project.json").is_file()
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    report = migrate_marketplace_cl(
        RepoPaths(root=project),
        remove_marketplace_plugin=True,
    )

    assert report.ok is True
    meta = json.loads((project / ".hive" / "project.json").read_text(encoding="utf-8"))
    assert meta.get("agent_handoff_mode") == "unified"
    assert meta.get("cl_source") == "vendored"

def test_migrate_marketplace_cl_merges_and_removes_plugin(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(_minimal_agents_with_learned(), encoding="utf-8")
    write_project_profile(project, profile="minimal", project_name="app", agent_handoff_mode=AGENT_HANDOFF_UNIFIED)
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    report = migrate_marketplace_cl(
        RepoPaths(root=project),
        remove_marketplace_plugin=True,
    )

    assert report.ok is True
    assert report.merged_bullets == 1
    assert report.removed_marketplace_plugin is True
    assert not (project / MARKETPLACE_CL_REL).exists()
    assert (project / ".hive" / "cl-migration.json").is_file()
    meta = json.loads((project / ".hive" / "project.json").read_text(encoding="utf-8"))
    assert meta.get("cl_source") == "vendored"


def test_ci_cl_install_step_fails_on_dual_install(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "dual"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(project, profile="minimal", project_name="dual", agent_handoff_mode=AGENT_HANDOFF_UNIFIED)
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    ok, detail = ci_cl_install_step(project)
    assert ok is False
    assert "cl-migrate" in detail


def test_migrate_fails_when_marketplace_remains_without_removal(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "partial"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(_minimal_agents_with_learned(), encoding="utf-8")
    write_project_profile(project, profile="minimal", project_name="partial", agent_handoff_mode=AGENT_HANDOFF_UNIFIED)
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    report = migrate_marketplace_cl(RepoPaths(root=project), remove_marketplace_plugin=False)

    assert report.ok is False
    assert report.warnings
    assert not (project / ".hive" / "cl-migration.json").is_file()
    meta_path = project / ".hive" / "project.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta.get("cl_source") != "vendored"


def test_migrate_still_removes_marketplace_when_agents_lint_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.agents_memory import AgentsLintReport, LintIssue
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "lint-fail"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    agents_path = project / "AGENTS.md"
    agents_path.write_text(_minimal_agents_with_learned(), encoding="utf-8")
    write_project_profile(
        project, profile="minimal", project_name="lint-fail", agent_handoff_mode=AGENT_HANDOFF_UNIFIED
    )
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    def _fail_lint(paths, agents_path=None):
        return AgentsLintReport(
            path=str(agents_path or paths.root / "AGENTS.md"),
            issues=[LintIssue(severity="error", message="simulated lint failure")],
        )

    monkeypatch.setattr("hive_planner.cl_migration.lint_agents_md", _fail_lint)

    report = migrate_marketplace_cl(RepoPaths(root=project), remove_marketplace_plugin=True)

    assert report.removed_marketplace_plugin is True
    assert not (project / MARKETPLACE_CL_REL).exists()
    assert agents_path.read_text(encoding="utf-8") == _minimal_agents_with_learned()
    assert report.ok is True
    assert any("lint failed" in warning for warning in report.warnings)
    assert not (project / ".hive" / "cl-migration.json").is_file()
    meta = json.loads((project / ".hive" / "project.json").read_text(encoding="utf-8"))
    assert meta.get("cl_source") != "vendored"


def test_migrate_rolls_back_agents_when_plugin_removal_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.cl_migration import ClMigrationError
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "remove-fail"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    agents_path = project / "AGENTS.md"
    original_agents = _minimal_agents_with_learned()
    agents_path.write_text(original_agents, encoding="utf-8")
    write_project_profile(
        project, profile="minimal", project_name="remove-fail", agent_handoff_mode=AGENT_HANDOFF_UNIFIED
    )
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    def _fail_remove(_root: Path) -> bool:
        raise ClMigrationError("simulated plugin removal failure")

    monkeypatch.setattr("hive_planner.cl_migration.remove_marketplace_cl_plugin", _fail_remove)

    report = migrate_marketplace_cl(RepoPaths(root=project), remove_marketplace_plugin=True)

    assert report.ok is False
    assert (project / MARKETPLACE_CL_REL).exists()
    assert agents_path.read_text(encoding="utf-8") == original_agents
    assert any("simulated plugin removal failure" in warning for warning in report.warnings)


def test_migrate_without_agents_md_can_still_remove_marketplace_plugin(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "no-agents"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(
        project, profile="minimal", project_name="no-agents", agent_handoff_mode=AGENT_HANDOFF_UNIFIED
    )
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    report = migrate_marketplace_cl(RepoPaths(root=project), remove_marketplace_plugin=True)

    assert report.ok is True
    assert report.removed_marketplace_plugin is True
    assert not (project / MARKETPLACE_CL_REL).exists()
    assert any("AGENTS.md not found" in warning for warning in report.warnings)


def test_ci_cl_install_step_fails_on_learned_workspace_facts(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "legacy-facts"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(_minimal_agents_with_learned(), encoding="utf-8")
    write_project_profile(
        project, profile="minimal", project_name="legacy-facts", agent_handoff_mode=AGENT_HANDOFF_UNIFIED
    )
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    ok, detail = ci_cl_install_step(project)
    assert ok is False
    assert "Learned Workspace Facts" in detail
    assert "cl-migrate" in detail


def test_run_cl_migrate_includes_cl_runtime_and_headless_hints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.agents_memory import AgentsLintReport, LintIssue
    from hive_planner.cl_runtime import CL_RUNTIME_HEADLESS
    from hive_planner.launcher.service import run_cl_migrate
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "headless-fail"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(_minimal_agents_with_learned(), encoding="utf-8")
    write_project_profile(
        project,
        profile="minimal",
        project_name="headless-fail",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )

    def _fail_lint(paths, agents_path=None):
        return AgentsLintReport(
            path=str(agents_path or paths.root / "AGENTS.md"),
            issues=[LintIssue(severity="error", message="simulated lint failure")],
        )

    monkeypatch.setattr("hive_planner.cl_migration.lint_agents_md", _fail_lint)

    result = run_cl_migrate(project)
    assert result["ok"] is False
    assert result.get("cl_runtime") == CL_RUNTIME_HEADLESS
    assert any("Headless runtime" in hint for hint in result.get("hints", []))


def test_run_cl_migrate_tailors_hints_when_plugin_removed_but_merge_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.agents_memory import AgentsLintReport, LintIssue
    from hive_planner.launcher.service import run_cl_migrate
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "partial-merge"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(_minimal_agents_with_learned(), encoding="utf-8")
    write_project_profile(
        project, profile="minimal", project_name="partial-merge", agent_handoff_mode=AGENT_HANDOFF_UNIFIED
    )
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    def _fail_lint(paths, agents_path=None):
        return AgentsLintReport(
            path=str(agents_path or paths.root / "AGENTS.md"),
            issues=[LintIssue(severity="error", message="simulated lint failure")],
        )

    monkeypatch.setattr("hive_planner.cl_migration.lint_agents_md", _fail_lint)

    result = run_cl_migrate(project, remove_marketplace_plugin=True)

    assert result["ok"] is True
    assert result["removed_marketplace_plugin"] is True
    assert any("lint failed" in warning for warning in result["warnings"])
    assert result.get("hints")
    assert any("lint" in hint.lower() for hint in result["hints"])


def test_migrate_warns_on_unexpected_marketplace_plugin_name(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "wrong-name"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(_minimal_agents_with_learned(), encoding="utf-8")
    write_project_profile(
        project, profile="minimal", project_name="wrong-name", agent_handoff_mode=AGENT_HANDOFF_UNIFIED
    )
    _write_plugin(project, MARKETPLACE_CL_REL, "not-continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    report = migrate_marketplace_cl(RepoPaths(root=project), remove_marketplace_plugin=True)

    assert report.ok is False
    assert (project / MARKETPLACE_CL_REL).exists()
    assert any("unexpected name" in warning for warning in report.warnings)
    assert not any(action == "No marketplace plugin directory detected" for action in report.actions)


def test_migrate_headless_succeeds_despite_cursor_plugin_tree(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, MARKETPLACE_CL_REL
    from hive_planner.cl_runtime import CL_RUNTIME_HEADLESS
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "headless-migrate"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## Repository root",
                "",
                "`root`",
                "",
                "## Planning Rosetta Stone",
                "",
                "- hook",
                "",
                "## Startup read order",
                "",
                "1. rosetta",
                "",
                "## Delta model",
                "",
                "- micro",
                "",
                "## Active feature",
                "",
                "**feat**",
                "",
                "## Learned Workspace Facts",
                "",
                "- Prefer py -3.11 for Hive CLI.",
                "",
                "## Durable Workspace Facts",
                "",
            ]
        ),
        encoding="utf-8",
    )
    write_project_profile(
        project,
        profile="minimal",
        project_name="headless-migrate",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )
    from tests.test_cl_migration import _write_plugin

    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")

    report = migrate_marketplace_cl(RepoPaths(root=project), remove_marketplace_plugin=False)

    assert report.ok is True
    assert report.merged_bullets == 1
    assert (project / MARKETPLACE_CL_REL).exists()
    assert (project / ".hive" / "cl-migration.json").is_file()
    assert any("cl_runtime is" in warning for warning in report.warnings)


def test_migrate_requires_hive_plugin(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "legacy"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(_minimal_agents_with_learned(), encoding="utf-8")
    write_project_profile(project, profile="minimal", project_name="legacy", agent_handoff_mode=AGENT_HANDOFF_UNIFIED)
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")

    report = migrate_marketplace_cl(RepoPaths(root=project))
    assert report.ok is False
