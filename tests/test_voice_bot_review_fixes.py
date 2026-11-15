"""Regression tests from the Voice_Bot code review (2026-11-10).

Each test pins one bug found in review so it cannot return:
- approval replies: a negated approve must never approve; the action label's own words
  (e.g. "deny" inside a file name) must not decide the reply.
- close(): a pending approval timer must not fire after the runner lock is released.
- restart: a task already `unknown` must still get its provider-lost timer re-armed.
- bridge: an editor snapshot with a full file and a full selection is within the R21 limit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_bot import CodingTask
from hive_planner.voice_bridge import max_submit_body_bytes, validate_tool_args
from voice_turn_support import make_repo, make_runner, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def _await_approval(runner, task_id: str) -> dict:
    wait_task_state(runner, task_id, "awaiting_approval")
    return runner.state.coding_tasks[task_id].approval


def test_negated_approve_never_approves(runner):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="neg-1")
    _await_approval(runner, out["task_id"])
    reply = runner.reply_approval("don't approve edit src/app.py")
    assert reply["status"] != "approved"
    assert runner.state.coding_tasks[out["task_id"]].state == "awaiting_approval"
    runner.reply_approval("deny edit src/app.py")
    wait_task_terminal(runner, out["task_id"])


def test_action_words_do_not_count_as_yes_or_no(runner):
    # The action label itself contains the word "deny"; a clear approve must still approve.
    out = runner.submit("NEEDS_APPROVAL:deny list cleanup", client_request_id="word-1")
    _await_approval(runner, out["task_id"])
    reply = runner.reply_approval("approve deny list cleanup")
    assert reply["status"] == "approved"
    wait_task_terminal(runner, out["task_id"])


def test_close_cancels_pending_approval_timer(repo):
    r = make_runner(repo)
    out = r.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="close-1")
    _await_approval(r, out["task_id"])
    timer = r._pending_approval["timer"]
    r.close()
    timer.join(timeout=2)
    assert not timer.is_alive(), "approval timer must not fire after close() releases the lock"


def test_unknown_task_from_before_restart_gets_a_provider_lost_timer(runner):
    now = "2026-11-10T00:00:00+00:00"
    task = CodingTask(
        task_id="task_prior000001",
        voice_session_id=runner.session.session_id,
        context_snapshot_id="ctx_prior000001",
        state="unknown",
        created_at=now,
        updated_at=now,
        client_request_id="prior-1",
        mode="ask",
        instruction="older task",
        file_path="",
    )
    runner.state.coding_tasks[task.task_id] = task
    runner._recover_after_hive_restart()
    timer = runner._provider_lost_timers.get(task.task_id)
    assert timer is not None, "an unknown task must still reach provider_lost after the window"
    timer.cancel()


def test_editor_snapshot_with_full_file_and_selection_is_within_limit(repo):
    limit = 64 * 1024
    editor = {
        "file": "src/app.py",
        "reason": None,
        "dirty": False,
        "document_version": 1,
        "file_content": "x" * limit,
        "file_truncated": True,
        "selection": {"text": "y" * limit, "truncated": True},
        "diagnostics": [],
        "diagnostics_truncated": False,
    }
    data = {
        "workspace": str(repo.root),
        "instruction": "explain this file",
        "client_request_id": "ed-1",
        "mode": "ask",
        "editor_snapshot": editor,
    }
    out = validate_tool_args(
        "submit", data, root=repo.root, instruction_max_chars=2000, snapshot_max_bytes=limit,
    )
    assert out["editor_snapshot"] == editor


def test_question_answer_reaches_the_provider(runner):
    out = runner.submit("NEEDS_QUESTION:which file", client_request_id="q-wire-1")
    _await_approval(runner, out["task_id"])
    reply = runner.reply_approval("the second one")
    assert reply["status"] == "answered"
    assert wait_task_terminal(runner, out["task_id"]) == "completed"
    written = runner.state.coding_tasks[out["task_id"]].evidence.written_result
    assert "the second one" in written
    assert '"outcome": "selected"' in written
    assert '"outcome": "cancelled"' not in written


def test_prompt_timeout_does_not_block_the_next_task(repo):
    r = make_runner(repo, timeout=0.4)
    try:
        hung = r.submit("HANG_PROMPT", client_request_id="hang-1")
        assert wait_task_terminal(r, hung["task_id"], timeout=8) == "failed"
        assert r.state.coding_tasks[hung["task_id"]].reason == "provider_timeout"
        nxt = r.submit("hello after hang", client_request_id="hang-2")
        assert wait_task_terminal(r, nxt["task_id"], timeout=8) == "completed"
    finally:
        r.close()


def test_reconnect_without_a_live_session_does_not_restore_running(runner):
    now = "2026-11-10T00:00:00+00:00"
    task = CodingTask(
        task_id="task_zombie00001",
        voice_session_id=runner.session.session_id,
        context_snapshot_id="ctx_zombie00001",
        state="unknown",
        created_at=now,
        updated_at=now,
        client_request_id="zombie-1",
        mode="ask",
        instruction="older task",
        file_path="",
        prior_state="running",
        provider_session_id="sess-gone",
    )
    runner.state.coding_tasks[task.task_id] = task
    with pytest.raises(Exception) as exc:
        runner.reconnect_task(task.task_id)
    assert "no_provider_evidence" in str(exc.value)
    assert runner.state.coding_tasks[task.task_id].state == "unknown"


def test_disconnect_while_cancel_requested_reconnects_to_cancel_requested(runner):
    """R20/R26: the real disconnect branch (_finish) records prior_state, so a reconnect
    restores cancel_requested instead of reviving the task to running with no prompt thread."""
    out = runner.submit("CANCEL_ME hold", client_request_id="rc-cancel-disc")
    task_id = out["task_id"]
    wait_task_state(runner, task_id, "running")
    runner.cancel(task_id)
    assert runner.state.coding_tasks[task_id].state == "cancel_requested"
    runner._finish(task_id, ("disconnected", "transport dropped"))
    task = runner.state.coding_tasks[task_id]
    assert task.state == "unknown"
    assert task.prior_state == "cancel_requested"
    restored = runner.reconnect_task(task_id)
    assert restored["state"] == "cancel_requested"
    assert runner.state.coding_tasks[task_id].state == "cancel_requested"


def _transition_event(task, name: str) -> dict:
    # The first event of this name is the _transition payload; _settle later adds a second
    # task.failed with tests_status and no correlation ids.
    matches = [e for e in task.events if e["name"] == name]
    assert matches, f"no {name} event recorded"
    return matches[0]["payload"]


def test_disconnect_and_timeout_events_carry_correlation_ids(runner):
    """R9 item 10: provider_disconnected and provider_timeout payloads carry task_id,
    voice_session_id, and provider_session_id, and keep the existing reason field."""
    out = runner.submit("CANCEL_ME hold", client_request_id="rc-ids-disc")
    task_id = out["task_id"]
    wait_task_state(runner, task_id, "running")
    task = runner.state.coding_tasks[task_id]
    task.provider_session_id = "sess-ids-disc"
    runner._finish(task_id, ("disconnected", "transport dropped"))
    payload = _transition_event(task, "task.unknown")
    assert payload["reason"] == "provider_disconnected"
    assert payload["task_id"] == task_id
    assert payload["voice_session_id"] == runner.session.session_id
    assert payload["provider_session_id"] == "sess-ids-disc"


def test_timeout_event_carries_correlation_ids(repo):
    r = make_runner(repo, timeout=0.4)
    try:
        hung = r.submit("HANG_PROMPT", client_request_id="rc-ids-timeout")
        task_id = hung["task_id"]
        assert wait_task_terminal(r, task_id, timeout=8) == "failed"
        task = r.state.coding_tasks[task_id]
        payload = _transition_event(task, "task.failed")
        assert payload["reason"] == "provider_timeout"
        assert payload["task_id"] == task_id
        assert payload["voice_session_id"] == r.session.session_id
        assert payload["provider_session_id"] == task.provider_session_id
    finally:
        r.close()


def test_body_cap_covers_editor_snapshot_at_full_limits():
    limit = 64 * 1024
    cap = max_submit_body_bytes(2000, limit)
    # file + selection + diagnostics can each be at the limit inside editor_snapshot
    assert cap >= 3 * limit + 2000 * 4


def test_malformed_session_update_does_not_kill_the_pump(runner):
    out = runner.submit("CANCEL_ME hold", client_request_id="pump-bad")
    wait_task_state(runner, out["task_id"], "running")
    client = runner._client
    assert client is not None
    client.notifications.put({"method": "session/update", "params": ["not-a-dict"]})
    runner._drain(client)
    runner.cancel(out["task_id"])
    assert wait_task_terminal(runner, out["task_id"]) == "cancelled"
