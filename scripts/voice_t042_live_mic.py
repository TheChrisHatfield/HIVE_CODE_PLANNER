"""T042 live-mic evidence run (Voice_Bot, Windows S1). Operator runs this at the microphone.

Steps:
  1. Plays a fixed one-second tone through the default output (winsound) and records playback success.
  2. Records a fixed phrase from the default microphone (sounddevice, 16 kHz mono PCM16).
  3. Transcribes the recording with the pinned faster-whisper model (voice_stt.FasterWhisperAdapter).
  4. Computes word error rate against the fixed reference phrase (threshold fixed before the run).
  5. Appends one live audio row to docs/specs/Voice_Bot/evidence-register.md (only with --write).

Usage (pinned venv, Windows host, operator at the mic):
  .hive\\stt-pin\\.venv\\Scripts\\python.exe scripts\\voice_t042_live_mic.py            # dry run, prints row
  .hive\\stt-pin\\.venv\\Scripts\\python.exe scripts\\voice_t042_live_mic.py --write    # appends row

Scope: this records the T042 live audio row only (spec § Speech I/O rollout, evidence item 2).
It does NOT record the audio-on live interruption row (item 3) and does NOT flip STT_PROVIDER,
audio_enabled, or any config. Playback here is a direct winsound tone, not the runtime
speak path, so the row says so explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import tempfile
import time
import wave
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "stt_pin"))

REGISTER = ROOT / "docs" / "specs" / "Voice_Bot" / "evidence-register.md"
RESULT = ROOT / ".hive" / "stt-pin" / "live-mic-result.json"

# Fixed before the run (same discipline as the T033 pin).
REFERENCE_PHRASE = "voice bot test one two three"
WER_THRESHOLD = 0.10
RECORD_SECONDS = 5
SAMPLE_RATE = 16000
CHANNELS = 1
TONE_HZ = 440
TONE_SECONDS = 1.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def write_tone(path: Path) -> None:
    import math
    import struct

    n = int(SAMPLE_RATE * TONE_SECONDS)
    frames = b"".join(
        struct.pack("<h", int(12000 * math.sin(2 * math.pi * TONE_HZ * i / SAMPLE_RATE))) for i in range(n)
    )
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(frames)


def play_tone(tmp: Path) -> dict:
    """Playback success = winsound returned without raising on an existing file."""
    tone = tmp / "tone.wav"
    write_tone(tone)
    out = {"file_sha256": sha256(tone), "played": False, "error": None}
    try:
        import winsound

        winsound.PlaySound(str(tone), winsound.SND_FILENAME)  # blocks until done
        out["played"] = True
    except Exception as exc:  # noqa: BLE001 - record any failure as evidence, do not hide it
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def record_phrase(tmp: Path) -> dict:
    """Record RECORD_SECONDS from the default mic. Fails loudly if sounddevice is missing."""
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise SystemExit("sounddevice not installed in the pinned venv; install it, then rerun") from exc

    print(f"Say: '{REFERENCE_PHRASE}'. Recording {RECORD_SECONDS} seconds starting in 1 second...")
    time.sleep(1)
    data = sd.rec(
        int(RECORD_SECONDS * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16"
    )
    sd.wait()
    wav = tmp / "mic.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(data.tobytes())
    peak = int(abs(data).max())
    return {"path": wav, "sha256": sha256(wav), "seconds": RECORD_SECONDS, "peak_int16": peak}


def transcribe(wav: Path) -> dict:
    from hive_planner.voice_stt import FasterWhisperAdapter, resolve_pinned_model_dir
    from wer import normalize, word_edits

    model_dir = resolve_pinned_model_dir()
    if model_dir is None:
        raise SystemExit("pinned STT model not found; run the T033 pin first")
    t = time.perf_counter()
    hyp = FasterWhisperAdapter(model_dir).transcribe_file(wav)
    wall_ms = round((time.perf_counter() - t) * 1000, 1)
    ref_words = normalize(REFERENCE_PHRASE)
    hyp_words = normalize(hyp)
    edits = word_edits(ref_words, hyp_words)
    return {
        "hypothesis": hyp,
        "word_edits": edits,
        "ref_words": len(ref_words),
        "wer": round(edits / len(ref_words), 4),
        "transcribe_wall_ms": wall_ms,
    }


def build_row(result: dict) -> str:
    passed = result["playback"]["played"] and result["stt"]["wer"] <= WER_THRESHOLD and result["mic"]["peak_int16"] > 0
    verdict = "**pass**" if passed else "**open**"
    return (
        f"| T042-live-audio | Windows S1 spoken input + playback, `audio: true` | "
        f"`faster-whisper` pinned (T033-S1); tone playback via winsound (direct, not runtime speak path) | "
        f"`py scripts\\voice_t042_live_mic.py --write`; reference '{REFERENCE_PHRASE}', WER threshold {WER_THRESHOLD}, "
        f"{RECORD_SECONDS}s mic capture | {verdict} | {result['date']} | "
        f"playback_ok={result['playback']['played']} wer={result['stt']['wer']} "
        f"hyp={result['stt']['hypothesis']!r} mic_sha256={result['mic']['sha256'][:12]} "
        f"host={platform.platform()} audio_enabled=false (not read by this run) |"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="append the row to evidence-register.md")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="t042-live-") as td:
        tmp = Path(td)
        playback = play_tone(tmp)
        mic = record_phrase(tmp)
        stt = transcribe(mic["path"])

    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "phrase": REFERENCE_PHRASE,
        "wer_threshold": WER_THRESHOLD,
        "playback": playback,
        "mic": {k: v for k, v in mic.items() if k != "path"},
        "stt": stt,
    }
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    row = build_row(result)
    print(json.dumps(result, indent=2, default=str))
    print(row)
    if args.write:
        with REGISTER.open("a", encoding="utf-8") as f:
            f.write("\n" + row + "\n")
        print(f"appended to {REGISTER}")
    else:
        print("dry run: register not changed (rerun with --write)")
    return 0 if "**pass**" in row else 1


if __name__ == "__main__":
    raise SystemExit(main())
