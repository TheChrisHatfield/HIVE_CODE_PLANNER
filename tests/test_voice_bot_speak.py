"""T024 / R32 — spoken playback adapter. Typed path is no-audio; Pipecat cancel is independent."""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_bot import (
    PipecatVoiceAdapter,
    SecondStubAdapter,
    TypedInstructionAdapter,
    VoiceBotError,
    hybrid_speech_path,
    pipecat_cancel_on_interruption,
)


def test_runner_spoken_event_records_no_audio(tmp_path: Path):
    from voice_turn_support import make_repo, make_runner, wait_task_terminal

    paths = make_repo(tmp_path)
    runner = make_runner(paths)
    try:
        out = runner.submit("hello", client_request_id="speak-evt")
        wait_task_terminal(runner, out["task_id"])
        events = runner.state.coding_tasks[out["task_id"]].events
        spoken = [e for e in events if e.get("name") == "speech.spoken"]
        assert spoken
        assert spoken[-1].get("payload", {}).get("audio") is False
    finally:
        runner.close()


def test_typed_speak_records_text_and_plays_no_audio():
    spoken = TypedInstructionAdapter().speak("Task accepted, running.")
    assert spoken["audio"] is False
    assert spoken["played"] is False
    assert spoken["path"] == "typed"
    assert spoken["text"] == "Task accepted, running."


def test_stub_adapter_speak_is_also_silent():
    spoken = SecondStubAdapter().speak("hi")
    assert spoken["audio"] is False
    assert spoken["played"] is False


def test_speech_path_stays_typed_until_stt_is_pinned():
    assert hybrid_speech_path() == "typed_instruction"


def test_pipecat_adapter_keeps_cancel_on_interruption_false():
    assert PipecatVoiceAdapter.cancel_on_interruption is False
    policy = pipecat_cancel_on_interruption()
    if policy is None:
        with pytest.raises(VoiceBotError, match="pipecat_unavailable"):
            PipecatVoiceAdapter().speak("hi")
    else:
        assert policy is False
        spoken = PipecatVoiceAdapter().speak("hi")
        assert spoken["cancel_on_interruption"] is False
        assert spoken["audio"] is False
