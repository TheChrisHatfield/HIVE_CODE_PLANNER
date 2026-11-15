"""Fail-closed evidence: an ACP update that cannot be recorded fails the task (R8, R22).

Before this fix, `_apply_notification` swallowed any exception from `_on_update`. A write whose
evidence failed to record was then invisible to `_has_unguarded_write`, and the turn reported
`completed`. Integrated test: real submit through the fake ACP child.
"""

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


def test_unrecordable_write_update_fails_task_not_completes(runner: VoiceTaskRunner, monkeypatch):
    def broken_write_record(task, call_id):
        raise RuntimeError("evidence store refused the write")

    monkeypatch.setattr(VoiceTaskRunner, "_record_write_event", staticmethod(broken_write_record))

    out = runner.submit("WRITE_DIFF_UNGUARDED change the add function", client_request_id="dropped-1")
    task_id = out["task_id"]

    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "evidence_error"
        assert any(e["name"] == "update.error" for e in task.events)
        assert not any(e["name"] == "task.completed" for e in task.events)
