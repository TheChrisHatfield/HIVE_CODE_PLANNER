"""ML-T4 / ML5: approved Moshi proposals run through the runner (R6 approval, R23 binding).

Each test drives the real VoiceTaskRunner against the stdio ACP child (voice_turn_support), so an
allowed proposal is observed as a real task in runner state, and a refused one as no task at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_moshi import MoshiConversation
from hive_planner.voice_moshi_lane import MoshiToolBroker
from voice_turn_support import make_repo, make_runner, wait_for, wait_task_terminal


class _FakeSession:
    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def send_audio(self, opus: bytes) -> None:
        self.sent.append(opus)


@pytest.fixture
def runner(tmp_path: Path):
    r = make_runner(make_repo(tmp_path))
    yield r
    r.close()


@pytest.fixture
def broker(runner):
    b = MoshiToolBroker(runner, workspace=str(runner.paths.root))
    yield b
    b.close()


def _seed_task(runner) -> tuple[str, str]:
    """Create one real task through the controller; return (task_id, context_snapshot_id)."""
    out = runner.invoke_controller_tool(
        "submit_coding_task",
        instruction="hello",
        mode="ask",
        client_request_id="seed-moshi-lane",
        workspace=str(runner.paths.root),
    )
    wait_task_terminal(runner, out["task_id"])
    return out["task_id"], runner.state.coding_tasks[out["task_id"]].context_snapshot_id


def _task_count(runner) -> int:
    return len(runner.state.coding_tasks)


SUBMIT = 'TOOL: submit_coding_task {"instruction": "add a test", "mode": "ask"}'


def test_read_only_proposal_runs_without_approval(runner, broker):
    tid, snap = _seed_task(runner)
    broker.set_snapshot(snap)
    row = broker.offer(f'TOOL: task_status {{"task_id": "{tid}"}}')
    assert row["status"] == "executed"
    assert row["result"]["task_id"] == tid
    assert broker.pending is None


def test_write_proposal_waits_for_exact_approval_then_runs(runner, broker):
    row = broker.offer(SUBMIT)
    assert row["status"] == "pending_approval"
    assert row["action"] == "submit coding task"
    assert _task_count(runner) == 0  # nothing runs before the reply

    done = broker.reply("approve submit coding task")
    assert done["status"] == "approved"
    assert done["execution"]["status"] == "executed"
    assert _task_count(runner) == 1
    (task_id,) = runner.state.coding_tasks
    assert wait_task_terminal(runner, task_id) in ("completed", "failed")
    assert broker.pending is None


def test_deny_runs_nothing(runner, broker):
    broker.offer(SUBMIT)
    done = broker.reply("deny submit coding task")
    assert done["status"] == "denied"
    assert _task_count(runner) == 0
    assert broker.pending is None


def test_reply_without_exact_label_reprompts_and_keeps_pending(runner, broker):
    broker.offer(SUBMIT)
    assert broker.reply("approve")["status"] == "reprompt"
    assert broker.pending is not None
    assert _task_count(runner) == 0


def test_negated_reply_reprompts_and_never_approves(runner, broker):
    broker.offer(SUBMIT)
    assert broker.reply("do not approve submit coding task")["status"] == "reprompt"
    assert _task_count(runner) == 0


def test_timeout_records_timed_out_and_runs_nothing(runner):
    b = MoshiToolBroker(runner, workspace=str(runner.paths.root), approval_timeout_s=0.2)
    try:
        b.offer(SUBMIT)
        assert wait_for(lambda: b.pending is None, timeout=5)
        assert b.log[-1]["status"] == "timed_out"
        assert b.reply("approve submit coding task")["status"] == "no_pending_approval"
        assert _task_count(runner) == 0
    finally:
        b.close()


def test_moshi_cannot_set_binding_fields(runner, broker):
    row = broker.offer('TOOL: submit_coding_task {"instruction": "x", "mode": "ask", "workspace": "/etc"}')
    assert row == {"status": "refused", "reason": "binding_not_allowed"}
    assert broker.pending is None
    assert _task_count(runner) == 0


def test_missing_required_and_unknown_args_are_refused(runner, broker):
    assert broker.offer('TOOL: submit_coding_task {"instruction": "x"}')["reason"] == "missing_arg"
    assert broker.offer('TOOL: task_status {"task_id": "t", "extra": 1}')["reason"] == "unknown_arg"
    assert broker.offer('TOOL: task_status {"task_id": 7}')["reason"] == "bad_arg_type"
    assert _task_count(runner) == 0


def test_agent_mode_is_refused_before_any_approval(runner, broker):
    row = broker.offer('TOOL: submit_coding_task {"instruction": "x", "mode": "agent"}')
    assert row == {"status": "refused", "reason": "agent_mode_refused"}
    assert broker.pending is None


def test_second_proposal_is_refused_while_one_approval_is_pending(runner, broker):
    _tid, snap = _seed_task(runner)
    broker.set_snapshot(snap)
    assert broker.offer(SUBMIT)["status"] == "pending_approval"
    row = broker.offer('TOOL: cancel_coding_task {"task_id": "t1"}')
    assert row == {"status": "refused", "reason": "approval_already_pending"}
    assert _task_count(runner) == 1  # only the seed task; the second proposal created nothing


def test_moshi_text_frame_becomes_pending_proposal_and_no_audio(runner, broker):
    session = _FakeSession()
    conv = MoshiConversation(session, tool_broker=broker)
    assert conv.handle_frame(0x02, SUBMIT.encode("utf-8")) is None
    assert session.sent == []  # text never goes back out as audio
    assert _task_count(runner) == 0
    assert conv.tool_results[-1]["status"] == "pending_approval"
    assert broker.pending is not None


def test_plain_speech_text_is_not_treated_as_a_proposal(runner, broker):
    conv = MoshiConversation(_FakeSession(), tool_broker=broker)
    conv.handle_frame(0x02, b"let's talk about the add function")
    assert conv.transcript == ["let's talk about the add function"]
    assert conv.tool_results == []
    assert broker.pending is None


def test_moshi_text_frame_replies_to_pending_lane_approval(runner, broker):
    conv = MoshiConversation(_FakeSession(), tool_broker=broker)
    conv.handle_frame(0x02, SUBMIT.encode("utf-8"))
    assert broker.pending is not None
    assert _task_count(runner) == 0
    conv.handle_frame(0x02, b"approve submit coding task")
    assert conv.tool_results[-1]["status"] == "approved"
    assert broker.pending is None
    assert _task_count(runner) == 1
    (task_id,) = runner.state.coding_tasks
    assert wait_task_terminal(runner, task_id) in ("completed", "failed")
