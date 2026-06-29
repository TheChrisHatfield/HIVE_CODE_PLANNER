from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, unified_handoff_artifacts, validate_unified_handoff
from hive_planner.cl_migration import ci_cl_install_step
from hive_planner.cl_runtime import (
    CL_RUNTIME_HEADLESS,
    HEADLESS_CL_WORKFLOW_REL,
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
