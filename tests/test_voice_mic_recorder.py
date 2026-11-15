"""Tests for the launcher mic recorder (T042 slice 5d). Fake sounddevice, no real microphone."""

from __future__ import annotations

import io
import json
import wave
from pathlib import Path

import pytest

from hive_planner.launcher import voice_mic_recorder as vmr
from hive_planner.launcher.voice_mic_recorder import WavMicRecorder
from hive_planner.launcher.voice_panel_controller import VoicePanelController
from hive_planner.voice_stt import STT_PIN_PROVIDER


class _FakeStream:
    """Mimics sd.InputStream: start() pushes two int16 blocks through the callback."""

    instances: list[_FakeStream] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.closed = False
        _FakeStream.instances.append(self)

    def start(self) -> None:
        self.started = True
        block = (b"\x01\x00" * 160)  # 160 mono int16 samples
        self.kwargs["callback"](block, 160, None, None)
        self.kwargs["callback"](block, 160, None, None)

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


class _FakeSoundDevice:
    InputStream = _FakeStream


@pytest.fixture(autouse=True)
def _reset_streams():
    _FakeStream.instances.clear()
    yield


def _read_wav(data: bytes) -> tuple[int, int, int, int]:
    with wave.open(io.BytesIO(data), "rb") as wav:
        return wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()


def test_recorder_start_stop_returns_16khz_mono_wav() -> None:
    rec = WavMicRecorder(lambda: None, sounddevice=_FakeSoundDevice)
    rec.start()
    audio = rec.stop()
    channels, width, rate, frames = _read_wav(audio)
    assert (channels, width, rate) == (1, 2, 16000)
    assert frames == 320
    stream = _FakeStream.instances[0]
    assert stream.kwargs["samplerate"] == 16000
    assert stream.kwargs["dtype"] == "int16"
    assert stream.kwargs["device"] is None
    assert stream.stopped and stream.closed


def test_recorder_passes_saved_input_device_name() -> None:
    rec = WavMicRecorder(lambda: "  USB Mic  ", sounddevice=_FakeSoundDevice)
    rec.start()
    assert _FakeStream.instances[0].kwargs["device"] == "USB Mic"
    rec.stop()


def test_recorder_stop_without_start_returns_empty_wav() -> None:
    rec = WavMicRecorder(sounddevice=_FakeSoundDevice)
    _channels, _width, _rate, frames = _read_wav(rec.stop())
    assert frames == 0


def test_recorder_open_failure_is_oserror() -> None:
    class _Broken:
        class InputStream:
            def __init__(self, **_kwargs) -> None:
                raise ValueError("No input device matching 'nope'")

    rec = WavMicRecorder(lambda: "nope", sounddevice=_Broken)
    with pytest.raises(OSError, match="could not open microphone nope"):
        rec.start()


def test_missing_sounddevice_is_oserror(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def _no_sd(name, *args, **kwargs):
        if name == "sounddevice":
            raise ImportError("no module named sounddevice")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_sd)
    rec = WavMicRecorder(lambda: None)
    with pytest.raises(OSError, match="sounddevice is not installed"):
        rec.start()


def test_controller_with_real_recorder_mic_start_then_stop_submits_wav(tmp_path: Path, monkeypatch) -> None:
    """Integration: panel mic start/stop -> WavMicRecorder -> workspace WAV -> POST /v1/submit/spoken."""
    (tmp_path / ".hive" / "voice-bot").mkdir(parents=True)
    (tmp_path / ".hive" / "voice-bot" / "config.json").write_text(
            json.dumps({"stt_provider": STT_PIN_PROVIDER, "voice_layer": "typed"}), encoding="utf-8"
    )
    posts: list[tuple[str, dict]] = []

    def _post(route: str, body: dict) -> tuple[int, dict]:
        posts.append((route, body))
        return 200, {}

    rec = WavMicRecorder(lambda: None, sounddevice=_FakeSoundDevice)
    ctrl = VoicePanelController(lambda: tmp_path, post=_post, recorder=rec)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)

    assert ctrl.on_mic(True) is None
    assert ctrl.mic_active is True
    assert ctrl.on_mic(False) is None

    assert [route for route, _ in posts] == ["/v1/submit/spoken"]
    body = posts[0][1]
    wav_file = (tmp_path / body["wav_path"]).resolve()
    assert wav_file.is_relative_to(tmp_path.resolve())
    assert _read_wav(wav_file.read_bytes())[2] == 16000


def test_controller_mic_start_refused_when_sounddevice_missing(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".hive" / "voice-bot").mkdir(parents=True)
    (tmp_path / ".hive" / "voice-bot" / "config.json").write_text(
            json.dumps({"stt_provider": STT_PIN_PROVIDER, "voice_layer": "typed"}), encoding="utf-8"
    )
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", None)  # makes import raise ImportError
    ctrl = VoicePanelController(lambda: tmp_path, post=lambda *_: (200, {}), recorder=WavMicRecorder(lambda: None))
    refusal = ctrl.on_mic(True)
    assert refusal is not None and "could not start recording" in refusal
    assert ctrl.mic_active is False


def test_module_exports_sample_contract() -> None:
    assert vmr.SAMPLE_RATE == 16000 and vmr.CHANNELS == 1 and vmr.SAMPLE_WIDTH_BYTES == 2
