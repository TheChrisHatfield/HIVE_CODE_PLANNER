from __future__ import annotations

import json
from pathlib import Path

from hive_planner.agent_handoff import (
    AGENT_HANDOFF_OFF,
    AGENT_HANDOFF_UNIFIED,
    MARKETPLACE_CL_REL,
    apply_agent_handoff_mode,
    deploy_unified_agent_handoff,
    integrations_from_mode,
    resolve_agent_handoff_mode,
    scan_legacy_deployment,
    validate_unified_handoff,
)
from hive_planner.bootstrap import init_project
from hive_planner.config import RepoPaths
from hive_planner.project_profile import read_project_profile, write_project_profile


def _hive_source(tmp_path: Path) -> RepoPaths:
    root = tmp_path / "hive-planner"
    kit = root / "starter-kit"
    rules = root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# Architecture\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# Task Execution\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# Validation\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "cl-spec-integration.md").write_text("# CL + Spec integration\n", encoding="utf-8")
    return RepoPaths(root=root)


def test_integrations_from_mode_unified_pairs_both() -> None:
    spec, cl = integrations_from_mode(AGENT_HANDOFF_UNIFIED)
    assert spec is True
    assert cl is True
    spec, cl = integrations_from_mode(AGENT_HANDOFF_OFF)
    assert spec is False
    assert cl is False


def test_resolve_agent_handoff_mode_from_meta(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    write_project_profile(project, profile="minimal", project_name="demo", agent_handoff_mode="off")
    assert resolve_agent_handoff_mode(project) == AGENT_HANDOFF_OFF
    apply_agent_handoff_mode(project, AGENT_HANDOFF_UNIFIED)
    assert resolve_agent_handoff_mode(project) == AGENT_HANDOFF_UNIFIED


def test_deploy_unified_agent_handoff_to_existing_project(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "existing"
    init_project(source, target, agent_handoff="off")
    written, warnings = deploy_unified_agent_handoff(source, target, force=True)
    assert any("example-feature" in path for path in written)
    status = validate_unified_handoff(target)
    assert status.mode == AGENT_HANDOFF_UNIFIED
    assert status.complete is True
    assert status.missing == []
    assert (target / ".cursor" / "rules" / "integration-wiring-audit.mdc").is_file()
    assert (target / "docs" / "cl-spec-integration.md").is_file()
    meta = json.loads((target / ".hive" / "project.json").read_text(encoding="utf-8"))
    assert meta["agent_handoff_mode"] == "unified"


def test_validate_unified_handoff_flags_stale_spec_kit_overlay_rev(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "stale-overlay"
    init_project(source, target, agent_handoff="unified")
    rev_marker = target / ".hive" / "spec-kit" / ".hive-overlay-rev"
    assert rev_marker.is_file()
    rev_marker.write_text("0\n", encoding="utf-8")

    status = validate_unified_handoff(target)

    assert status.complete is False
    assert ".hive/spec-kit/.hive-overlay-rev" in status.missing


def test_validate_unified_handoff_flags_stale_cl_overlay_rev(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "stale-cl-overlay"
    init_project(source, target, agent_handoff="unified")
    rev_marker = target / ".cursor" / "plugins" / "hive-continual-learning" / ".hive-overlay-rev"
    assert rev_marker.is_file()
    rev_marker.write_text("0\n", encoding="utf-8")

    status = validate_unified_handoff(target)

    assert status.complete is False
    assert ".cursor/plugins/hive-continual-learning/.hive-overlay-rev" in status.missing


def test_validate_unified_handoff_flags_unreadable_upstream_pins(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "bad-pins"
    init_project(source, target, agent_handoff="unified")
    (target / ".hive" / "upstream-pins.json").write_text("{not-json", encoding="utf-8")

    status = validate_unified_handoff(target)

    assert status.complete is False
    assert ".hive/upstream-pins.json" in status.missing


def test_validate_unified_handoff_flags_missing_upstream_pins(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "no-pins"
    init_project(source, target, agent_handoff="unified")
    (target / ".hive" / "upstream-pins.json").unlink()

    status = validate_unified_handoff(target)

    assert status.complete is False
    assert ".hive/upstream-pins.json" in status.missing


def test_validate_unified_handoff_flags_missing_integration_rules(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "partial-unified"
    init_project(source, target, agent_handoff="unified")
    (target / ".cursor" / "rules" / "integration-wiring-audit.mdc").unlink()

    status = validate_unified_handoff(target)

    assert status.complete is False
    assert ".cursor/rules/integration-wiring-audit.mdc" in status.missing


def test_apply_agent_handoff_mode_infers_full_bootstrap_profile(tmp_path: Path) -> None:
    project = tmp_path / "legacy-full"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    apply_agent_handoff_mode(project, AGENT_HANDOFF_UNIFIED)
    meta = read_project_profile(project)
    assert meta is not None
    assert meta.bootstrap_profile == "full"


def test_scan_legacy_headless_reports_stale_cursor_plugins_not_dual_install(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, MARKETPLACE_CL_REL, scan_legacy_deployment
    from hive_planner.cl_runtime import CL_RUNTIME_HEADLESS
    from hive_planner.project_profile import write_project_profile
    from hive_planner.vendor_sync import CL_OVERLAY_REL
    from tests.test_cl_migration import _write_plugin

    project = tmp_path / "headless-stale"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(
        project,
        profile="minimal",
        project_name="headless-stale",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    report = scan_legacy_deployment(project)
    codes = {item.code for item in report.findings}

    assert "dual_cl_install" not in codes
    assert "marketplace_cl_only" not in codes
    assert "stale_cursor_cl_on_headless" in codes


def test_scan_legacy_deployment_detects_marketplace_cl(tmp_path: Path) -> None:
    project = tmp_path / "legacy-cl"
    project.mkdir()
    plugin = project / MARKETPLACE_CL_REL / ".cursor-plugin"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text('{"name":"continual-learning"}\n', encoding="utf-8")

    report = scan_legacy_deployment(project)

    assert not report.ok
    codes = {item.code for item in report.findings}
    assert "marketplace_cl_only" in codes


def test_scan_legacy_deployment_detects_dual_cl(tmp_path: Path) -> None:
    project = tmp_path / "dual-cl"
    project.mkdir()
    for rel in (
        MARKETPLACE_CL_REL,
        ".cursor/plugins/hive-continual-learning",
    ):
        plugin = project / rel / ".cursor-plugin"
        plugin.mkdir(parents=True)
        (plugin / "plugin.json").write_text('{"name":"cl"}\n', encoding="utf-8")

    report = scan_legacy_deployment(project)

    assert not report.ok
    assert any(item.code == "dual_cl_install" for item in report.findings)


def test_scan_legacy_deployment_detects_starter_kit_without_pins(tmp_path: Path) -> None:
    project = tmp_path / "starter-only"
    project.mkdir()
    (project / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")

    report = scan_legacy_deployment(project)

    codes = {item.code for item in report.findings}
    assert "missing_upstream_pins" in codes
    assert "starter_kit_only_layout" in codes


def test_scan_legacy_deployment_skips_hive_planner_source_repo(tmp_path: Path) -> None:
    repo = tmp_path / "hive-planner"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "hive-planner"\n', encoding="utf-8")
    (repo / "START_HERE.md").write_text("# Hive\n", encoding="utf-8")
    specs = repo / "docs" / "specs" / "example"
    specs.mkdir(parents=True)
    (specs / "spec.md").write_text("# Spec\n", encoding="utf-8")

    report = scan_legacy_deployment(repo)

    assert report.ok is True
    assert report.findings == []


def test_scan_legacy_deployment_clean_unified_project(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "unified-clean"
    init_project(source, target, agent_handoff="unified")

    report = scan_legacy_deployment(target)

    assert not any(item.code == "marketplace_cl_only" for item in report.findings)
    assert not any(item.code == "dual_cl_install" for item in report.findings)
