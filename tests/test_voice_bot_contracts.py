"""T005 — normalized session, task, snapshot, event models; R20 states; R21 limits; client_request_id.

Contract tests run through the runner so the models are exercised as they are persisted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_bot import (
    CODING_TASK_STATES,
    TERMINAL_TASK_STATES,
    CodingTask,
    VoiceBotState,
    load_state,
)
from hive_planner.voice_task import DelegationError, TRANSITIONS
from voice_turn_support import make_repo, make_runner, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_r20_state_enum_is_exact_and_has_no_queued_task_state():
    assert set(CODING_TASK_STATES) == {
        "submitted", "running", "awaiting_approval", "cancel_requested",
        "unknown", "completed", "failed", "cancelled",
    }
    assert "queued" not in CODING_TASK_STATES  # queue entries are not tasks (R5)
    assert set(TERMINAL_TASK_STATES) == {"completed", "failed", "cancelled"}


def test_transition_table_has_no_exit_from_terminal_states():
    for state in TERMINAL_TASK_STATES:
        assert TRANSITIONS[state] == frozenset()


def test_illegal_transition_is_refused(runner):
    out = runner.submit("hello", client_request_id="req-illegal")
    wait_task_terminal(runner, out["task_id"])
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.state == "completed"
    with pytest.raises(DelegationError) as exc:
        runner._transition(task, "running", "should_not_happen")
    assert exc.value.code == "illegal_transition"
    assert task.state == "completed"


def test_submit_records_client_request_id_and_transcript_event(runner):
    out = runner.submit("hello", client_request_id="req-evt")
    wait_task_terminal(runner, out["task_id"])
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.client_request_id == "req-evt"
    names = [e["name"] for e in task.events]
    assert names.index("context.snapshot") < names.index("task.started")
    assert {"transcript.final", "task.completed"} <= set(names)


def test_task_is_bound_to_a_persisted_context_snapshot(runner):
    out = runner.submit("hello", file_path="src/app.py", client_request_id="req-snap")
    wait_task_terminal(runner, out["task_id"])
    task = runner.state.coding_tasks[out["task_id"]]
    snap = runner.state.context_snapshots[task.context_snapshot_id]
    assert snap.file_path == "src/app.py"
    assert snap.instruction == "hello"
    assert snap.cartridge_trace is not None and snap.cartridge_trace.feature_id == "Voice_Bot"


def test_task_round_trips_through_saved_state(runner):
    out = runner.submit("hello", client_request_id="req-rt")
    wait_task_terminal(runner, out["task_id"])
    reloaded = load_state(runner.paths)
    task = reloaded.coding_tasks[out["task_id"]]
    assert task.state == "completed"
    assert task.transitions and task.transitions[0]["to"] == "running"
    assert task.client_request_id == "req-rt"


def test_unknown_stored_state_is_read_as_unknown_not_silently_queued():
    task = CodingTask.from_dict({"task_id": "t1", "state": "queued"})
    assert task.state == "unknown"


def test_state_file_queue_and_dedupe_round_trip():
    state = VoiceBotState(queue=[{"queue_id": "q1", "text": "x", "state": "queued"}],
                          dedupe={"vs|r": {"task_id": None, "queue_id": "q1"}})
    again = VoiceBotState.from_dict(state.to_dict())
    assert again.queue == state.queue
    assert again.dedupe == state.dedupe


def test_instruction_limit_is_refused_without_truncation(repo):
    r = make_runner(repo)
    try:
        with pytest.raises(DelegationError) as exc:
            r.submit("x" * 4001, client_request_id="req-big")
        assert exc.value.code == "instruction_too_long"
        assert r.state.coding_tasks == {}
    finally:
        r.close()


def _extension_editor(*, dirty: bool) -> dict:
    """Shape matches the extension core.js snapshot keys (T007/T008)."""
    return {
        "file": "src/app.py",
        "reason": "",
        "selection": {"text": "x = 1", "truncated": False},
        "file_content": "x = 1\n",
        "document_version": 3,
        "dirty": dirty,
        "diagnostics": [{"severity": "error", "message": "boom"}],
        "file_truncated": False,
        "diagnostics_truncated": False,
    }


def test_map_editor_snapshot_clean_and_dirty_extension_shapes():
    from hive_planner.voice_bot import map_editor_snapshot

    clean = map_editor_snapshot(
        _extension_editor(dirty=False), instruction="fix it", workspace_root="/ws"
    )
    assert clean.workspace_root == "/ws"
    assert clean.file_path == "src/app.py"
    assert clean.selection_text == "x = 1"
    assert clean.file_content == "x = 1\n"
    assert clean.document_version == 3
    assert clean.dirty is False
    assert clean.instruction == "fix it"
    assert clean.diagnostics == ["error: boom"]
    assert clean.truncated is False
    assert clean.excluded == ""

    dirty = map_editor_snapshot(
        _extension_editor(dirty=True), instruction="fix it", workspace_root="/ws"
    )
    assert dirty.dirty is True
    assert dirty.excluded == "unsaved"
    assert dirty.selection_text == ""
    assert dirty.file_content == ""
    # Metadata survives exclusion so the task can still be bound to the file.
    assert dirty.file_path == "src/app.py"
    assert dirty.document_version == 3
