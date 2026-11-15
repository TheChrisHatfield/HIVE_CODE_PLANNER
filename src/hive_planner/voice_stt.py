"""T042 / T033 S1: faster-whisper STT adapter behind `stt_provider` (Windows, CPU).

Pin: evidence-register.md § T033 pin row (faster-whisper 1.2.1, Systran/faster-whisper-base.en
at commit 3d3d5dee26484f91867d81cb899cfcf72b96be6c). The package is imported lazily so the
Hive core stays dependency-free; a missing package raises `stt_unavailable`, never a silent no-op.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

STT_PIN_PROVIDER = "faster-whisper"
STT_PIN_PACKAGE_VERSION = "1.2.1"
STT_PIN_REPO_ID = "Systran/faster-whisper-base.en"
STT_PIN_COMMIT = "3d3d5dee26484f91867d81cb899cfcf72b96be6c"
STT_PIN_MODEL_BIN_SHA256 = "2a166925539a16005f14ff328359f9b9adb9dc4fb631bb3b227526862e93e2ef"
STT_PIN_DEVICE = "cpu"
STT_PIN_COMPUTE_TYPE = "int8"


class SttError(Exception):
    """STT adapter error (stt_unavailable / stt_model_missing / stt_failed)."""


def _local_snapshot() -> Path | None:
    """Cached snapshot dir for the pinned commit, or None. Never downloads."""
    import importlib.util

    if importlib.util.find_spec("faster_whisper") is None:
        return None
    try:
        from huggingface_hub import snapshot_download

        return Path(snapshot_download(STT_PIN_REPO_ID, revision=STT_PIN_COMMIT, local_files_only=True))
    except Exception:
        return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# (path, size, mtime_ns) -> bool. A ~150 MB hash runs once per model file, not per utterance.
_PIN_CHECKS: dict[tuple[str, int, int], bool] = {}


def _model_bin_matches_pin(model_bin: Path) -> bool:
    """True only when `model.bin` hashes to STT_PIN_MODEL_BIN_SHA256."""
    st = model_bin.stat()
    key = (str(model_bin), st.st_size, st.st_mtime_ns)
    if key not in _PIN_CHECKS:
        _PIN_CHECKS[key] = _sha256_file(model_bin) == STT_PIN_MODEL_BIN_SHA256
    return _PIN_CHECKS[key]


def resolve_pinned_model_dir() -> Path | None:
    """Local snapshot of the pinned model, or None when STT cannot run here.

    None unless the optional `faster_whisper` package imports, the pinned commit is in the local
    Hugging Face cache, AND its `model.bin` hashes to the pinned SHA-256. The commit names the
    snapshot, but the cache can still hold other bytes (partial download, manual copy), so the
    hash is what makes the model "pinned". Never downloads. Used to keep `speech_path` honest (T042).
    """
    local = _local_snapshot()
    if local is None:
        return None
    model_bin = local / "model.bin"
    try:
        if not model_bin.is_file() or not _model_bin_matches_pin(model_bin):
            return None
    except OSError:
        return None
    return local


class FasterWhisperAdapter:
    """Transcribe WAV bytes or a WAV path with the pinned faster-whisper model.

    The model directory must be a local snapshot of STT_PIN_REPO_ID at STT_PIN_COMMIT.
    The adapter does not download models.
    """

    name = STT_PIN_PROVIDER
    cancel_on_interruption = False

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = Path(model_dir)
        if not (self.model_dir / "model.bin").is_file():
            raise SttError("stt_model_missing")
        try:
            from faster_whisper import WhisperModel  # lazy: optional voice dependency
        except ImportError as exc:
            raise SttError("stt_unavailable") from exc
        try:
            self._model: Any = WhisperModel(
                str(self.model_dir), device=STT_PIN_DEVICE, compute_type=STT_PIN_COMPUTE_TYPE
            )
        except Exception as exc:  # corrupt/partial model, CTranslate2 load error, OSError
            raise SttError("stt_unavailable") from exc

    def transcribe_file(self, wav_path: Path) -> str:
        try:
            segments, _ = self._model.transcribe(
                str(wav_path),
                language="en",
                beam_size=5,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
        except SttError:
            raise
        except Exception as exc:
            raise SttError("stt_failed") from exc

    def transcribe(self, audio: bytes) -> str:
        if not audio:
            raise SttError("stt_failed")
        with tempfile.TemporaryDirectory(prefix="hive-stt-") as tmp:
            wav = Path(tmp) / "utterance.wav"
            wav.write_bytes(audio)
            return self.transcribe_file(wav)
