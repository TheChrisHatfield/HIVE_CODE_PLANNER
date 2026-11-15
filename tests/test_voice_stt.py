"""T042 / T033: stt_provider read site, pinned adapter, WAV + WER through the adapter."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import (
    VoiceBotConfig,
    VoiceBotError,
    hybrid_speech_path,
    load_voice_bot_config,
    voice_bot_config_path,
)
from hive_planner.voice_stt import (
    STT_PIN_COMMIT,
    STT_PIN_MODEL_BIN_SHA256,
    STT_PIN_REPO_ID,
    FasterWhisperAdapter,
    SttError,
)

ROOT = Path(__file__).resolve().parents[1]
STT_DIR = ROOT / "scripts" / "stt_pin"


def _write_config(root: Path, data: dict) -> RepoPaths:
    paths = RepoPaths(root=root)
    cfg = voice_bot_config_path(paths)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(data), encoding="utf-8")
    return paths


def test_stt_provider_defaults_to_null_and_typed_path(tmp_path: Path):
    paths = RepoPaths(root=tmp_path)
    assert load_voice_bot_config(paths).stt_provider is None
    assert hybrid_speech_path(load_voice_bot_config(paths)) == "typed_instruction"


def test_stt_provider_flag_in_config_flips_speech_path(tmp_path: Path, monkeypatch):
    import hive_planner.voice_stt as voice_stt

    monkeypatch.setattr(voice_stt, "resolve_pinned_model_dir", lambda: tmp_path / "model")
    paths = _write_config(tmp_path, {"stt_provider": "faster-whisper"})
    cfg = load_voice_bot_config(paths)
    assert cfg.stt_provider == "faster-whisper"
    assert hybrid_speech_path(cfg) == "stt"
    # the flag is read from config, not a constant: null in config goes back to typed
    assert hybrid_speech_path(VoiceBotConfig(stt_provider=None)) == "typed_instruction"


def test_unpinned_stt_provider_is_rejected(tmp_path: Path):
    paths = _write_config(tmp_path, {"stt_provider": "moshi"})
    with pytest.raises(VoiceBotError, match="stt_provider"):
        load_voice_bot_config(paths)


def test_resolve_pinned_model_dir_rejects_model_bin_with_wrong_hash(tmp_path: Path, monkeypatch):
    import hive_planner.voice_stt as voice_stt

    snapshot = tmp_path / "snap"
    snapshot.mkdir()
    (snapshot / "model.bin").write_bytes(b"not the pinned model")
    monkeypatch.setattr(voice_stt, "_local_snapshot", lambda: snapshot)
    # Production hash check: the cached file does not match the pin, so speech stays unavailable.
    assert voice_stt.resolve_pinned_model_dir() is None


def test_resolve_pinned_model_dir_accepts_model_bin_matching_pin(tmp_path: Path, monkeypatch):
    import hashlib

    import hive_planner.voice_stt as voice_stt

    payload = b"stand-in model bytes"
    snapshot = tmp_path / "snap"
    snapshot.mkdir()
    (snapshot / "model.bin").write_bytes(payload)
    monkeypatch.setattr(voice_stt, "_local_snapshot", lambda: snapshot)
    monkeypatch.setattr(voice_stt, "STT_PIN_MODEL_BIN_SHA256", hashlib.sha256(payload).hexdigest())
    voice_stt._PIN_CHECKS.clear()
    assert voice_stt.resolve_pinned_model_dir() == snapshot


def test_adapter_without_model_fails_loudly(tmp_path: Path):
    with pytest.raises(SttError, match="stt_model_missing"):
        FasterWhisperAdapter(tmp_path / "no-model")


def test_model_load_failure_is_stt_unavailable_not_raw(tmp_path: Path, monkeypatch):
    """A present but unloadable model.bin must surface as SttError, not a raw exception."""
    import sys
    import types

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "model.bin").write_bytes(b"not a real ctranslate2 model")

    def broken_model(*args, **kwargs):
        raise OSError("corrupt model.bin")

    fake = types.ModuleType("faster_whisper")
    fake.WhisperModel = broken_model
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    with pytest.raises(SttError, match="stt_unavailable"):
        FasterWhisperAdapter(model_dir)


def test_transcribe_runtime_error_is_stt_failed(tmp_path: Path):
    adapter = FasterWhisperAdapter.__new__(FasterWhisperAdapter)

    class Boom:
        def transcribe(self, *args, **kwargs):
            raise RuntimeError("corrupt wav")

    adapter._model = Boom()
    with pytest.raises(SttError, match="stt_failed"):
        adapter.transcribe_file(tmp_path / "x.wav")


def _pinned_model_dir() -> Path | None:
    """Local snapshot of the pinned commit only. Never downloads; skips when absent."""
    try:
        from huggingface_hub import snapshot_download

        local = Path(snapshot_download(STT_PIN_REPO_ID, revision=STT_PIN_COMMIT, local_files_only=True))
    except Exception:
        return None
    return local if (local / "model.bin").is_file() else None


def _wer_helpers():
    spec = importlib.util.spec_from_file_location("stt_pin_wer", STT_DIR / "wer.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pinned_model_matches_register_hash():
    model_dir = _pinned_model_dir()
    if model_dir is None:
        pytest.skip("pinned faster-whisper model not in local HF cache")
    assert model_dir.name == STT_PIN_COMMIT
    helpers = _wer_helpers()
    assert helpers.sha256(model_dir / "model.bin") == STT_PIN_MODEL_BIN_SHA256


def test_wav_fixtures_through_adapter_meet_wer_threshold():
    pytest.importorskip("faster_whisper")
    model_dir = _pinned_model_dir()
    if model_dir is None:
        pytest.skip("pinned faster-whisper model not in local HF cache")
    helpers = _wer_helpers()
    manifest = json.loads((STT_DIR / "fixtures.json").read_text(encoding="utf-8"))
    adapter = FasterWhisperAdapter(model_dir)
    total_ref = total_edits = 0
    for clip in manifest["clips"]:
        wav = STT_DIR / "fixtures" / clip["file"]
        assert wav.is_file(), f"missing fixture {wav}"
        hyp = adapter.transcribe_file(wav)
        ref_words = helpers.normalize(clip["reference"])
        total_ref += len(ref_words)
        total_edits += helpers.word_edits(ref_words, helpers.normalize(hyp))
    wer = total_edits / total_ref
    assert wer <= float(manifest["wer_threshold"]), f"corpus WER {wer:.4f} above threshold"


def test_adapter_transcribe_bytes_matches_file_path():
    pytest.importorskip("faster_whisper")
    model_dir = _pinned_model_dir()
    if model_dir is None:
        pytest.skip("pinned faster-whisper model not in local HF cache")
    adapter = FasterWhisperAdapter(model_dir)
    wav = STT_DIR / "fixtures" / "c01_settings_diff.wav"
    assert adapter.transcribe(wav.read_bytes()) == adapter.transcribe_file(wav)
    with pytest.raises(SttError, match="stt_failed"):
        adapter.transcribe(b"")
