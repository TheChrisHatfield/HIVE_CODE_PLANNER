"""R17 gap fix: provider tool titles are sanitized before approval speech and task status.

The raw title stays in `task.events` / `raw_events`. Spoken text and `task_status` carry only the
sanitized label. Exact-match replies still work with that label (T008).
"""

from __future__ import annotations

from pathlib import Path

from hive_planner.voice_task import (
    APPROVAL_ACTION_MAX_CHARS,
    DEFAULT_APPROVAL_ACTION,
    _safe_action_label,
)
from voice_turn_support import make_repo, make_runner, wait_task_state, wait_task_terminal


def test_safe_action_label_strips_marks_and_collapses_whitespace():
    assert _safe_action_label("Edit `src/app.py`\n**now**") == "Edit src/app.py now"


def test_safe_action_label_replaces_control_characters():
    assert _safe_action_label("delete\x00\x1b build\tdir") == "delete build dir"


def test_safe_action_label_caps_length():
    label = _safe_action_label("x" * 500)
    assert len(label) <= APPROVAL_ACTION_MAX_CHARS
    assert label.endswith("...")


def test_safe_action_label_empty_falls_back_to_default():
    assert _safe_action_label("") == DEFAULT_APPROVAL_ACTION
    assert _safe_action_label("  `` ** ") == DEFAULT_APPROVAL_ACTION
    assert _safe_action_label(None) == DEFAULT_APPROVAL_ACTION


def test_approval_speech_and_status_carry_only_the_sanitized_label(tmp_path: Path):
    repo = make_repo(tmp_path)
    runner = make_runner(repo)
    try:
        out = runner.submit("NEEDS_APPROVAL:edit `src/app.py` now", client_request_id="lbl-1")
        task_id = out["task_id"]
        wait_task_state(runner, task_id, "awaiting_approval")
        task = runner.state.coding_tasks[task_id]

        assert task.approval["action"] == "edit src/app.py now"
        assert "`" not in task.evidence.spoken_update
        assert task.evidence.spoken_update == "Approval needed to edit src/app.py now. Say approve or deny edit src/app.py now."

        status = runner.task_status(task_id)
        assert status["approval"]["action"] == "edit src/app.py now"
        assert "`" not in str(status)

        reply = runner.reply_approval("approve edit src/app.py now")
        assert reply["status"] == "approved"
        assert wait_task_terminal(runner, task_id) == "completed"
    finally:
        runner.close()
