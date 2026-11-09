"""T009 — one active turn, FIFO follow-up queue (depth from config), held while awaiting approval,
dedupe via client_request_id, and dispatch once the active slot frees.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.voice_task import DelegationError
from voice_turn_support import make_repo, make_runner, wait_for, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_submit_while_busy_queues_without_issuing_a_task_id(runner):
    blocker = runner.submit("CANCEL_ME block", client_request_id="b-1")
    wait_task_state(runner, blocker["task_id"], "running")
    queued = runner.submit("later one", client_request_id="b-2")
    assert queued["status"] == "queued"
    assert queued["task_id"] is None
    assert len(runner.state.coding_tasks) == 1  # a queue entry is not a task (R5)
    assert runner.state.queue[0]["state"] == "queued"
    runner.cancel(blocker["task_id"])


def test_queue_dispatches_fifo_after_the_active_task_finishes(runner):
    blocker = runner.submit("CANCEL_ME block", client_request_id="f-0")
    wait_task_state(runner, blocker["task_id"], "running")
    runner.queue_follow_up("first queued", task_id=blocker["task_id"])
    runner.queue_follow_up("second queued", task_id=blocker["task_id"])
    runner.cancel(blocker["task_id"])

    assert wait_for(lambda: all(q["state"] == "dispatched" for q in runner.state.queue), timeout=20)
    runner.wait_idle(timeout=20)
    dispatched = [runner.state.coding_tasks[q["task_id"]] for q in runner.state.queue]
    assert [t.instruction for t in dispatched] == ["first queued", "second queued"]  # FIFO
    assert all(t.state == "completed" for t in dispatched)
    assert dispatched[0].created_at <= dispatched[1].created_at


def test_queue_depth_is_read_from_config_and_refuses_overflow(repo):
    cfg_dir = repo.root / ".hive" / "voice-bot"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps({"queue_depth": 2}), encoding="utf-8")
    r = make_runner(repo)
    try:
        blocker = r.submit("CANCEL_ME block", client_request_id="d-0")
        wait_task_state(r, blocker["task_id"], "running")
        r.queue_follow_up("one", task_id=blocker["task_id"])
        r.queue_follow_up("two", task_id=blocker["task_id"])
        with pytest.raises(DelegationError) as exc:
            r.queue_follow_up("three", task_id=blocker["task_id"])
        assert exc.value.code == "queue_full"
        assert len(r.state.queue) == 2  # no entry and no task for the refused follow-up
        assert len(r.state.coding_tasks) == 1
        r.cancel(blocker["task_id"])
    finally:
        r.close()


def test_queue_entries_are_persisted_with_the_contract_fields(runner):
    blocker = runner.submit("CANCEL_ME block", client_request_id="p-0")
    wait_task_state(runner, blocker["task_id"], "running")
    runner.queue_follow_up("persist me", task_id=blocker["task_id"])
    entry = runner.state.queue[0]
    for key in ("queue_id", "session_id", "task_id", "text", "state"):
        assert key in entry
    assert entry["task_id"] is None and entry["text"] == "persist me"
    runner.cancel(blocker["task_id"])


def test_submit_dedupe_applies_to_queued_submits_after_dispatch(runner):
    blocker = runner.submit("CANCEL_ME block", client_request_id="s-0")
    wait_task_state(runner, blocker["task_id"], "running")
    runner.submit("queued work", client_request_id="s-1")
    runner.cancel(blocker["task_id"])
    assert wait_for(lambda: runner.state.queue and runner.state.queue[0]["state"] == "dispatched", timeout=20)
    task_id = runner.state.queue[0]["task_id"]
    runner.wait_idle(timeout=20)
    again = runner.submit("queued work", client_request_id="s-1")
    assert again["status"] == "duplicate"
    assert again["task_id"] == task_id
    assert wait_task_terminal(runner, task_id) == "completed"
