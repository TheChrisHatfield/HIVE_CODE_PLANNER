"""T024 / R32 — spoken playback adapter. Typed path is no-audio; Pipecat cancel is independent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import (
    DEFAULT_VOICE_BOT_CONFIG,
    PipecatVoiceAdapter,
    SecondStubAdapter,
    TypedInstructionAdapter,
    VoiceBotConfig,
    VoiceBotError,
    hybrid_speech_path,
    load_voice_bot_config,
    pipecat_cancel_on_interruption,
    speech_adapter,
    voice_bot_config_path,
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


def test_pipecat_adapter_keeps_cancel_on_interruption_false(monkeypatch):
    import hive_planner.voice_tts as tts

    # Stub the synth and the speaker: this test checks the R13 flag, not real audio.
    monkeypatch.setattr(tts, "speak_via_pipecat", lambda text: {"played": True, "sample_rate": 22050})
    assert PipecatVoiceAdapter.cancel_on_interruption is False
    policy = pipecat_cancel_on_interruption()
    if policy is None:
        with pytest.raises(VoiceBotError, match="pipecat_unavailable"):
            PipecatVoiceAdapter().speak("hi")
    else:
        assert policy is False
        spoken = PipecatVoiceAdapter().speak("hi")
        assert spoken["cancel_on_interruption"] is False
        assert spoken["audio"] is True


def test_pipecat_missing_import_is_explicit_error_not_silent_audio(monkeypatch):
    # T034: force the missing-import branch so it is covered on every machine.
    import hive_planner.voice_bot as vb

    monkeypatch.setattr(vb, "_module_installed", lambda name: False)
    assert pipecat_cancel_on_interruption() is None
    with pytest.raises(VoiceBotError, match="pipecat_unavailable"):
        PipecatVoiceAdapter().speak("hi")


def test_pipecat_payload_claims_playback_only_when_audio_started(monkeypatch):
    # Real Pipecat path: a failed playback must raise, never return played/audio true.
    import hive_planner.voice_bot as vb
    import hive_planner.voice_tts as tts

    monkeypatch.setattr(vb, "_module_installed", lambda name: True)
    monkeypatch.setattr(tts, "synthesize_via_pipecat", lambda text: (b"\x00\x01" * 100, 22050))

    def _no_device(pcm, rate):
        raise VoiceBotError("tts_playback_failed: no output device")

    monkeypatch.setattr(tts, "play_pcm16", _no_device)
    with pytest.raises(VoiceBotError, match="tts_playback_failed"):
        PipecatVoiceAdapter().speak("hi")

    played = []
    monkeypatch.setattr(tts, "play_pcm16", lambda pcm, rate: played.append((len(pcm), rate)))
    spoken = PipecatVoiceAdapter().speak("hi")
    assert spoken["played"] is True and spoken["audio"] is True
    assert played == [(200, 22050)]


def test_interrupt_during_synth_does_not_start_playback(monkeypatch):
    # R7: interrupt while SAPI is still rendering must not start the speaker afterward.
    import types

    import hive_planner.voice_tts as tts

    plays: list[int] = []
    fake_sd = types.SimpleNamespace(
        play=lambda *a, **k: plays.append(1),
        stop=lambda *a, **k: None,
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    def _synth(text: str):
        tts.stop_playback()
        return (b"\x00\x01" * 100, 22050)

    monkeypatch.setattr(tts, "synthesize_via_pipecat", _synth)
    with pytest.raises(VoiceBotError, match="tts_playback_failed"):
        tts.speak_via_pipecat("Tests passed.")
    assert plays == []


def test_pipecat_empty_text_plays_nothing(monkeypatch):
    import hive_planner.voice_bot as vb
    import hive_planner.voice_tts as tts

    monkeypatch.setattr(vb, "_module_installed", lambda name: True)
    monkeypatch.setattr(tts, "synthesize_via_pipecat", lambda text: pytest.fail("no synth for empty text"))
    spoken = PipecatVoiceAdapter().speak("   ")
    assert spoken["played"] is False and spoken["audio"] is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows SAPI synthesizer")
def test_pipecat_service_synthesizes_non_silent_audio_without_playback():
    # Real synthesis through the Pipecat TTS service (no speaker). Proves Pipecat produces audio.
    import numpy as np

    from hive_planner.voice_tts import synthesize_via_pipecat

    pcm, rate = synthesize_via_pipecat("Created the file hello dot py.")
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    assert rate > 0
    assert samples.size / rate > 0.5
    assert float(np.abs(samples).max()) > 0.1


def test_runtime_speech_does_not_depend_on_pipecat(tmp_path: Path, monkeypatch):
    # T034 wiring: a real runner turn still records no-audio speech when Pipecat would fail.
    from voice_turn_support import make_repo, make_runner, wait_task_terminal

    def _boom(self, text):
        raise VoiceBotError("pipecat_unavailable")

    monkeypatch.setattr(PipecatVoiceAdapter, "speak", _boom)
    paths = make_repo(tmp_path)
    runner = make_runner(paths)
    try:
        out = runner.submit("hello", client_request_id="speak-no-pipecat")
        wait_task_terminal(runner, out["task_id"])
        events = runner.state.coding_tasks[out["task_id"]].events
        spoken = [e for e in events if e.get("name") == "speech.spoken"]
        assert spoken and all(e.get("payload", {}).get("audio") is False for e in spoken)
    finally:
        runner.close()


def _write_voice_config(paths: RepoPaths, data: dict) -> None:
    path = voice_bot_config_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_audio_enabled_defaults_false_and_loads_from_config(tmp_path: Path):
    # T042 slice 4: absent key is false (no read-site surprise); true loads; non-bool is refused.
    from voice_turn_support import make_repo

    paths = make_repo(tmp_path)
    assert DEFAULT_VOICE_BOT_CONFIG.audio_enabled is False
    assert load_voice_bot_config(paths).audio_enabled is False

    _write_voice_config(paths, {"audio_enabled": True})
    assert load_voice_bot_config(paths).audio_enabled is True

    _write_voice_config(paths, {"audio_enabled": "yes"})
    with pytest.raises(VoiceBotError, match="audio_enabled"):
        load_voice_bot_config(paths)


def test_speech_adapter_follows_audio_enabled_flag(monkeypatch):
    # The flag, not a constant, picks the adapter. Pipecat missing keeps typed even when enabled.
    import hive_planner.voice_bot as vb

    # voice_layer typed: the speech-out choice is tested here; the Moshi wrapper is in test_voice_moshi.py.
    monkeypatch.setattr(vb, "_module_installed", lambda name: True)
    assert isinstance(speech_adapter(VoiceBotConfig(voice_layer="typed", audio_enabled=False)), TypedInstructionAdapter)
    assert isinstance(speech_adapter(VoiceBotConfig(voice_layer="typed", audio_enabled=True)), PipecatVoiceAdapter)

    monkeypatch.setattr(vb, "_module_installed", lambda name: False)
    assert isinstance(speech_adapter(VoiceBotConfig(voice_layer="typed", audio_enabled=True)), TypedInstructionAdapter)


def test_runner_speech_event_uses_audio_enabled_adapter(tmp_path: Path, monkeypatch):
    # Wiring: config audio_enabled true + Pipecat importable routes _say through PipecatVoiceAdapter.
    # Payload still says audio false (T034). With the flag absent, Pipecat is never called.
    import hive_planner.voice_bot as vb
    from voice_turn_support import make_repo, make_runner, wait_task_terminal

    calls: list[str] = []

    def _record(self, text):
        calls.append(text)
        return {"played": False, "audio": False, "text": text, "path": "pipecat"}

    monkeypatch.setattr(vb, "_module_installed", lambda name: True)
    monkeypatch.setattr(PipecatVoiceAdapter, "speak", _record)

    def _run(flag: bool | None, tag: str) -> list[dict]:
        (tmp_path / tag).mkdir()
        paths = make_repo(tmp_path / tag)
        if flag is not None:
            _write_voice_config(paths, {"audio_enabled": flag})
        runner = make_runner(paths)
        try:
            out = runner.submit("hello", client_request_id=f"audio-{tag}")
            wait_task_terminal(runner, out["task_id"])
            events = runner.state.coding_tasks[out["task_id"]].events
            return [e.get("payload", {}) for e in events if e.get("name") == "speech.spoken"]
        finally:
            runner.close()

    on = _run(True, "on")
    assert on and all(p.get("audio") is False and p.get("path") == "pipecat" for p in on)
    assert calls

    calls.clear()
    off = _run(None, "off")
    assert off and all(p.get("path") == "typed" for p in off)
    assert calls == []
