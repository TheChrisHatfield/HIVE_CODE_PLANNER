"""Handoff validation must surface overlay hook problems, not only missing files."""

from __future__ import annotations

import json
from pathlib import Path

from hive_planner.agent_handoff import validate_unified_handoff
from hive_planner.bootstrap import init_project
from hive_planner.config import RepoPaths


def _hive_source(tmp_path: Path) -> RepoPaths:
    root = tmp_path / "hive-planner"
    rules = root / ".cursor" / "rules"
    kit = root / "starter-kit"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# Architecture\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# Task Execution\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# Validation\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "cl-spec-integration.md").write_text("# CL + Spec integration\n", encoding="utf-8")
    return RepoPaths(root=root)


def test_handoff_flags_overlay_hooks_that_still_call_bun(tmp_path: Path) -> None:
    target = tmp_path / "bun-hooks"
    init_project(_hive_source(tmp_path), target, agent_handoff="unified")
    hooks = target / ".cursor" / "plugins" / "hive-continual-learning" / "hooks" / "hooks.json"
    hooks.write_text(
        json.dumps({"hooks": {"stop": [{"command": "bun run continual-learning-stop.py"}]}}),
        encoding="utf-8",
    )

    status = validate_unified_handoff(target)

    assert status.complete is False
    assert ".cursor/plugins/hive-continual-learning/hooks/hooks.json" in status.missing


def test_handoff_flags_hooks_json_that_omits_workspace_open(tmp_path: Path) -> None:
    target = tmp_path / "no-workspace-open"
    init_project(_hive_source(tmp_path), target, agent_handoff="unified")
    project_hooks = target / ".cursor" / "hooks.json"
    project_hooks.write_text(
        json.dumps({"version": 1, "hooks": {"stop": [{"command": "echo keep"}]}}),
        encoding="utf-8",
    )

    status = validate_unified_handoff(target)

    assert status.complete is False
    assert ".cursor/hooks.json" in status.missing
