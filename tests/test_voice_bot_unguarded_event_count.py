"""R22: write.unguarded write_count is write_events, including no-diff writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_task import VoiceTaskRunner
from voice_turn_support import make_repo, make_runner, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_unguarded_event_write_count_uses_write_events_when_diffs_empty(runner: VoiceTaskRunner):
    out = runner.submit(
        "WRITE_NO_DIFF_UNGUARDED change the add function",
        client_request_id="nodiff-count-1",
    )
    task_id = out["task_id"]
    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "unguarded_write"
        assert task.evidence.write_diffs == []
        assert task.evidence.write_events
        events = [e for e in task.events if e.get("name") == "write.unguarded"]
        assert events
        assert events[0]["payload"]["write_count"] == len(task.evidence.write_events)
        assert events[0]["payload"]["write_count"] >= 1
