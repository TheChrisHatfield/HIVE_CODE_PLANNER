"""Tests for Voice_Bot contracts (T001)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import (
    CartridgeTrace,
    ContextSnapshot,
    TaskEvidence,
    VoiceBotError,
    create_context_snapshot,
    grounded_spoken_update,
    init_voice_session,
    load_state,
    resolve_cartridge_trace,
    resolve_cursor_agent_cli,
    save_state,
    status_summary,
    validate_context_snapshot,
    voice_bot_state_path,
)


@pytest.fixture
def repo(tmp_path: Path) -> RepoPaths:
    root = tmp_path
    (root / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (root / "AGENTS.md").write_text(
        "## Active feature\n\n- **Voice_Bot** — listed lane.\n",
        encoding="utf-8",
    )
    spec_dir = root / "docs" / "specs" / "Voice_Bot"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    cart = root / "cartridge"
    cart.mkdir(parents=True)
    (cart / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "cartridge.v1",
                "cartridge_id": "ctx-test",
                "features": ["Voice_Bot"],
            }
        ),
        encoding="utf-8",
    )
    return RepoPaths(root=root)


def test_resolve_cartridge_trace_links_spec_and_cartridge(repo: RepoPaths) -> None:
    trace = resolve_cartridge_trace(repo, "Voice_Bot")
    assert trace.cartridge_id == "ctx-test"
    assert trace.spec_path == "docs/specs/Voice_Bot/spec.md"
    assert "voice.experience" in trace.rosetta_hooks


def test_init_and_snapshot_round_trip(repo: RepoPaths) -> None:
    state = init_voice_session(repo, "Voice_Bot", provider_voice="stub")
    assert state.voice_session is not None
    assert state.voice_session.state == "active"
    snap = ContextSnapshot(
        workspace_root=str(repo.root),
        file_path="src/example.py",
        selection_text="def foo(): pass",
        document_version=3,
        dirty=False,
        instruction="Explain this function",
    )
    create_context_snapshot(repo, load_state(repo), snap)
    reloaded = load_state(repo)
    assert snap.snapshot_id in reloaded.context_snapshots


def test_validate_rejects_traversal(repo: RepoPaths) -> None:
    bad = ContextSnapshot(
        workspace_root=str(repo.root),
        file_path="../outside.py",
        selection_text="",
        document_version=0,
        dirty=False,
        instruction="hi",
    )
    with pytest.raises(VoiceBotError):
        validate_context_snapshot(bad)


def test_grounded_spoken_update_blocks_false_test_claim() -> None:
    ev = TaskEvidence(
        spoken_update="All tests passed.",
        written_result="Done.",
        tests_status="not_run",
        provider_turn_finished=True,
    )
    assert grounded_spoken_update(ev) == ""


def test_status_summary_and_persist_path(repo: RepoPaths) -> None:
    init_voice_session(repo, "Voice_Bot")
    summary = status_summary(repo, "Voice_Bot")
    assert summary["spec_ready"] is True
    assert summary["voice_session"] == "active"
    assert voice_bot_state_path(repo).is_file()
    cli = summary["cursor_agent_cli"]
    assert "available" in cli
    assert "path" in cli
    assert "version" in cli
    assert "acp_subcommand" in cli


def test_resolve_cursor_agent_cli_shape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "hive_planner.voice_bot.shutil.which",
        lambda _name: None,
    )
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    missing = resolve_cursor_agent_cli()
    assert missing["available"] is False
    assert missing["path"] is None
