"""T040 / P2-4 — R24 budgets are checked at runtime, not only by helper assertions.

Integrated path: real VoiceTaskRunner submit -> ACP child -> task events. The clock is a
deterministic counter (1 s per event stamp) so the measured elapsed time is stable on any machine.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from hive_planner import voice_task
from hive_planner.voice_bot import voice_bot_config_path
from voice_turn_support import make_repo, make_runner, wait_task_terminal


@pytest.fixture
def fake_clock(monkeypatch):
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 11, 12, tzinfo=timezone.utc)
    ticks = itertools.count()
    monkeypatch.setattr(voice_task, "_now", lambda: (base + timedelta(seconds=next(ticks))).isoformat())


def _run_with_config(tmp_path: Path, config: dict) -> list[dict]:
    repo = make_repo(tmp_path)
    path = voice_bot_config_path(repo)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(config), encoding="utf-8")
    r = make_runner(repo)
    try:
        result = r.submit("hello", client_request_id="r24-1")
        wait_task_terminal(r, result["task_id"])
        return list(r.state.coding_tasks[result["task_id"]].events)
    finally:
        r.close()


def _over_budget(events: list[dict]) -> list[dict]:
    return [e["payload"] for e in events if e.get("name") == "r24.over_budget"]


def test_over_budget_task_start_is_logged_at_runtime(tmp_path: Path, fake_clock) -> None:
    events = _run_with_config(tmp_path, {"latency_target_ms": 1})
    kinds = {p["kind"] for p in _over_budget(events)}
    assert "task_started" in kinds
    row = next(p for p in _over_budget(events) if p["kind"] == "task_started")
    assert row["target_ms"] == 1
    assert row["elapsed_ms"] > 1


def test_loose_budget_is_not_logged(tmp_path: Path, fake_clock) -> None:
    events = _run_with_config(
        tmp_path,
        {"latency_target_ms": 10_000_000, "first_spoken_update_target_ms": 10_000_000},
    )
    assert _over_budget(events) == []


def test_first_speech_budget_is_logged_once(tmp_path: Path, fake_clock) -> None:
    events = _run_with_config(
        tmp_path,
        {"latency_target_ms": 10_000_000, "first_spoken_update_target_ms": 1},
    )
    rows = [p for p in _over_budget(events) if p["kind"] == "first_speech"]
    assert len(rows) == 1
    assert rows[0]["target_ms"] == 1


def test_missing_target_is_not_checked(tmp_path: Path, fake_clock) -> None:
    events = _run_with_config(
        tmp_path,
        {"latency_target_ms": None, "first_spoken_update_target_ms": None},
    )
    assert _over_budget(events) == []
