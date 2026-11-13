from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "scripts" / "voice_t042_live_mic.py"


def _mod():
    spec = importlib.util.spec_from_file_location("voice_t042_live_mic", SRC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_transcribe_imports_hive_planner_voice_stt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wav = tmp_path / "mic.wav"
    wav.write_bytes(b"RIFF")
    import hive_planner.voice_stt as vs

    class FakeAdapter:
        def __init__(self, model_dir: Path) -> None:
            self.model_dir = model_dir

        def transcribe_file(self, wav_path: Path) -> str:
            assert wav_path == wav
            return "voice bot test one two three"

    monkeypatch.setattr(vs, "resolve_pinned_model_dir", lambda: tmp_path)
    monkeypatch.setattr(vs, "FasterWhisperAdapter", FakeAdapter)
    out = _mod().transcribe(wav)
    assert out["wer"] == 0.0
    assert out["hypothesis"] == "voice bot test one two three"
    assert out["ref_words"] > 0
