"""T033 gap A: Whisper-class Windows STT pin run (CPU only).

Run with the pinned venv:
  .hive\\stt-pin\\.venv\\Scripts\\python.exe scripts\\stt_pin\\run_pin.py

Writes .hive/stt-pin/result.json. Does not change STT_PROVIDER or any test.
"""

from __future__ import annotations

import json
import platform
import time
import wave
from importlib import metadata
from pathlib import Path

from wer import normalize, sha256, word_edits

REPO_ID = "Systran/faster-whisper-base.en"
COMPUTE_TYPE = "int8"
DEVICE = "cpu"
LATENCY_TARGET_MS = 8000  # VoiceBotConfig.latency_target_ms default (R24); comparison only

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MANIFEST = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
WER_THRESHOLD = float(MANIFEST["wer_threshold"])
OUT = ROOT / ".hive" / "stt-pin" / "result.json"


def wav_info(path: Path) -> dict:
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        frames = w.getnframes()
        return {
            "sample_rate": rate,
            "channels": w.getnchannels(),
            "sample_width_bytes": w.getsampwidth(),
            "seconds": round(frames / rate, 3) if rate > 0 else 0.0,
        }


def wer_ratio(edits: int, ref_count: int) -> float | None:
    """Word error rate, or None when the reference has no words (not a pass)."""
    if ref_count <= 0:
        return None
    return round(edits / ref_count, 4)


def duration_ratio(numerator: float, seconds: float, digits: int = 3) -> float | None:
    if seconds <= 0:
        return None
    return round(numerator / seconds, digits)


def nearest_rank(sorted_vals: list[float], q: float) -> float | None:
    if not sorted_vals:
        return None
    index = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[index]


def main() -> int:
    from faster_whisper import WhisperModel
    from huggingface_hub import snapshot_download

    t0 = time.perf_counter()
    model_dir = Path(snapshot_download(REPO_ID))
    download_s = time.perf_counter() - t0
    commit = model_dir.name
    model_bin = model_dir / "model.bin"

    t1 = time.perf_counter()
    model = WhisperModel(str(model_dir), device=DEVICE, compute_type=COMPUTE_TYPE)
    load_s = time.perf_counter() - t1

    clips = []
    total_ref = total_edits = 0
    total_audio_s = total_wall_s = 0.0
    fixtures_dir = HERE / "fixtures"
    for clip in MANIFEST["clips"]:
        wav = fixtures_dir / clip["file"]
        info = wav_info(wav)
        t = time.perf_counter()
        segments, _ = model.transcribe(
            str(wav), language="en", beam_size=5, vad_filter=False, condition_on_previous_text=False
        )
        hyp_text = " ".join((seg.text or "").strip() for seg in segments).strip()
        wall_ms = (time.perf_counter() - t) * 1000
        ref_words = normalize(clip["reference"])
        hyp_words = normalize(hyp_text)
        edits = word_edits(ref_words, hyp_words)
        nref = len(ref_words)
        if nref:
            total_ref += nref
            total_edits += edits
        if info["seconds"] > 0:
            total_audio_s += info["seconds"]
            total_wall_s += wall_ms / 1000
        clips.append(
            {
                "id": clip["id"],
                "file": clip["file"],
                "audio": info,
                "sha256": sha256(wav),
                "reference": clip["reference"],
                "hypothesis": hyp_text,
                "word_edits": edits,
                "ref_words": nref,
                "wer": wer_ratio(edits, nref),
                "transcribe_wall_ms": round(wall_ms, 1),
                "rtf": duration_ratio(wall_ms / 1000, info["seconds"]),
            }
        )

    corpus_wer = wer_ratio(total_edits, total_ref)
    lat_ms = [c["transcribe_wall_ms"] for c in clips]
    lat_ms_sorted = sorted(lat_ms)
    result = {
        "phase": "S1 candidate (T033 gap A)",
        "date": time.strftime("%Y-%m-%d"),
        "host": {
            "os": platform.platform(),
            "cpu": platform.processor(),
            "python": platform.python_version(),
            "device": DEVICE,
            "compute_type": COMPUTE_TYPE,
            "threads_note": "faster-whisper CPU default threads",
        },
        "packages": {
            "faster-whisper": metadata.version("faster-whisper"),
            "ctranslate2": metadata.version("ctranslate2"),
        },
        "model": {
            "repo_id": REPO_ID,
            "commit": commit,
            "model_bin_sha256": sha256(model_bin),
            "model_bin_bytes": model_bin.stat().st_size,
            "local_dir": str(model_dir),
        },
        "method": {
            "fixtures": "scripts/stt_pin/fixtures/*.wav (SAPI TTS, 16 kHz mono PCM16)",
            "manifest": "scripts/stt_pin/fixtures.json",
            "decode": "beam_size=5, language=en, vad_filter=False, condition_on_previous_text=False",
            "wer_threshold": WER_THRESHOLD,
            "wer_normalization": "lowercase, strip non [a-z0-9'], whitespace split, word-level Levenshtein",
        },
        "timing": {
            "download_s": round(download_s, 2),
            "model_load_s": round(load_s, 2),
            "latency_target_ms_reference": LATENCY_TARGET_MS,
            "per_clip_p95_ms": nearest_rank(lat_ms_sorted, 0.95),
            "per_clip_max_ms": lat_ms_sorted[-1] if lat_ms_sorted else None,
            "corpus_rtf": duration_ratio(total_wall_s, total_audio_s),
        },
        "clips": clips,
        "corpus": {
            "ref_words": total_ref,
            "word_edits": total_edits,
            "wer": corpus_wer,
            "pass": corpus_wer is not None and corpus_wer <= WER_THRESHOLD,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("packages", "model", "timing", "corpus")}, indent=2))
    for c in clips:
        print(f"{c['id']} wer={c['wer']} ms={c['transcribe_wall_ms']} hyp={c['hypothesis']!r}")
    return 0 if result["corpus"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
