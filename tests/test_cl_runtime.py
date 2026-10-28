from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, unified_handoff_artifacts, validate_unified_handoff
from hive_planner.cl_migration import ci_cl_install_step
from hive_planner.cl_runtime import (
    CL_RUNTIME_EXTERNAL,
    CL_RUNTIME_HEADLESS,
    HEADLESS_CL_WORKFLOW_REL,
    cl_runtime_launcher_choice,
    deploy_headless_cl_artifacts,
    normalize_cl_runtime,
    requires_cursor_plugin,
    resolve_cl_runtime,
    set_project_cl_runtime,
)
from hive_planner.project_profile import read_project_profile, write_project_profile


def test_normalize_cl_runtime_aliases() -> None:
    assert normalize_cl_runtime("cli") == CL_RUNTIME_HEADLESS
    assert normalize_cl_runtime("cursor") == "cursor"


def test_cl_runtime_launcher_choice_maps_external_to_headless() -> None:
    assert cl_runtime_launcher_choice(CL_RUNTIME_EXTERNAL) == CL_RUNTIME_HEADLESS
    assert cl_runtime_launcher_choice(CL_RUNTIME_HEADLESS) == CL_RUNTIME_HEADLESS
    assert cl_runtime_launcher_choice("cursor") == "cursor"


def test_set_and_resolve_cl_runtime(tmp_path: Path) -> None:
    project = tmp_path / "app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(project, profile="minimal", project_name="app", agent_handoff_mode=AGENT_HANDOFF_UNIFIED)

    set_project_cl_runtime(project, CL_RUNTIME_HEADLESS)
    meta = read_project_profile(project)
    assert meta is not None
    assert meta.cl_runtime == CL_RUNTIME_HEADLESS
    assert resolve_cl_runtime(project) == CL_RUNTIME_HEADLESS


def test_headless_deploy_writes_workflow_and_manifest(tmp_path: Path) -> None:
    project = tmp_path / "headless"
    project.mkdir()
    written: list[str] = []
    deploy_headless_cl_artifacts(project, CL_RUNTIME_HEADLESS, force=True, written=written)

    assert (project / HEADLESS_CL_WORKFLOW_REL).is_file()
    assert (project / ".hive" / "cl-runtime.json").is_file()
    assert HEADLESS_CL_WORKFLOW_REL in written


def test_unified_handoff_artifacts_runtime_aware(tmp_path: Path) -> None:
    project = tmp_path / "mixed"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(
        project,
        profile="minimal",
        project_name="mixed",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )

    artifacts = unified_handoff_artifacts(project)
    assert HEADLESS_CL_WORKFLOW_REL in artifacts
    assert ".cursor/plugins/hive-continual-learning/WORKFLOW.md" not in artifacts
    assert requires_cursor_plugin(resolve_cl_runtime(project)) is False


def test_unified_handoff_artifacts_follow_active_feature(tmp_path: Path) -> None:
    project = tmp_path / "renamed"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(
        "# AGENTS\n\n## Active feature\n\n**my-feature**\n",
        encoding="utf-8",
    )
    write_project_profile(project, profile="minimal", project_name="renamed", agent_handoff_mode=AGENT_HANDOFF_UNIFIED)
    artifacts = unified_handoff_artifacts(project)
    assert "docs/specs/my-feature/spec.md" in artifacts
    assert "docs/specs/example-feature/spec.md" not in artifacts
    status = validate_unified_handoff(project)
    assert "docs/specs/example-feature/spec.md" not in status.missing
    assert "docs/specs/my-feature/spec.md" in status.missing


def test_overlay_issues_as_missing_skips_cursor_cl_for_headless(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import CL_OVERLAY_REL, overlay_issues_as_missing

    project = tmp_path / "headless-overlay"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(
        project,
        profile="minimal",
        project_name="headless-overlay",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )
    deploy_headless_cl_artifacts(project, CL_RUNTIME_HEADLESS, force=True)

    overlay_missing = overlay_issues_as_missing(project, None)
    assert not any(rel.startswith(CL_OVERLAY_REL) for rel in overlay_missing)

    status = validate_unified_handoff(project)
    assert ".cursor/plugins/hive-continual-learning/WORKFLOW.md" not in status.missing


def test_ci_cl_install_headless_requires_workflow_artifact(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.cl_runtime import CL_RUNTIME_HEADLESS
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "headless-no-workflow"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(
        project,
        profile="minimal",
        project_name="headless-no-workflow",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )

    ok, detail = ci_cl_install_step(project)
    assert ok is False
    assert "continual-learning/WORKFLOW.md" in detail


def test_ci_cl_install_headless_skips_cursor_plugin_checks(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import CL_OVERLAY_REL

    project = tmp_path / "ci-headless"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(
        project,
        profile="minimal",
        project_name="ci-headless",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )
    deploy_headless_cl_artifacts(project, CL_RUNTIME_HEADLESS, force=True)
    plugin = project / CL_OVERLAY_REL / ".cursor-plugin"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text('{"name":"hive-continual-learning"}\n', encoding="utf-8")

    ok, detail = ci_cl_install_step(project)
    assert ok is True
    assert "headless" in detail


def test_headless_deploy_warns_when_cursor_plugins_remain(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import MARKETPLACE_CL_REL
    from hive_planner.config import RepoPaths
    from hive_planner.vendor_sync import CL_OVERLAY_REL, deploy_unified_vendor_artifacts
    from tests.test_cl_migration import _write_plugin

    source = tmp_path / "hive"
    source.mkdir()
    target = tmp_path / "project"
    target.mkdir()
    (target / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    _write_plugin(target, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(target, CL_OVERLAY_REL, "hive-continual-learning")

    warnings: list[str] = []
    deploy_unified_vendor_artifacts(
        source,
        target,
        force=True,
        warnings=warnings,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )

    assert any("Cursor CL plugin tree still present" in item for item in warnings)
    assert any("hive-continual-learning overlay still present" in item for item in warnings)


def test_init_headless_runtime_skips_cursor_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.bootstrap import init_project
    from hive_planner.config import RepoPaths
    from hive_planner.vendor_sync import CL_OVERLAY_REL

    source = tmp_path / "hive"
    source.mkdir()
    (source / "START_HERE.md").write_text("# hive\n", encoding="utf-8")
    (source / "docs").mkdir()
    (source / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")
    kit = source / "starter-kit"
    kit.mkdir()
    (kit / "spec-kit-agent-integration.md").write_text("# kit\n", encoding="utf-8")
    monkeypatch.setattr(
        "hive_planner.bootstrap._starter_kit_dir",
        lambda _root: kit,
    )

    target = tmp_path / "new-headless"
    result = init_project(
        RepoPaths(root=source),
        target,
        force=True,
        agent_handoff="unified",
        cl_runtime=CL_RUNTIME_HEADLESS,
    )
    assert (result.target / HEADLESS_CL_WORKFLOW_REL).is_file()
    assert not (result.target / CL_OVERLAY_REL).exists()
    meta = read_project_profile(result.target)
    assert meta is not None
    assert meta.cl_runtime == CL_RUNTIME_HEADLESS

def test_ci_cl_install_headless_fails_on_marketplace_plugin(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, MARKETPLACE_CL_REL
    from tests.test_cl_migration import _write_plugin

    project = tmp_path / "headless-marketplace"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(
        project,
        profile="minimal",
        project_name="headless-marketplace",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )
    deploy_headless_cl_artifacts(project, CL_RUNTIME_HEADLESS, force=True)
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")

    ok, detail = ci_cl_install_step(project)
    assert ok is False
    assert "cl-migrate" in detail
    assert "--remove-marketplace-plugin" not in detail


def test_ci_cl_install_headless_dual_marketplace_uses_remove_flag(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, MARKETPLACE_CL_REL
    from hive_planner.vendor_sync import CL_OVERLAY_REL
    from tests.test_cl_migration import _write_plugin

    project = tmp_path / "headless-dual"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(
        project,
        profile="minimal",
        project_name="headless-dual",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )
    deploy_headless_cl_artifacts(project, CL_RUNTIME_HEADLESS, force=True)
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    ok, detail = ci_cl_install_step(project)
    assert ok is False
    assert "--remove-marketplace-plugin" in detail
