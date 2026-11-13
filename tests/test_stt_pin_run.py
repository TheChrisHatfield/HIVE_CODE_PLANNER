from __future__ import annotations

import importlib.util
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STT_DIR = ROOT / "scripts" / "stt_pin"
if str(STT_DIR) not in sys.path:
    sys.path.insert(0, str(STT_DIR))


def _load():
    spec = importlib.util.spec_from_file_location("stt_pin_run", STT_DIR / "run_pin.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_does_not_require_faster_whisper():
    already = "faster_whisper" in sys.modules
    _load()
    if not already:
        assert "faster_whisper" not in sys.modules


def test_wer_ratio_empty_reference_is_not_a_pass():
    pin = _load()
    assert pin.wer_ratio(0, 0) is None
    assert pin.wer_ratio(3, 0) is None
    assert pin.wer_ratio(4, 41) == 0.0976


def test_duration_ratio_zero_seconds():
    pin = _load()
    assert pin.duration_ratio(1.5, 0.0) is None
    assert pin.duration_ratio(2.0, 1.0) == 2.0


def test_nearest_rank_empty_and_five_clip_p95():
    pin = _load()
    assert pin.nearest_rank([], 0.95) is None
    assert pin.nearest_rank([10.0, 20.0, 30.0, 40.0, 50.0], 0.95) == 50.0


def test_wav_info_empty_pcm_does_not_divide(tmp_path: Path):
    pin = _load()
    path = tmp_path / "empty.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"")
    info = pin.wav_info(path)
    assert info["seconds"] == 0.0
    assert pin.duration_ratio(0.4, info["seconds"]) is None
