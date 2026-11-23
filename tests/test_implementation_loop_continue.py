"""CodeSpec stop-hook ping on checker fail or stall."""

from __future__ import annotations

import json
from pathlib import Path

from hive_planner.implementation_loop import (
    CODESPEC_NEXT_TASK_FOLLOWUP,
    LoopState,
    PACK_1,
    _save_state,
    codespec_followup_message,
    codespec_should_followup,
    write_codespec_continue,
    _loop_dir,
    _mark_check_started,
    _mark_check_finished,
)


def _running(root: Path) -> None:
    _loop_dir(root).mkdir(parents=True, exist_ok=True)
    _save_state(
        root,
        LoopState(
            feature="PersonaPlex_migrate",
            pack=PACK_1,
            branch="main",
            current_task="PP-T12",
            round_trips=1,
            status="running",
        ),
    )


def test_no_followup_when_idle(tmp_path: Path) -> None:
    assert codespec_should_followup(tmp_path) is False


def test_followup_when_continue_active(tmp_path: Path) -> None:
    _running(tmp_path)
    write_codespec_continue(tmp_path, active=True, reason="checker-fail")
    assert codespec_should_followup(tmp_path) is True
    write_codespec_continue(tmp_path, active=False, reason="checker-pass")
    assert codespec_should_followup(tmp_path) is False


def test_followup_when_check_pid_present(tmp_path: Path) -> None:
    _running(tmp_path)
    _mark_check_started(tmp_path)
    assert codespec_should_followup(tmp_path) is True
    _mark_check_finished(tmp_path)
    assert codespec_should_followup(tmp_path) is False


def test_continue_json_shape(tmp_path: Path) -> None:
    write_codespec_continue(tmp_path, active=True, reason="checker-fail")
    raw = json.loads((_loop_dir(tmp_path) / "continue.json").read_text(encoding="utf-8"))
    assert raw["active"] is True
    assert raw["reason"] == "checker-fail"
    assert raw["pause_seconds"] == 9


def test_followup_message_next_task(tmp_path: Path) -> None:
    _running(tmp_path)
    write_codespec_continue(tmp_path, active=True, reason="next-task", pause_seconds=0)
    assert codespec_should_followup(tmp_path) is True
    assert codespec_followup_message(tmp_path) == CODESPEC_NEXT_TASK_FOLLOWUP
    raw = json.loads((_loop_dir(tmp_path) / "continue.json").read_text(encoding="utf-8"))
    assert raw["pause_seconds"] == 0
