"""T020 — R25–R29 through submit and approval paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_bot import map_editor_snapshot
from hive_planner.voice_task import DelegationError, VoiceTaskRunner
from voice_turn_support import make_repo, make_runner, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


def test_call_end_during_pending_approval_does_not_cancel_and_does_not_speak(repo):
    r = make_runner(repo)
    try:
        out = r.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="e-ap")
        wait_task_state(r, out["task_id"], "awaiting_approval")
        spoken_before = r.state.coding_tasks[out["task_id"]].evidence.spoken_update
        ended = r.end_call()
        assert ended["active_task_state"] == "awaiting_approval"
        assert r.state.coding_tasks[out["task_id"]].state == "awaiting_approval"
        r.reply_approval("deny edit src/app.py")
        wait_task_terminal(r, out["task_id"])
        assert r.state.coding_tasks[out["task_id"]].evidence.spoken_update == spoken_before
    finally:
        r.close()


def test_restart_moves_in_flight_task_to_unknown_and_discards_queue(repo, monkeypatch):
    (repo.root / ".hive" / "voice-bot").mkdir(parents=True, exist_ok=True)
    (repo.root / ".hive" / "voice-bot" / "config.json").write_text(
        '{"reconnect_window_s": 1}', encoding="utf-8"
    )

    def fake_launch(self, task_id: str) -> None:
        with self._lock:
            task = self.state.coding_tasks[task_id]
            if task.state == "submitted":
                self._transition(task, "running", "provider_accepted")
                self._save()

    monkeypatch.setattr(VoiceTaskRunner, "_launch", fake_launch)
    first = make_runner(repo)
    out = first.submit("hold without a provider", client_request_id="rst-1")
    wait_task_state(first, out["task_id"], "running")
    first.submit("queued later", client_request_id="rst-q")
    session_id = first.session.session_id
    task_id = out["task_id"]
    first.close()

    second = make_runner(repo)
    try:
        task = second.state.coding_tasks[task_id]
        assert task.state == "unknown"
        assert task.reason == "hive_restarted"
        assert all(q["state"] == "discarded" for q in second.state.queue if q.get("client_request_id") == "rst-q")
        dup = second.submit("hold without a provider", client_request_id="rst-1")
        assert dup["task_id"] == task_id
        assert dup["state"] == "unknown"
        assert second.session.session_id == session_id
        restored = second.reconnect_task(task_id)
        assert restored["state"] == "running"
        second.cancel(task_id)
        wait_task_terminal(second, task_id)
    finally:
        second.close()


def test_second_approval_is_refused_while_one_is_pending(repo):
    r = make_runner(repo)
    try:
        out = r.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="one-ap")
        wait_task_state(r, out["task_id"], "awaiting_approval")
        view = r.pending_approval_view()
        assert view["pending"] is True
        r.reply_approval("deny edit src/app.py")
        wait_task_terminal(r, out["task_id"])
    finally:
        r.close()


def test_snapshot_scope_no_file_unsaved_and_binary(repo):
    none = map_editor_snapshot(
        {"file": None, "reason": "no_active_file", "selection": None, "dirty": False},
        instruction="workspace question",
        workspace_root=str(repo.root),
    )
    assert none.file_path == ""
    unsaved = map_editor_snapshot(
        {"file": "src/app.py", "dirty": True, "selection": {"text": "not yet saved"}},
        instruction="explain",
        workspace_root=str(repo.root),
    )
    assert unsaved.excluded == "unsaved"
    assert unsaved.selection_text == ""
    binary = map_editor_snapshot(
        {"file": "src/app.py", "dirty": False, "selection": {"text": "a\x00b"}},
        instruction="explain",
        workspace_root=str(repo.root),
    )
    assert binary.excluded == "binary"
    r = make_runner(repo)
    try:
        out = r.submit("workspace question", client_request_id="no-file")
        snap = r.state.context_snapshots[r.state.coding_tasks[out["task_id"]].context_snapshot_id]
        assert snap.file_path == ""
        wait_task_terminal(r, out["task_id"])
    finally:
        r.close()


def test_agent_mode_stays_disabled(repo):
    r = make_runner(repo)
    try:
        with pytest.raises(DelegationError) as exc:
            r.submit("edit it", mode="agent", client_request_id="no-edit")
        assert exc.value.code == "agent_mode_disabled"
    finally:
        r.close()
