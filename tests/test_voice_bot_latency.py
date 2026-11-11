"""T018 — R24 latency check is driven by the config object (acceptance 20)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_bot import VoiceBotConfig, event_delta_ms, latency_meets_target, load_voice_bot_config
from voice_turn_support import make_repo, make_runner, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


def test_latency_target_from_config_changes_the_checked_result(repo):
    out_dir = repo.root / ".hive" / "voice-bot"
    out_dir.mkdir(parents=True)
    (out_dir / "config.json").write_text('{"latency_target_ms": 1}', encoding="utf-8")
    tight = load_voice_bot_config(repo)
    (out_dir / "config.json").write_text('{"latency_target_ms": 60000}', encoding="utf-8")
    loose = load_voice_bot_config(repo)
    r = make_runner(repo)
    try:
        result = r.submit("hello", client_request_id="lat-1")
        wait_task_terminal(r, result["task_id"])
        events = r.state.coding_tasks[result["task_id"]].events
        elapsed = event_delta_ms(events, "transcript.final", "task.started")
        assert elapsed is not None
        sample_ms = 10
        assert latency_meets_target(sample_ms, tight.latency_target_ms) is False
        assert latency_meets_target(sample_ms, loose.latency_target_ms) is True
        assert latency_meets_target(elapsed, VoiceBotConfig().latency_target_ms) is True
    finally:
        r.close()
