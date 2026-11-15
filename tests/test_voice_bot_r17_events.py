"""AC 13 / SC-010 — all five R17 task event kinds reach `task.events` through the runner.

Drives one real submission per lifecycle branch through the stdio fixture provider:
  - start + progress + completion (default turn: agent chunk, end_turn)
  - approval wait (NEEDS_APPROVAL, answered through reply_approval)
  - failure (REFUSE -> stopReason refusal -> failed)
Each event is read from the persisted `task.events` list, not from a mock.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_task import VoiceTaskRunner
from voice_turn_support import make_repo, make_runner, wait_task_state, wait_task_terminal

R17_KINDS = {
    "task.started",
    "task.progress",
    "task.awaiting_approval",
    "task.completed",
    "task.failed",
}


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def _names(runner: VoiceTaskRunner, task_id: str) -> list[str]:
    return [e["name"] for e in runner.state.coding_tasks[task_id].events]


def test_all_five_r17_event_kinds_reach_task_events(runner: VoiceTaskRunner):
    # 1. start, progress, completion
    done = runner.submit("hello", client_request_id="r17-complete")
    assert wait_task_terminal(runner, done["task_id"]) == "completed"
    done_names = _names(runner, done["task_id"])
    assert "task.started" in done_names
    assert "task.progress" in done_names
    assert "task.completed" in done_names
    assert "task.failed" not in done_names

    # 2. approval wait, then resolved through the voice reply path
    gated = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="r17-approval")
    wait_task_state(runner, gated["task_id"], "awaiting_approval")
    gated_names = _names(runner, gated["task_id"])
    assert "task.awaiting_approval" in gated_names
    # Two events share this name: the transition mirror (reason only) and the explicit
    # approval event (request_id + kind). The explicit one carries the R17 payload.
    approval_evt = next(
        e for e in runner.state.coding_tasks[gated["task_id"]].events
        if e["name"] == "task.awaiting_approval" and "kind" in e["payload"]
    )
    assert approval_evt["payload"]["kind"] == "write_or_command"
    assert approval_evt["payload"]["request_id"]

    runner.reply_approval("approve edit src/app.py")
    assert wait_task_terminal(runner, gated["task_id"]) == "completed"
    assert "task.completed" in _names(runner, gated["task_id"])

    # 3. failure (provider refusal ends the turn as failed)
    failed = runner.submit("REFUSE", client_request_id="r17-failure")
    assert wait_task_terminal(runner, failed["task_id"]) == "failed"
    failed_names = _names(runner, failed["task_id"])
    assert "task.failed" in failed_names
    assert "task.completed" not in failed_names

    # Union across the three lifecycle branches covers every R17 kind exactly.
    seen = set(done_names) | set(gated_names) | set(failed_names)
    assert R17_KINDS <= seen, f"missing R17 kinds: {sorted(R17_KINDS - seen)}"
