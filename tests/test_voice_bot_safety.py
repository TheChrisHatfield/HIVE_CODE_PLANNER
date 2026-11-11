"""T014 — secret exclusion, bounded tools, adapter swap, truncation, stale buffer, disconnect."""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_bot import (
    SecondStubAdapter,
    TypedInstructionAdapter,
    VOICE_CONTROLLER_TOOLS,
    adapter_contract_names,
    map_editor_snapshot,
)
from hive_planner.voice_task import DelegationError, VoiceTaskRunner
from voice_turn_support import make_repo, make_runner, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_secret_filename_is_excluded_from_the_snapshot(repo):
    env = repo.root / ".env.local"
    env.write_text("SECRET=aaaaaaaaaaaaaaaaaaaa", encoding="utf-8")
    r = make_runner(repo)
    try:
        out = r.submit("explain", client_request_id="sec-fn", file_path=".env.local", selection_text="SECRET=aaaaaaaaaaaaaaaaaaaa")
        snap = r.state.context_snapshots[r.state.coding_tasks[out["task_id"]].context_snapshot_id]
        assert snap.excluded == "secret"
        assert snap.selection_text == ""
        wait_task_terminal(r, out["task_id"])
    finally:
        r.close()


def test_secret_content_pattern_is_excluded(repo):
    r = make_runner(repo)
    try:
        out = r.submit(
            "explain",
            client_request_id="sec-ct",
            file_path="src/app.py",
            selection_text="token = ghp_" + ("a" * 36),
        )
        snap = r.state.context_snapshots[r.state.coding_tasks[out["task_id"]].context_snapshot_id]
        assert snap.excluded == "secret"
        assert snap.selection_text == ""
        wait_task_terminal(r, out["task_id"])
    finally:
        r.close()


def test_editor_selection_object_maps_to_selection_text(repo):
    mapped = map_editor_snapshot(
        {
            "file": "src/app.py",
            "document_version": 4,
            "dirty": False,
            "selection": {"text": "def add(a, b):", "truncated": False, "start": {"line": 1, "column": 1}, "end": {"line": 1, "column": 14}},
            "diagnostics": [{"severity": "error", "message": "oops"}],
        },
        instruction="explain add",
        workspace_root=str(repo.root),
    )
    assert mapped.selection_text == "def add(a, b):"
    assert mapped.document_version == 4
    assert mapped.diagnostics == ["error: oops"]
    r = make_runner(repo)
    try:
        out = r.submit(
            "explain add",
            client_request_id="map-1",
            editor_snapshot={
                "file": "src/app.py",
                "document_version": 4,
                "dirty": False,
                "selection": {"text": "def add(a, b):"},
                "diagnostics": [{"severity": "warning", "message": "note"}],
            },
        )
        snap = r.state.context_snapshots[r.state.coding_tasks[out["task_id"]].context_snapshot_id]
        assert snap.selection_text == "def add(a, b):"
        assert snap.document_version == 4
        assert snap.diagnostics == ["warning: note"]
        wait_task_terminal(r, out["task_id"])
    finally:
        r.close()


def test_shell_and_filesystem_tools_are_refused(runner):
    with pytest.raises(DelegationError) as exc:
        runner.invoke_controller_tool("shell", command="rm -rf /")
    assert exc.value.code == "unbounded_tool"
    with pytest.raises(DelegationError) as exc:
        runner.invoke_controller_tool("read_file", path="src/app.py")
    assert exc.value.code == "unbounded_tool"
    named = runner.invoke_controller_tool(
        "submit_coding_task",
        instruction="hello",
        client_request_id="tool-ok",
        workspace=str(runner.paths.root),
    )
    assert named["task_id"]
    wait_task_terminal(runner, named["task_id"])
    assert "shell" not in VOICE_CONTROLLER_TOOLS


def test_two_stub_adapters_share_the_same_hive_contracts():
    a = TypedInstructionAdapter()
    b = SecondStubAdapter()
    assert adapter_contract_names() == ("session", "task", "permission", "evidence")
    with pytest.raises(Exception):
        a.transcribe(b"")
    with pytest.raises(Exception):
        b.transcribe(b"")


def test_oversize_selection_is_truncated_and_flagged(repo):
    r = make_runner(repo)
    try:
        cfg = r.config
        out = r.submit(
            "explain",
            client_request_id="trunc-1",
            file_path="src/app.py",
            selection_text="x" * (cfg.snapshot_max_bytes + 10),
        )
        snap = r.state.context_snapshots[r.state.coding_tasks[out["task_id"]].context_snapshot_id]
        assert snap.truncated is True
        assert len(snap.selection_text.encode("utf-8")) <= cfg.snapshot_max_bytes
        wait_task_terminal(r, out["task_id"])
    finally:
        r.close()


def test_stale_buffer_blocks_an_approved_write(runner):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="stale-1", document_version=1, dirty=False)
    wait_task_state(runner, out["task_id"], "awaiting_approval")
    runner.set_live_buffer(lambda _path: (2, False))
    reply = runner.reply_approval("approve edit src/app.py")
    assert reply["status"] == "stale"
    task = runner.state.coding_tasks[out["task_id"]]
    assert any(e["name"] == "context.stale" for e in task.events)
    assert task.approvals[-1]["status"] == "denied"
    wait_task_terminal(runner, out["task_id"])


def test_disconnect_moves_running_task_to_unknown(repo):
    (repo.root / ".hive" / "voice-bot").mkdir(parents=True, exist_ok=True)
    (repo.root / ".hive" / "voice-bot" / "config.json").write_text(
        '{"reconnect_window_s": 1}', encoding="utf-8"
    )
    r = make_runner(repo)
    try:
        out = r.submit("CRASH_MID_TURN please", client_request_id="disc-1")
        wait_task_state(r, out["task_id"], "unknown")
        assert r.state.coding_tasks[out["task_id"]].reason == "provider_disconnected"
        assert wait_task_terminal(r, out["task_id"]) == "failed"
        assert r.state.coding_tasks[out["task_id"]].reason == "provider_lost"
    finally:
        r.close()
