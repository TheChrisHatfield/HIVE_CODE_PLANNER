"""Bug hunt (voice-bot scope): a retried submit must return the existing task, not fail (R29).

Drives the real path: `VoiceBridge` over loopback HTTP, then `run_turn_via_bridge` as the CLI
does. The first submit runs a task to completion; the retry carries the same
`client_request_id`. The duplicate reply must still bind the task's `context_snapshot_id` so
the follow-up `GET /v1/task` is accepted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_bridge import VoiceBridge, run_turn_via_bridge
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


@pytest.fixture
def bridge(runner: VoiceTaskRunner):
    b = VoiceBridge(runner)
    b.start()
    yield b
    b.close()


def test_retry_through_bridge_returns_existing_task_not_an_error(repo, runner, bridge):
    first = run_turn_via_bridge(
        repo, instruction="RUN_TESTS_PASS explain add", mode="ask", file_path="",
        client_request_id="rt-retry-1", timeout=10.0,
    )
    assert first["task_id"]
    wait_task_terminal(runner, first["task_id"])

    retry = run_turn_via_bridge(
        repo, instruction="RUN_TESTS_PASS explain add", mode="ask", file_path="",
        client_request_id="rt-retry-1", timeout=10.0,
    )

    assert retry["task_id"] == first["task_id"]
    assert retry["state"] == first["state"]
    assert len(runner.state.coding_tasks) == 1
