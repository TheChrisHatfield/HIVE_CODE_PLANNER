"""T016 — G5 fixture proof: conversation while a task runs; queue while awaiting approval; interrupt."""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_bot import IN_CHAT_MCP_MICROPHONE
from voice_turn_support import make_repo, make_runner, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_follow_up_is_accepted_while_a_task_runs(runner):
    first = runner.submit("CANCEL_ME hold", client_request_id="g5-1")
    wait_task_state(runner, first["task_id"], "running")
    queued = runner.submit("second question", client_request_id="g5-2")
    assert queued["status"] == "queued"
    assert queued["task_id"] is None
    runner.interrupt_playback()
    assert runner.state.coding_tasks[first["task_id"]].state == "running"
    runner.cancel(first["task_id"])
    wait_task_terminal(runner, first["task_id"])


def test_follow_up_is_held_while_awaiting_approval(runner):
    first = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="g5-ap")
    wait_task_state(runner, first["task_id"], "awaiting_approval")
    queued = runner.submit("ask something else", client_request_id="g5-q")
    assert queued["state"] == "held"
    runner.reply_approval("deny edit src/app.py")
    wait_task_terminal(runner, first["task_id"])


def test_in_chat_mcp_microphone_loop_is_not_enabled():
    assert IN_CHAT_MCP_MICROPHONE is False
