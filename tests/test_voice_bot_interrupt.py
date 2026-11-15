"""T010 — playback interruption, coding cancellation, call ending, and rollback reporting are separate.

- Stopping playback changes no task state (R7, SC-003).
- Cancellation is requested, then acknowledged or failed; the two are recorded separately (SC-011).
- Ending the call discards queued follow-ups, does not cancel the task, speaks nothing after
  the call, and reports rollback as not performed (R1, R25).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voice_turn_support import make_repo, make_runner, wait_for, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_playback_interruption_leaves_task_state_unchanged(runner):
    out = runner.submit("CANCEL_ME hold", client_request_id="i-1")
    wait_task_state(runner, out["task_id"], "running")
    before = runner.state.coding_tasks[out["task_id"]].state
    result = runner.interrupt_playback()
    assert result["event"] == "speech.interrupted"
    assert result["state_changed"] is False
    assert runner.state.coding_tasks[out["task_id"]].state == before == "running"
    assert any(e["name"] == "speech.interrupted"
               for e in runner.state.coding_tasks[out["task_id"]].events)
    runner.cancel(out["task_id"])


def test_r13_playback_interrupt_with_audio_on_leaves_running_task_unchanged(repo, monkeypatch):
    """R13 (T042 close-out): audio_enabled + Pipecat path selected; playback interrupt keeps task running."""
    import json

    import hive_planner.voice_bot as vb
    from hive_planner.voice_bot import PipecatVoiceAdapter

    cfg_dir = repo.root / ".hive" / "voice-bot"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps({"audio_enabled": True}), encoding="utf-8")

    monkeypatch.setattr(vb, "_module_installed", lambda name: True)
    paths_seen: list[str] = []

    def _record(self, text):
        paths_seen.append(text)
        return {"played": False, "audio": False, "text": text, "path": "pipecat"}

    monkeypatch.setattr(PipecatVoiceAdapter, "speak", _record)

    r = make_runner(repo)
    try:
        out = r.submit("CANCEL_ME hold", client_request_id="r13-audio")
        wait_task_state(r, out["task_id"], "running")
        # Proof the Pipecat path was selected by the audio_enabled flag (not the typed adapter).
        events = r.state.coding_tasks[out["task_id"]].events
        spoken = [e for e in events if e.get("name") == "speech.spoken"]
        assert spoken and all(e["payload"]["path"] == "pipecat" for e in spoken)
        assert paths_seen

        before = r.state.coding_tasks[out["task_id"]].state
        result = r.interrupt_playback()
        assert result["event"] == "speech.interrupted"
        assert result["state_changed"] is False
        assert r.state.coding_tasks[out["task_id"]].state == before == "running"
        assert r.session.state == "interrupted"

        r.cancel(out["task_id"])
        wait_task_terminal(r, out["task_id"])
    finally:
        r.close()


def test_acknowledged_cancel_records_requested_then_cancelled(runner):
    out = runner.submit("CANCEL_ME hold", client_request_id="c-1")
    wait_task_state(runner, out["task_id"], "running")
    runner.cancel(out["task_id"])
    assert wait_task_terminal(runner, out["task_id"]) == "cancelled"
    task = runner.state.coding_tasks[out["task_id"]]
    steps = [(t["from"], t["to"], t["reason"]) for t in task.transitions]
    assert ("running", "cancel_requested", "user_cancel") in steps  # requested
    assert ("cancel_requested", "cancelled", "cancel_acknowledged") in steps  # acknowledged
    assert task.reason == "cancel_acknowledged"


def test_cancel_the_provider_does_not_acknowledge_becomes_failed(runner):
    out = runner.submit("CANCEL_ME IGNORE_CANCEL", client_request_id="c-2")
    wait_task_state(runner, out["task_id"], "running")
    runner.cancel(out["task_id"])
    assert wait_task_terminal(runner, out["task_id"]) == "failed"
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.reason == "cancel_not_acknowledged"  # never reported as cancelled


def test_cancel_reports_rollback_not_performed(runner):
    out = runner.submit("CANCEL_ME hold", client_request_id="c-3")
    wait_task_state(runner, out["task_id"], "running")
    result = runner.cancel(out["task_id"])
    assert result["rollback"] == "not_performed"
    wait_task_terminal(runner, out["task_id"])


def test_end_call_keeps_the_task_running_and_speaks_nothing_after(runner):
    out = runner.submit("CANCEL_ME hold", client_request_id="e-1")
    wait_task_state(runner, out["task_id"], "running")
    spoken_before = runner.state.coding_tasks[out["task_id"]].evidence.spoken_update
    result = runner.end_call()
    assert result["session_ended"] is True
    assert result["active_task_state"] == "running"  # R1: ending audio does not cancel work
    assert result["rollback"] == "not_performed"

    # The task still finishes its provider turn: finish the CANCEL_ME hold by cancelling via the
    # provider (the call is over, but the task is not cancelled automatically). We verify the
    # task is not terminal yet, then release it.
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.state == "running"
    runner.cancel(out["task_id"])
    assert wait_task_terminal(runner, out["task_id"]) == "cancelled"
    assert runner.state.coding_tasks[out["task_id"]].evidence.spoken_update == spoken_before


def test_end_call_discards_queued_follow_ups(runner):
    blocker = runner.submit("CANCEL_ME hold", client_request_id="e-2")
    wait_task_state(runner, blocker["task_id"], "running")
    runner.queue_follow_up("never runs", task_id=blocker["task_id"])
    result = runner.end_call()
    assert result["discarded"] == 1
    assert runner.state.queue[0]["state"] == "discarded"
    runner.cancel(blocker["task_id"])
    wait_task_terminal(runner, blocker["task_id"])
    assert runner.state.queue[0]["task_id"] is None  # never dispatched, never a task


def test_end_call_during_pending_approval_keeps_the_approval_timeout(repo):
    import json

    cfg_dir = repo.root / ".hive" / "voice-bot"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps({"approval_timeout_s": 1}), encoding="utf-8")
    r = make_runner(repo)
    try:
        out = r.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="e-3")
        wait_task_state(r, out["task_id"], "awaiting_approval")
        result = r.end_call()
        assert result["pending_approval"] is not None  # the call end did not drop the request
        # R25: the timeout still applies after the call, so the request is recorded as timed_out.
        assert wait_task_terminal(r, out["task_id"], timeout=15) == "completed"
        task = r.state.coding_tasks[out["task_id"]]
        assert task.approvals[-1]["status"] == "timed_out"
        # R25: no speech after the call end. The last spoken line is the pre-call approval prompt.
        assert task.evidence.spoken_update.startswith("Approval needed")
        assert "Task completed" not in task.evidence.spoken_update
        assert any(t["reason"] == "approval_timed_out" for t in task.transitions)
    finally:
        r.close()


def test_submit_after_call_end_is_refused(runner):
    runner.end_call()
    from hive_planner.voice_task import DelegationError

    with pytest.raises(DelegationError) as exc:
        runner.submit("hello", client_request_id="e-4")
    assert exc.value.code == "session_not_active"
    assert wait_for(lambda: runner.session.state == "ended", timeout=2)


# -- T030: R1 session `interrupted` (spec Patch A) ----------------------------


def test_interrupt_playback_sets_session_interrupted_and_keeps_task_running(runner):
    out = runner.submit("CANCEL_ME hold", client_request_id="s-1")
    wait_task_state(runner, out["task_id"], "running")
    result = runner.interrupt_playback()
    assert result["session_state"] == "interrupted"
    assert runner.session.state == "interrupted"
    assert result["state_changed"] is False
    assert runner.state.coding_tasks[out["task_id"]].state == "running"
    runner.cancel(out["task_id"])
    wait_task_terminal(runner, out["task_id"])


def test_interrupted_session_is_persisted(repo):
    from hive_planner.voice_bot import load_state

    r = make_runner(repo)
    try:
        r.interrupt_playback()
    finally:
        r.close()
    assert load_state(repo).voice_session.state == "interrupted"


def test_submit_after_interrupt_restores_active(runner):
    runner.interrupt_playback()
    assert runner.session.state == "interrupted"
    out = runner.submit("CANCEL_ME hold", client_request_id="s-2")
    assert runner.session.state == "active"
    wait_task_state(runner, out["task_id"], "running")
    runner.cancel(out["task_id"])
    wait_task_terminal(runner, out["task_id"])


def test_follow_up_after_interrupt_restores_active(runner):
    blocker = runner.submit("CANCEL_ME hold", client_request_id="s-3")
    wait_task_state(runner, blocker["task_id"], "running")
    runner.interrupt_playback()
    assert runner.session.state == "interrupted"
    runner.queue_follow_up("after the interruption", task_id=blocker["task_id"])
    assert runner.session.state == "active"
    assert runner.state.coding_tasks[blocker["task_id"]].state == "running"
    runner.cancel(blocker["task_id"])
    wait_task_terminal(runner, blocker["task_id"])


def test_end_call_after_interrupt_moves_session_to_ended(runner):
    runner.interrupt_playback()
    result = runner.end_call()
    assert result["session_ended"] is True
    assert runner.session.state == "ended"


def test_interrupt_after_call_end_does_not_reopen_session(runner):
    runner.end_call()
    runner.interrupt_playback()
    assert runner.session.state == "ended"
