"""Regression tests from the Voice_Bot 4-loop code review (2026-11-10 cascade).

Each test pins one confirmed bug:
- C1 (R7/R20): `_finish` after cancel has already settled a disconnected in-flight
  prompt must not raise illegal_transition.
- C2 (R9): a provider-lost timer must not mutate state after `close()`.
- C3 (R22): a stale live buffer blocks submit before a task is created.
- C5 (R23): workspace bind uses the same realpath+normcase rule as the bridge.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hive_planner.voice_bot import CodingTask, same_workspace
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


def test_finish_after_terminal_cancel_does_not_raise(runner):
    out = runner.submit("explain add", client_request_id="c1-term")
    wait_task_terminal(runner, out["task_id"])
    runner._finish(out["task_id"], ("disconnected", "already done"))
    assert runner.state.coding_tasks[out["task_id"]].state in ("completed", "failed", "cancelled")


def test_cancel_while_disconnected_inflight_prompt_settles(runner):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="c1-race")
    wait_task_state(runner, out["task_id"], "awaiting_approval")
    client = runner._client
    assert client is not None
    client.terminate()
    assert wait_for(lambda: not client.is_connected())
    result = runner.cancel(out["task_id"])
    assert result["state"] in ("failed", "cancel_requested")
    wait_task_terminal(runner, out["task_id"])
    runner._finish(out["task_id"], ("disconnected", "late"))
    follow = runner.submit("explain add", client_request_id="c1-follow")
    wait_task_terminal(runner, follow["task_id"])


def test_close_stops_provider_lost_timer_from_writing(repo):
    r = make_runner(repo)
    now = "2026-11-10T00:00:00+00:00"
    task = CodingTask(
        task_id="task_closed00001",
        voice_session_id=r.session.session_id,
        context_snapshot_id="ctx_closed00001",
        state="unknown",
        created_at=now,
        updated_at=now,
        client_request_id="c2-close",
        mode="ask",
        instruction="older task",
        file_path="",
    )
    r.state.coding_tasks[task.task_id] = task
    r._settle(task)
    timer = r._provider_lost_timers[task.task_id]
    r.close()
    timer.join(timeout=2)
    assert r._closed
    assert task.state == "unknown", "timer must not fail the task after close()"
    r._provider_lost(task.task_id)
    assert task.state == "unknown"


def test_stale_buffer_blocks_submit_before_a_task_exists(runner):
    runner.set_live_buffer(lambda _path: (9, True))
    with pytest.raises(DelegationError) as exc:
        runner.submit(
            "explain add",
            client_request_id="c3-stale",
            file_path="src/app.py",
            document_version=1,
            dirty=False,
        )
    assert exc.value.code == "stale"
    assert exc.value.spoken
    assert runner.state.coding_tasks == {}
    assert runner.state.queue == []


def test_matching_live_buffer_still_submits(runner):
    runner.set_live_buffer(lambda _path: (4, False))
    out = runner.submit(
        "explain add",
        client_request_id="c3-ok",
        file_path="src/app.py",
        document_version=4,
        dirty=False,
    )
    assert out["task_id"]
    wait_task_terminal(runner, out["task_id"])


def test_same_workspace_folds_realpath(repo):
    dotted = str(Path(repo.root) / ".")
    assert same_workspace(dotted, repo.root)


@pytest.mark.skipif(os.name != "nt", reason="path case folding is a Windows rule")
def test_bind_workspace_accepts_case_folded_root(runner, repo):
    folded = str(repo.root).swapcase()
    if folded == str(repo.root):
        pytest.skip("temp path has no letters to fold")
    named = runner.invoke_controller_tool(
        "submit_coding_task",
        workspace=folded,
        instruction="hello",
        client_request_id="c5-case",
    )
    assert named["task_id"]
    wait_task_terminal(runner, named["task_id"])
