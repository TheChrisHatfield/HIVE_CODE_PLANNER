"""Tests for scripts/voice_record_clip.py using a fake sounddevice (no real mic)."""

from __future__ import annotations

import importlib.util
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("voice_record_clip", ROOT / "scripts" / "voice_record_clip.py")
clip = importlib.util.module_from_spec(_spec)
sys.modules["voice_record_clip"] = clip
_spec.loader.exec_module(clip)


class FakeStream:
    """Feeds `blocks` of PCM16 to the callback on start, like a real input stream would."""

    def __init__(self, blocks: list[bytes], callback, **kwargs):
        self._blocks = blocks
        self._callback = callback
        self.kwargs = kwargs
        self.stopped = False
        self.closed = False

    def start(self):
        for block in self._blocks:
            self._callback(block, len(block) // 2, None, None)

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class FakeSoundDevice:
    def __init__(self, blocks: list[bytes]):
        self._blocks = blocks
        self.streams: list[FakeStream] = []

    def InputStream(self, **kwargs):  # noqa: N802 - mirrors sounddevice's API
        stream = FakeStream(self._blocks, kwargs["callback"], **{k: v for k, v in kwargs.items() if k != "callback"})
        self.streams.append(stream)
        return stream


REAL_RECORDER = clip.WavMicRecorder  # keep the real class before any test monkeypatches the name


def _patch_recorder(monkeypatch: pytest.MonkeyPatch, fake: FakeSoundDevice) -> None:
    monkeypatch.setattr(
        clip, "WavMicRecorder", lambda getter, sounddevice=None: REAL_RECORDER(getter, sounddevice=fake)
    )


def _tone_block(value: int, samples: int = 160) -> bytes:
    return (value.to_bytes(2, "little", signed=True)) * samples


def test_record_clip_writes_16k_mono_wav_with_captured_audio(tmp_path: Path) -> None:
    fake = FakeSoundDevice([_tone_block(1000), _tone_block(-2000)])

    path = clip.record_clip(0, "Mic X", tmp_path, sounddevice=fake, sleep=lambda _s: None)

    assert path.exists() and path.parent == tmp_path
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == 320
    stream = fake.streams[0]
    assert stream.kwargs["device"] == "Mic X"
    assert stream.stopped and stream.closed


def test_clip_stats_reports_peak_and_flags_silence(tmp_path: Path) -> None:
    loud = clip.record_clip(0, None, tmp_path, sounddevice=FakeSoundDevice([_tone_block(-2000)]), sleep=lambda _s: None)
    quiet = clip.record_clip(0, None, tmp_path, sounddevice=FakeSoundDevice([_tone_block(0)]), sleep=lambda _s: None)

    stats_loud = clip.clip_stats(loud)
    stats_quiet = clip.clip_stats(quiet)

    assert stats_loud["peak_int16"] == 2000 and stats_loud["silent"] is False
    assert stats_quiet["peak_int16"] == 0 and stats_quiet["silent"] is True
    assert stats_loud["sample_rate"] == 16000


def test_main_returns_2_on_silent_clip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    _patch_recorder(monkeypatch, FakeSoundDevice([_tone_block(0)]))

    code = clip.main(["--seconds", "0", "--out-dir", str(tmp_path)])

    assert code == 2
    assert "pure silence" in capsys.readouterr().err


def test_main_returns_0_on_audible_clip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_recorder(monkeypatch, FakeSoundDevice([_tone_block(500)]))

    assert clip.main(["--seconds", "0", "--out-dir", str(tmp_path)]) == 0

def test_finish_clip_saves_wav_and_last_clip_json(tmp_path: Path) -> None:
    import json

    sys.path.insert(0, str(ROOT / "scripts"))
    import voice_record_app as app

    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(_tone_block(900, samples=800))
    wav_bytes = buf.getvalue()

    stats = app.finish_clip(wav_bytes, tmp_path)

    assert Path(stats["path"]).exists()
    assert stats["peak_int16"] == 900 and stats["silent"] is False
    saved = json.loads((tmp_path / "last-clip.json").read_text(encoding="utf-8"))
    assert saved["path"] == stats["path"]
