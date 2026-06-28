from __future__ import annotations

import json
from pathlib import Path

from hive_planner.agent_handoff import (
    AGENT_HANDOFF_OFF,
    AGENT_HANDOFF_UNIFIED,
    apply_agent_handoff_mode,
    deploy_unified_agent_handoff,
    integrations_from_mode,
    resolve_agent_handoff_mode,
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
