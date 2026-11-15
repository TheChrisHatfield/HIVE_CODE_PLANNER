"""Voice_Bot code-review cascade regressions (approval state, false success, status labels).

Each test drives the real runner on a live ACP child (fixture server) where possible. Two
tests create a task directly and call the permission handler, because the state under test
(`cancel_requested`, a question with no allow option) is not reachable from a plain prompt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_acp import DEFER
from hive_planner.voice_task import VoiceTaskRunner
from voice_turn_support import make_repo, make_runner, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def _warm(runner: VoiceTaskRunner) -> None:
    """Start the persistent ACP child with a plain turn so a live client exists."""
    out = runner.submit("say hello", client_request_id="warm-1")
    assert wait_task_terminal(runner, out["task_id"]) == "completed"
    assert runner._client is not None and runner._client.is_connected()


def _manual_task(runner: VoiceTaskRunner):
    """A task in the active slot with no provider prompt behind it (test-only construction)."""
    with runner._lock:
        return runner._new_task(
            text="manual", file_path="", mode="ask", client_request_id="", queue_id=None,
        )


def test_permission_during_cancel_requested_is_refused_and_leaves_no_pending_approval(repo):
    runner = make_runner(repo)
    try:
        _warm(runner)
        task = _manual_task(runner)
        runner._transition(task, "cancel_requested", "test_cancel_requested")
        reply = runner._on_permission({
            "toolCall": {"title": "edit src/app.py", "kind": "edit"},
            "options": [{"optionId": "allow", "kind": "allow_once"}],
        })
        assert reply == {"outcome": {"outcome": "cancelled"}}
        assert runner._pending_approval is None
        assert task.state == "cancel_requested"
    finally:
        runner.close()


def test_question_without_allow_option_is_not_reported_as_answered(repo):
    runner = make_runner(repo)
    try:
        _warm(runner)
        task = _manual_task(runner)
        runner._transition(task, "running", "test_running")
        result = runner._on_permission({
            "kind": "question",
            "toolCall": {"title": "which file"},
            "options": [{"optionId": "reject", "kind": "reject_once"}],
        })
        assert result is DEFER
        reply = runner.reply_approval("the second one")
        assert reply["status"] == "not_delivered"
        assert "answer recorded" not in reply["spoken"].lower()
        assert runner._pending_approval is None
        assert task.state == "running"
        assert task.approvals[-1]["status"] == "denied"
    finally:
        runner.close()


def test_user_cancel_of_pending_approval_is_recorded_as_denied_not_timed_out(runner):
    out = runner.submit("NEEDS_APPROVAL:drop table", client_request_id="cx-1")
    wait_task_state(runner, out["task_id"], "awaiting_approval")
    runner.cancel(out["task_id"])
    wait_task_terminal(runner, out["task_id"])
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.approvals[-1]["status"] == "denied"
    assert task.approvals[-1]["detail"] == "task_cancelled"
