"""SC-010 — spoken updates cite task evidence (`task.*` events), never raw provider tokens.

Drives real submissions through the stdio fixture provider and checks the persisted
`task.events` trail and `evidence` record:
  - every `speech.spoken` event is preceded by a recorded lifecycle event
    (`task.started`, `task.progress`, `task.awaiting_approval`, `task.completed`, `task.failed`);
  - the spoken text never carries the raw provider chunk ("turn N in <session>: ...");
    that text lives only in `written_result`;
  - the spoken outcome for a completed task names the test status from recorded evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_task import VoiceTaskRunner
from voice_turn_support import make_repo, make_runner, wait_task_terminal

CITABLE_BEFORE_SPEECH = {
    "task.started",
    "task.progress",
    "task.awaiting_approval",
    "task.completed",
    "task.failed",
}
RAW_PROVIDER_MARKER = "turn "  # fixture chunks read "turn N in <session>: <prompt>"


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def _events(runner: VoiceTaskRunner, task_id: str) -> list[dict]:
    return list(runner.state.coding_tasks[task_id].events)


def _assert_speech_cites_evidence(events: list[dict]) -> None:
    speech_seen = 0
    for idx, evt in enumerate(events):
        if evt["name"] != "speech.spoken":
            continue
        speech_seen += 1
        assert idx > 0, "speech emitted with no preceding lifecycle event"
        prev = events[idx - 1]["name"]
        assert prev in CITABLE_BEFORE_SPEECH, (
            f"speech.spoken at {idx} follows {prev!r}, not a task evidence event"
        )
    assert speech_seen > 0


def test_completed_turn_speech_cites_task_events_not_raw_tokens(runner: VoiceTaskRunner):
    sub = runner.submit("hello", client_request_id="sc010-complete")
    assert wait_task_terminal(runner, sub["task_id"]) == "completed"
    task = runner.state.coding_tasks[sub["task_id"]]
    events = _events(runner, sub["task_id"])

    _assert_speech_cites_evidence(events)

    # Raw provider tokens are recorded in written_result only.
    assert RAW_PROVIDER_MARKER in task.evidence.written_result
    assert RAW_PROVIDER_MARKER not in task.evidence.spoken_update
    for evt in events:
        if evt["name"] == "speech.spoken":
            assert RAW_PROVIDER_MARKER not in evt["payload"].get("text", "")

    # The final spoken outcome is the completion summary, backed by task.completed.
    assert any(e["name"] == "task.completed" for e in events)
    assert "Task completed." in task.evidence.spoken_update


def test_failed_turn_speech_cites_task_failed_event(runner: VoiceTaskRunner):
    sub = runner.submit("REFUSE", client_request_id="sc010-failed")
    assert wait_task_terminal(runner, sub["task_id"]) == "failed"
    task = runner.state.coding_tasks[sub["task_id"]]
    events = _events(runner, sub["task_id"])

    _assert_speech_cites_evidence(events)
    assert any(e["name"] == "task.failed" for e in events)
    assert "Task failed" in task.evidence.spoken_update
    assert RAW_PROVIDER_MARKER not in task.evidence.spoken_update
