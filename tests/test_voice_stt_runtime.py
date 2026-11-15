"""T042 slice 2: runtime STT entry (`submit_spoken`) and an honest `hybrid_speech_path`.

The fake adapter is injected, so these tests do not need faster-whisper or the model.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import hive_planner.voice_stt as voice_stt
from hive_planner.config import RepoPaths
from hive_planner.voice_bot import (
    VoiceBotConfig,
    VoiceBotError,
    hybrid_speech_path,
    load_voice_bot_config,
    voice_bot_config_path,
)
from hive_planner.voice_stt import SttError
from hive_planner.voice_task import DelegationError, VoiceTaskRunner


class FakeAdapter:
    def __init__(self, text: str = "explain add", error: str | None = None) -> None:
        self.text = text
        self.error = error
        self.bytes_calls: list[bytes] = []
        self.file_calls: list[Path] = []

    def transcribe(self, audio: bytes) -> str:
        self.bytes_calls.append(audio)
        if self.error:
            raise SttError(self.error)
        return self.text

    def transcribe_file(self, wav_path: Path) -> str:
        self.file_calls.append(Path(wav_path))
        if self.error:
            raise SttError(self.error)
        return self.text


def _write_config(root: Path, data: dict) -> RepoPaths:
    paths = RepoPaths(root=root)
    cfg = voice_bot_config_path(paths)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    # These tests exercise STT in isolation. The default voice_layer is moshi, which gates
    # spoken submits on a live Moshi handshake (T053). That gate is tested in test_voice_moshi.py.
    data = {"voice_layer": "typed", **data}
    cfg.write_text(json.dumps(data), encoding="utf-8")
    return paths


def _no_provider(handler):
    raise AssertionError("STT tests must not start a provider")


@pytest.fixture
def stt_runner(tmp_path: Path, monkeypatch):
    """Runner with stt_provider set. `_launch` is stubbed so no ACP child starts."""
    paths = _write_config(tmp_path, {"stt_provider": "faster-whisper"})
    (tmp_path / "utt.wav").write_bytes(b"RIFF-fake")
    launched: list[str] = []
    monkeypatch.setattr(VoiceTaskRunner, "_launch", lambda self, task_id: launched.append(task_id))
    runner = VoiceTaskRunner(paths, "Voice_Bot", client_factory=_no_provider, request_timeout=5)
    runner.launched = launched  # type: ignore[attr-defined]
    yield runner
    runner.close()


def test_submit_spoken_refused_when_stt_provider_is_null(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(VoiceTaskRunner, "_launch", lambda self, task_id: None)
    runner = VoiceTaskRunner(RepoPaths(root=tmp_path), "Voice_Bot", client_factory=_no_provider, request_timeout=5)
    try:
        with pytest.raises(DelegationError) as exc:
            runner.submit_spoken(audio=b"x", client_request_id="s-off", stt_adapter=FakeAdapter())
        assert exc.value.code == "stt_not_configured"
        assert runner.state.coding_tasks == {}
    finally:
        runner.close()


def test_audio_bytes_are_transcribed_and_submitted(stt_runner: VoiceTaskRunner):
    adapter = FakeAdapter(text="explain add")
    out = stt_runner.submit_spoken(audio=b"RIFF", client_request_id="s-audio", stt_adapter=adapter)
    assert adapter.bytes_calls == [b"RIFF"]
    assert out["transcript"] == "explain add"
    task = stt_runner.state.coding_tasks[out["task_id"]]
    assert task.instruction == "explain add"
    assert stt_runner.launched == [out["task_id"]]


def test_submit_spoken_keeps_editor_snapshot(stt_runner: VoiceTaskRunner, tmp_path: Path):
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "app.py").write_text("return 1\n", encoding="utf-8")
    out = stt_runner.submit_spoken(
        audio=b"RIFF",
        client_request_id="s-snap",
        stt_adapter=FakeAdapter(text="explain add"),
        editor_snapshot={
            "file": "src/app.py",
            "document_version": 3,
            "dirty": False,
            "selection": {"text": "picked"},
        },
    )
    task = stt_runner.state.coding_tasks[out["task_id"]]
    snap = stt_runner.state.context_snapshots[task.context_snapshot_id]
    assert task.file_path == "src/app.py"
    assert snap.document_version == 3
    assert snap.dirty is False
    assert snap.selection_text == "picked"


def test_wav_path_inside_workspace_is_transcribed_from_file(stt_runner: VoiceTaskRunner, tmp_path: Path):
    adapter = FakeAdapter(text="explain add")
    out = stt_runner.submit_spoken(wav_path="utt.wav", client_request_id="s-file", stt_adapter=adapter)
    assert adapter.file_calls == [(tmp_path / "utt.wav").resolve()]
    assert out["transcript"] == "explain add"
    assert stt_runner.state.coding_tasks[out["task_id"]].instruction == "explain add"


def test_wav_path_outside_workspace_is_refused_before_transcribing(stt_runner: VoiceTaskRunner, tmp_path: Path):
    adapter = FakeAdapter()
    with pytest.raises(DelegationError) as exc:
        stt_runner.submit_spoken(wav_path="../escape.wav", client_request_id="s-esc", stt_adapter=adapter)
    assert exc.value.code in ("path_outside_workspace", "file_not_found")
    assert adapter.file_calls == []
    assert stt_runner.state.coding_tasks == {}


def test_exactly_one_audio_input_is_required(stt_runner: VoiceTaskRunner):
    with pytest.raises(DelegationError) as neither:
        stt_runner.submit_spoken(client_request_id="s-none", stt_adapter=FakeAdapter())
    assert neither.value.code == "stt_input_required"
    with pytest.raises(DelegationError) as both:
        stt_runner.submit_spoken(audio=b"x", wav_path="utt.wav", client_request_id="s-both", stt_adapter=FakeAdapter())
    assert both.value.code == "stt_input_required"


def test_empty_transcript_is_stt_failed_and_creates_no_task(stt_runner: VoiceTaskRunner):
    with pytest.raises(DelegationError) as exc:
        stt_runner.submit_spoken(audio=b"RIFF", client_request_id="s-empty", stt_adapter=FakeAdapter(text="   "))
    assert exc.value.code == "stt_failed"
    assert stt_runner.state.coding_tasks == {}


def test_adapter_failure_is_loud_and_creates_no_task(stt_runner: VoiceTaskRunner):
    with pytest.raises(DelegationError) as exc:
        stt_runner.submit_spoken(audio=b"x", client_request_id="s-fail", stt_adapter=FakeAdapter(error="stt_failed"))
    assert exc.value.code == "stt_failed"
    assert stt_runner.state.coding_tasks == {}


def test_missing_model_with_no_adapter_is_refused(stt_runner: VoiceTaskRunner, monkeypatch):
    monkeypatch.setattr(voice_stt, "resolve_pinned_model_dir", lambda: None)
    monkeypatch.setattr("hive_planner.voice_task.resolve_pinned_model_dir", lambda: None)
    with pytest.raises(DelegationError) as exc:
        stt_runner.submit_spoken(audio=b"x", client_request_id="s-nomodel")
    assert exc.value.code == "stt_model_missing"
    assert stt_runner.state.coding_tasks == {}


def test_missing_client_request_id_is_refused(stt_runner: VoiceTaskRunner):
    with pytest.raises(DelegationError) as exc:
        stt_runner.submit_spoken(audio=b"x", stt_adapter=FakeAdapter())
    assert exc.value.code == "missing_client_request_id"


def test_speech_path_flips_from_config_flag_and_model_availability(tmp_path: Path, monkeypatch):
    assert hybrid_speech_path(VoiceBotConfig(stt_provider=None)) == "typed_instruction"

    paths = _write_config(tmp_path, {"stt_provider": "faster-whisper"})
    cfg = load_voice_bot_config(paths)

    monkeypatch.setattr(voice_stt, "resolve_pinned_model_dir", lambda: None)
    assert hybrid_speech_path(cfg) == "typed_instruction"  # flag set, but nothing can transcribe

    monkeypatch.setattr(voice_stt, "resolve_pinned_model_dir", lambda: tmp_path / "model")
    assert hybrid_speech_path(cfg) == "stt"


def test_unpinned_provider_still_rejected(tmp_path: Path):
    paths = _write_config(tmp_path, {"stt_provider": "moshi"})
    with pytest.raises(VoiceBotError, match="stt_provider"):
        load_voice_bot_config(paths)
