"""Regression tests from the Voice_Bot 10-layer code-review cascade (2026-11-10).

Each test pins one confirmed bug:
- C1 (R2/R28): an editor snapshot already marked excluded must not be refilled from disk,
  and the ACP prompt must not include that payload.
- C2 (R9): submit after close must refuse; _save after close must not rewrite state.
- C3 (R5): queue_full carries a spoken notice.
- C4 (R21): instruction_too_long carries a spoken notice.
- C5 (R6): agent_mode_disabled carries a spoken notice.
- C7 (R22): write approval compares the live editor snapshot from the reply, not the stored one.
- C14 (R22): a live snapshot of a different file with the same version/dirty cannot approve a write.
- C15 (R9): cancel after close must refuse; it must not report cancel_requested without a save.
- C1-close (R9): close during ACP handshake must kill the unassigned child (Stop Bridge).
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

from hive_planner.voice_acp import AcpClient
from hive_planner.voice_bot import VoiceBotError, load_state, voice_bot_state_path
from hive_planner.voice_task import DelegationError, VoiceTaskRunner
from voice_turn_support import (
    TURN_SERVER,
    make_repo,
    make_runner,
    wait_for,
    wait_task_state,
    wait_task_terminal,
)


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_excluded_editor_snapshot_is_not_refilled_from_disk(runner):
    secret_selection = "token = ghp_" + ("a" * 36)
    out = runner.submit(
        "explain add",
        client_request_id="nn-c1",
        editor_snapshot={
            "file": "src/app.py",
            "dirty": False,
            "document_version": 1,
            "selection": {"text": secret_selection, "truncated": False},
            "file_content": "",
            "diagnostics": [],
        },
    )
    task = runner.state.coding_tasks[out["task_id"]]
    snap = runner.state.context_snapshots[task.context_snapshot_id]
    assert snap.excluded == "secret"
    assert snap.selection_text == ""
    assert snap.file_content == ""
    prompt = runner._prompt_text(task)
    assert "def add" not in prompt
    assert "ghp_" not in prompt
    wait_task_terminal(runner, out["task_id"])


def test_submit_after_close_does_not_write_state(repo):
    r = make_runner(repo)
    first = r.submit("explain add", client_request_id="nn-c2-open")
    wait_task_terminal(r, first["task_id"])
    r.close()
    with pytest.raises(DelegationError) as exc:
        r.submit("explain add", client_request_id="nn-c2-closed")
    assert exc.value.code == "session_not_active"
    assert exc.value.spoken == "The voice session has ended. Nothing was submitted."
    r.state.queue.append({"queue_id": "should_not_persist"})
    r._save()
    assert all(q.get("queue_id") != "should_not_persist" for q in load_state(repo).queue)
    assert "should_not_persist" not in voice_bot_state_path(repo).read_text(encoding="utf-8")


def test_queue_full_includes_spoken_notice(repo):
    cfg_dir = repo.root / ".hive" / "voice-bot"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps({"queue_depth": 1}), encoding="utf-8")
    r = make_runner(repo)
    try:
        blocker = r.submit("CANCEL_ME block", client_request_id="nn-c3-0")
        wait_task_state(r, blocker["task_id"], "running")
        r.queue_follow_up("one", task_id=blocker["task_id"])
        with pytest.raises(DelegationError) as exc:
            r.queue_follow_up("two", task_id=blocker["task_id"])
        assert exc.value.code == "queue_full"
        assert exc.value.spoken
        r.cancel(blocker["task_id"])
    finally:
        r.close()


def test_instruction_too_long_includes_spoken_notice(runner):
    over = "x" * (runner.config.instruction_max_chars + 1)
    with pytest.raises(DelegationError) as exc:
        runner.submit(over, client_request_id="nn-c4")
    assert exc.value.code == "instruction_too_long"
    assert exc.value.spoken


def test_agent_mode_disabled_includes_spoken_notice(runner):
    with pytest.raises(DelegationError) as exc:
        runner.submit("explain add", mode="agent", client_request_id="nn-c5")
    assert exc.value.code == "agent_mode_disabled"
    assert exc.value.spoken


def test_write_approval_uses_live_editor_snapshot_not_the_stored_one(runner):
    """R22: a buffer that changed during the approval wait is blocked at reply time."""
    out = runner.submit(
        "NEEDS_APPROVAL:edit src/app.py",
        client_request_id="nn-c7",
        file_path="src/app.py",
        document_version=1,
        dirty=False,
    )
    wait_task_state(runner, out["task_id"], "awaiting_approval")
    reply = runner.reply_approval(
        "approve edit src/app.py",
        editor_snapshot={"document_version": 2, "dirty": False},
    )
    assert reply["status"] == "stale"
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.approvals[-1]["status"] == "denied"
    wait_task_terminal(runner, out["task_id"])


def test_matching_live_editor_snapshot_still_approves(runner):
    out = runner.submit(
        "NEEDS_APPROVAL:edit src/app.py",
        client_request_id="nn-c7b",
        file_path="src/app.py",
        document_version=4,
        dirty=False,
    )
    wait_task_state(runner, out["task_id"], "awaiting_approval")
    reply = runner.reply_approval(
        "approve edit src/app.py",
        editor_snapshot={"file": "src/app.py", "document_version": 4, "dirty": False},
    )
    assert reply["status"] == "approved"
    wait_task_terminal(runner, out["task_id"])


def test_write_approval_rejects_matching_version_on_a_different_file(runner):
    """R22: the live buffer is the bound snapshot file, not whichever editor is active."""
    out = runner.submit(
        "NEEDS_APPROVAL:edit src/app.py",
        client_request_id="nn-c14",
        file_path="src/app.py",
        document_version=1,
        dirty=False,
    )
    wait_task_state(runner, out["task_id"], "awaiting_approval")
    reply = runner.reply_approval(
        "approve edit src/app.py",
        editor_snapshot={"file": "src/other.py", "document_version": 1, "dirty": False},
    )
    assert reply["status"] == "stale"
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.approvals[-1]["status"] == "denied"
    wait_task_terminal(runner, out["task_id"])


def test_cancel_after_close_does_not_report_success(repo):
    r = make_runner(repo)
    out = r.submit("CANCEL_ME block", client_request_id="nn-c15")
    wait_task_state(r, out["task_id"], "running")
    r.close()
    with pytest.raises(DelegationError) as exc:
        r.cancel(out["task_id"])
    assert exc.value.code == "session_not_active"
    assert exc.value.spoken
    loaded = load_state(repo).coding_tasks[out["task_id"]]
    assert loaded.state == "running"


def test_acp_fs_read_serves_workspace_file_and_refuses_escape(runner, repo):
    """C1: live runner must serve ACP fs/read the way G2 live_prompt does (R23)."""
    target = repo.root / "src" / "app.py"
    inside = runner._handle_server_request(
        "fs/read_text_file",
        {"path": str(target)},
    )
    assert "def add" in inside["content"]
    camel = runner._handle_server_request(
        "fs/readTextFile",
        {"path": "src/app.py"},
    )
    assert camel["content"] == inside["content"]
    with pytest.raises(VoiceBotError, match="fs_read_outside_workspace"):
        runner._handle_server_request(
            "fs/read_text_file",
            {"path": str(repo.root.parent / "secret.py")},
        )
    hive_secret = repo.root / ".hive" / "voice-bot" / "bridge-token"
    hive_secret.parent.mkdir(parents=True, exist_ok=True)
    hive_secret.write_text("secret-token", encoding="utf-8")
    with pytest.raises(VoiceBotError, match="fs_read_protected"):
        runner._handle_server_request("fs/read_text_file", {"path": str(hive_secret)})
    with pytest.raises(VoiceBotError, match="fs_read_protected"):
        runner._handle_server_request("fs/read_text_file", {"path": ".hive/voice-bot/bridge-token"})
    # U11b: writes go through the approval broker. With no active task the broker refuses,
    # so nothing reaches disk (write gate tests cover the approved path).
    before = target.read_text(encoding="utf-8")
    with pytest.raises(VoiceBotError, match="fs_write_refused"):
        runner._handle_server_request("fs/write_text_file", {"path": str(target), "content": "x"})
    assert target.read_text(encoding="utf-8") == before


def test_pending_approval_view_names_the_bound_file(runner):
    out = runner.submit(
        "NEEDS_APPROVAL:edit src/app.py",
        client_request_id="nn-c16",
        file_path="src/app.py",
    )
    wait_task_state(runner, out["task_id"], "awaiting_approval")
    view = runner.pending_approval_view()
    assert view["pending"] is True
    assert view["file_path"] == "src/app.py"
    runner.reply_approval("deny edit src/app.py")
    wait_task_terminal(runner, out["task_id"])


def test_close_during_acp_handshake_kills_unassigned_child(repo):
    """C1 (R9): Stop Bridge during initialize must terminate the child that is not yet _client."""
    hold = threading.Event()
    created: list[AcpClient] = []

    def factory(handler):
        client = AcpClient(
            [sys.executable, str(TURN_SERVER)],
            cwd=str(repo.root),
            server_request_handler=handler,
        )
        created.append(client)
        hold.wait(timeout=5)
        return client

    r = VoiceTaskRunner(repo, "Voice_Bot", client_factory=factory, request_timeout=20.0)
    worker: threading.Thread | None = None
    try:
        worker = threading.Thread(
            target=lambda: r.submit("explain add", client_request_id="nn-c1-close"),
            daemon=True,
        )
        worker.start()
        assert wait_for(lambda: bool(created))
        r.close()
        hold.set()
        worker.join(timeout=15)
        assert created[0]._proc.poll() is not None
        assert r._client is None
        r2 = make_runner(repo)
        try:
            out = r2.submit("explain add", client_request_id="nn-c1-after")
            wait_task_terminal(r2, out["task_id"])
        finally:
            r2.close()
    finally:
        hold.set()
        if worker is not None:
            worker.join(timeout=5)
        if not r._closed:
            r.close()
