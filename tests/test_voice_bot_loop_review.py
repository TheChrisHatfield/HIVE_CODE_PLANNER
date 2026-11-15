"""Regression tests from the Voice_Bot 4-loop code review (2026-11-10).

Each test pins one bug found in review:
- cancel(): a cancel that ends a task without a live provider must dispatch the next queued
  follow-up. Otherwise the queue stalls with no active task.
- resolve_cursor_agent_cli(): a `--version` that prints only whitespace must not raise IndexError.
- validate_context_snapshot(): a file name containing ".." inside a segment (for example
  `notes..v2.py`) is a legal workspace path, not a traversal. Only a `..` segment is refused.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hive_planner import voice_bot
from hive_planner.voice_bot import (
    ContextSnapshot,
    VoiceBotConfig,
    validate_context_snapshot,
)
from voice_turn_support import make_repo, make_runner


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


def test_cancel_without_live_provider_dispatches_queued_follow_up(repo):
    from hive_planner.voice_bot import CodingTask

    runner = make_runner(repo)
    try:
        # A running task whose provider is gone (no client). Cancelling it ends the task
        # without a provider acknowledgement, which frees the active slot.
        now = "2026-11-10T00:00:00+00:00"
        task = CodingTask(
            task_id="task_loopcancel01",
            voice_session_id=runner.session.session_id,
            context_snapshot_id="ctx_loopcancel01",
            state="running",
            created_at=now,
            updated_at=now,
            client_request_id="loop-cancel-1",
            mode="ask",
            instruction="long task",
            file_path="",
        )
        runner.state.coding_tasks[task.task_id] = task
        runner.state.context_snapshots["ctx_loopcancel01"] = ContextSnapshot(
            workspace_root=str(repo.root),
            file_path="",
            selection_text="",
            document_version=0,
            dirty=False,
            instruction="long task",
            snapshot_id="ctx_loopcancel01",
        )
        runner._active_task_id = task.task_id
        runner._client = None
        runner.state.queue.append({
            "queue_id": "q_loopcancel01",
            "session_id": runner.session.session_id,
            "task_id": None,
            "text": "follow up",
            "state": "queued",
            "file_path": "",
            "mode": "ask",
            "client_request_id": "",
        })

        result = runner.cancel(task.task_id)

        assert result["state"] == "failed"
        entry = runner.state.queue[0]
        assert entry["state"] != "queued", "queued follow-up must dispatch once the slot is free"
        assert entry.get("task_id"), "dispatched follow-up must be bound to a new task"
    finally:
        runner.close()


def test_cli_version_with_only_whitespace_does_not_raise(monkeypatch):
    monkeypatch.setattr(voice_bot.shutil, "which", lambda name: "/fake/agent")

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="\n", stderr="")

    monkeypatch.setattr(voice_bot.subprocess, "run", fake_run)

    info = voice_bot.resolve_cursor_agent_cli()

    assert info["available"] is True
    assert info["version"] is None


def test_file_name_with_double_dot_inside_segment_is_allowed():
    snap = ContextSnapshot(
        workspace_root="/ws",
        file_path="src/notes..v2.py",
        selection_text="",
        document_version=0,
        dirty=False,
        instruction="explain this file",
    )
    validate_context_snapshot(snap, VoiceBotConfig())  # must not raise


def test_parent_segment_is_still_refused():
    snap = ContextSnapshot(
        workspace_root="/ws",
        file_path="src/../../etc/passwd",
        selection_text="",
        document_version=0,
        dirty=False,
        instruction="read this",
    )
    with pytest.raises(voice_bot.VoiceBotError):
        validate_context_snapshot(snap, VoiceBotConfig())
