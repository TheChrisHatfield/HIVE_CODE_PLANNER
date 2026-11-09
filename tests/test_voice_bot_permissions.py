"""T008 — visible approval handling: kinds, exact-match replies, timeout, denial, one pending per session.

The agent's `session/request_permission` arrives over the real stdio protocol. The runner
defers the reply; the test answers through `reply_approval` (the voice path) and the child
process reports what it received, so the outcome is observed on the wire, not assumed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from hive_planner.voice_task import VoiceTaskRunner
from voice_turn_support import make_repo, make_runner, wait_for, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def _await_approval(runner: VoiceTaskRunner, task_id: str) -> dict:
    wait_task_state(runner, task_id, "awaiting_approval")
    return runner.state.coding_tasks[task_id].approval


def test_approve_with_exact_action_and_yes_reaches_the_provider_as_selected(runner):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="ap-1")
    approval = _await_approval(runner, out["task_id"])
    assert approval["kind"] == "write_or_command"
    assert approval["action"] == "edit src/app.py"

    reply = runner.reply_approval("approve edit src/app.py")
    assert reply["status"] == "approved"
    assert wait_task_terminal(runner, out["task_id"]) == "completed"
    written = runner.state.coding_tasks[out["task_id"]].evidence.written_result
    assert '"outcome": "selected"' in written and '"optionId": "allow"' in written


def test_deny_prevents_execution_and_the_provider_sees_cancelled(runner):
    out = runner.submit("NEEDS_APPROVAL:delete build dir", client_request_id="dn-1")
    _await_approval(runner, out["task_id"])
    reply = runner.reply_approval("deny delete build dir")
    assert reply["status"] == "denied"
    assert wait_task_terminal(runner, out["task_id"]) == "completed"
    task = runner.state.coding_tasks[out["task_id"]]
    assert '"outcome": "cancelled"' in task.evidence.written_result
    assert task.approvals[-1]["status"] == "denied"


def test_ambiguous_reply_reprompts_and_never_approves(runner):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="am-1")
    _await_approval(runner, out["task_id"])
    both = runner.reply_approval("approve and deny edit src/app.py")
    assert both["status"] == "reprompt"
    partial = runner.reply_approval("approve")  # no action label
    assert partial["status"] == "reprompt"
    wrong = runner.reply_approval("approve something else")
    assert wrong["status"] == "reprompt"
    assert runner.state.coding_tasks[out["task_id"]].state == "awaiting_approval"
    runner.reply_approval("deny edit src/app.py")
    assert wait_task_terminal(runner, out["task_id"]) == "completed"


def test_ambient_speech_with_no_pending_approval_is_ignored(runner):
    out = runner.submit("hello", client_request_id="amb-1")
    wait_task_terminal(runner, out["task_id"])
    reply = runner.reply_approval("approve edit src/app.py")
    assert reply == {"status": "no_pending_approval", "spoken": ""}
    assert runner.state.queue == []  # approval replies never route to the follow-up queue


def test_unanswered_approval_times_out_and_nothing_executes(repo):
    cfg_dir = repo.root / ".hive" / "voice-bot"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps({"approval_timeout_s": 1}), encoding="utf-8")
    r = make_runner(repo)
    try:
        out = r.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="to-1")
        _await_approval(r, out["task_id"])
        assert wait_task_terminal(r, out["task_id"], timeout=15) == "completed"
        task = r.state.coding_tasks[out["task_id"]]
        assert task.approvals[-1]["status"] == "timed_out"
        assert '"outcome": "cancelled"' in task.evidence.written_result
        names = [t["to"] for t in task.transitions]
        assert names.index("awaiting_approval") < names.index("running", names.index("awaiting_approval"))
    finally:
        r.close()


def test_second_approval_request_while_one_is_pending_is_refused(runner):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="one-1")
    _await_approval(runner, out["task_id"])
    # The reader calls this same handler for each server request; a second one must be refused.
    refusal = runner._handle_server_request(
        "session/request_permission",
        {"sessionId": runner._acp_session_id,
         "toolCall": {"title": "second action", "kind": "edit"}, "options": []},
    )
    assert refusal == {"outcome": {"outcome": "cancelled"}}
    task = runner.state.coding_tasks[out["task_id"]]
    assert any(e["name"] == "approval.refused" for e in task.events)
    assert len(task.approvals) == 0  # the first request is still the only pending one
    runner.reply_approval("deny edit src/app.py")
    wait_task_terminal(runner, out["task_id"])


def test_plan_and_question_kinds_are_distinct_approvals(runner):
    plan = runner.submit("NEEDS_PLAN:apply the plan", client_request_id="pl-1")
    assert _await_approval(runner, plan["task_id"])["kind"] == "plan"
    runner.reply_approval("approve apply the plan")
    wait_task_terminal(runner, plan["task_id"])

    q = runner.submit("NEEDS_QUESTION:which file", client_request_id="qq-1")
    assert _await_approval(runner, q["task_id"])["kind"] == "question"
    empty = runner.reply_approval("   ")
    assert empty["status"] == "reprompt"
    answered = runner.reply_approval("the second one")
    assert answered["status"] == "answered"
    assert wait_task_terminal(runner, q["task_id"]) == "completed"
    task = runner.state.coding_tasks[q["task_id"]]
    assert task.approvals[-1]["status"] == "answered"
    assert task.approvals[-1]["detail"] == "the second one"


def test_pending_approval_holds_queued_follow_ups(runner):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="hd-1")
    _await_approval(runner, out["task_id"])
    follow = runner.queue_follow_up("and also this", task_id=out["task_id"])
    assert follow["state"] == "held"
    runner.reply_approval("approve edit src/app.py")
    wait_task_terminal(runner, out["task_id"])
    # After approval the held entry is released and dispatched as its own task.
    assert wait_for(lambda: runner.state.queue[0]["state"] == "dispatched", timeout=15)
    follow_task = runner.state.coding_tasks[runner.state.queue[0]["task_id"]]
    assert follow_task.instruction == "and also this"
