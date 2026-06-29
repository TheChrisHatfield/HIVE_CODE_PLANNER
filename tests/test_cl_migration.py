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
