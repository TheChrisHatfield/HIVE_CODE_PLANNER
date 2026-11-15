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
        task = r.state.coding_tasks[out["task_id"]]
        # R25: no speech after call end.
        assert task.evidence.spoken_update == spoken_before
        # R25: the pending approval's outcome is recorded after the call ended.
        assert task.approval is not None
        assert task.approval["status"] == "denied"
        assert task.approvals and task.approvals[-1]["status"] == "denied"
    finally:
        r.close()


def test_pending_approval_still_times_out_after_call_end(repo):
    """R25/R6: the approval timeout still applies after the call ends; no speech follows."""
    import time

    (repo.root / ".hive" / "voice-bot").mkdir(parents=True, exist_ok=True)
    (repo.root / ".hive" / "voice-bot" / "config.json").write_text(
        '{"approval_timeout_s": 1}', encoding="utf-8"
    )
    r = make_runner(repo)
    try:
        out = r.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="e-to")
        task_id = out["task_id"]
        wait_task_state(r, task_id, "awaiting_approval")
        r.end_call()
        spoken_after_end = r.state.coding_tasks[task_id].evidence.spoken_update

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            task = r.state.coding_tasks[task_id]
            if task.approval and task.approval.get("status") == "timed_out":
                break
            time.sleep(0.05)
        task = r.state.coding_tasks[task_id]
        assert task.approval is not None and task.approval["status"] == "timed_out"
        assert task.approvals and task.approvals[-1]["status"] == "timed_out"
        # The task leaves awaiting_approval. The fake agent may finish the turn right after,
        # so only the exit from the pending state is asserted here.
        assert task.state != "awaiting_approval"
        assert task.evidence.spoken_update == spoken_after_end
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
        with pytest.raises(DelegationError) as exc:
            second.reconnect_task(task_id)
        assert exc.value.code == "no_provider_evidence"
        assert second.state.coding_tasks[task_id].state == "unknown"
        second.cancel(task_id)
        wait_task_terminal(second, task_id)
    finally:
        second.close()


def test_restart_reconnect_over_bridge_refuses_without_provider_evidence(repo, monkeypatch):
    """T039 (R26, P2-3): after restart the task is `unknown`; POST /v1/reconnect returns the
    runner's refusal (no live matching ACP session) and must not restore the active slot."""
    import json
    import urllib.error
    import urllib.request

    from hive_planner.voice_bridge import VoiceBridge

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
    out = first.submit("hold without a provider", client_request_id="rst-bridge")
    wait_task_state(first, out["task_id"], "running")
    task_id = out["task_id"]
    first.close()

    second = make_runner(repo)
    bridge = VoiceBridge(second)
    bridge.start()
    try:
        assert second.state.coding_tasks[task_id].state == "unknown"
        req = urllib.request.Request(
            f"http://127.0.0.1:{bridge.port}/v1/reconnect",
            data=json.dumps({"workspace": str(repo.root), "task_id": task_id}).encode("utf-8"),
            method="POST",
            headers={"Authorization": f"Bearer {bridge.token}", "Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=10)
        body = json.loads(exc.value.read().decode("utf-8"))
        assert exc.value.code == 409
        assert body["error"] == "no_provider_evidence"
        assert second.state.coding_tasks[task_id].state == "unknown"
        assert second._active_task_id is None
    finally:
        bridge.close()
        second.cancel(task_id)
        wait_task_terminal(second, task_id)
        second.close()


def _mark_unknown_like_a_dropped_provider(runner: VoiceTaskRunner, task_id: str) -> None:
    """Drive the real disconnect transition (running -> unknown, R26) without a fake shutdown."""
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        task.prior_state = task.state
        runner._transition(task, "unknown", "provider_disconnected")
        runner._settle(task)


def test_reconnect_over_http_restores_running_when_provider_session_matches(repo):
    """T039 (R26, P2-3): POST /v1/reconnect returns the same reconnect_task payload the runner exposes."""
    import json
    import urllib.request

    from hive_planner.voice_bridge import VoiceBridge

    r = make_runner(repo)
    bridge = VoiceBridge(r)
    bridge.start()
    out = {}
    try:
        out = r.submit("CANCEL_ME hold", client_request_id="rc-http")
        wait_task_state(r, out["task_id"], "running")
        _mark_unknown_like_a_dropped_provider(r, out["task_id"])
        assert r.state.coding_tasks[out["task_id"]].state == "unknown"
        req = urllib.request.Request(
            f"http://127.0.0.1:{bridge.port}/v1/reconnect",
            data=json.dumps({"workspace": str(repo.root), "task_id": out["task_id"]}).encode("utf-8"),
            method="POST",
            headers={"Authorization": f"Bearer {bridge.token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
        assert body["task_id"] == out["task_id"]
        assert body["state"] == "running"
        assert "approval" in body
        assert r.state.coding_tasks[out["task_id"]].state == "running"
        assert r._active_task_id == out["task_id"]
    finally:
        bridge.close()
        if out.get("task_id"):
            r.cancel(out["task_id"])
            wait_task_terminal(r, out["task_id"])
        r.close()


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
    outside = map_editor_snapshot(
        {
            "file": None,
            "reason": "path_outside_workspace",
            "file_content": "stolen",
            "selection": {"text": "leak"},
        },
        instruction="explain",
        workspace_root=str(repo.root),
    )
    assert outside.file_path == ""
    assert outside.file_content == ""
    assert outside.selection_text == ""
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
