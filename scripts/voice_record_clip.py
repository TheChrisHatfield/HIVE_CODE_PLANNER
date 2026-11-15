"""Record a plain mic clip for Voice_Bot debugging (no evidence writes, no transcription).

Uses the same recorder the launcher Voice panel uses (`WavMicRecorder`), so a clip that records
here proves the capture path works on this machine. It writes one WAV and prints its stats.

Usage (run at the microphone):
  py -3.11 scripts\\voice_record_clip.py                    # 10 s, default mic
  py -3.11 scripts\\voice_record_clip.py --seconds 20 --device "Microphone (9- C-Media USB Head"
  py -3.11 scripts\\voice_record_clip.py --list-devices

Output goes to `.hive/voice-bot/recordings/` (git-ignored) unless --out-dir is given.
"""

from __future__ import annotations

import argparse
import array
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hive_planner.launcher.voice_mic_recorder import SAMPLE_RATE, WavMicRecorder  # noqa: E402

DEFAULT_OUT_DIR = ROOT / ".hive" / "voice-bot" / "recordings"


def record_clip(seconds: float, device: str | None, out_dir: Path, *, sounddevice=None, sleep=time.sleep) -> Path:
    """Record `seconds` from `device` (None = system default) and return the written WAV path."""
    recorder = WavMicRecorder(lambda: device, sounddevice=sounddevice)
    recorder.start()  # raises OSError when the mic cannot open; let it surface with its reason
    try:
        sleep(seconds)
    except KeyboardInterrupt:
        pass  # Ctrl+C ends the clip early; whatever was captured is still saved
    return save_clip(recorder.stop(), out_dir)


def save_clip(wav_bytes: bytes, out_dir: Path) -> Path:
    """Write WAV bytes to `out_dir` under a microsecond-stamped name (never overwrites)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"clip-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.wav"
    path.write_bytes(wav_bytes)
    return path


def clip_stats(path: Path) -> dict:
    with wave.open(str(path), "rb") as w:
        frames = w.getnframes()
        raw = w.readframes(frames)
        rate = w.getframerate()
        channels = w.getnchannels()
    samples = array.array("h")
    samples.frombytes(raw)
    peak = max((abs(s) for s in samples), default=0)
    return {
        "path": str(path),
        "seconds": round(frames / rate, 2) if rate else 0.0,
        "sample_rate": rate,
        "channels": channels,
        "peak_int16": peak,
        "silent": peak == 0,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Record a mic clip to WAV for Voice_Bot debugging.")
    ap.add_argument("--seconds", type=float, default=10.0, help="clip length in seconds (default 10)")
    ap.add_argument("--device", default=None, help="input device name (default: system default mic)")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="where to write the WAV")
    ap.add_argument("--list-devices", action="store_true", help="print input devices and exit")
    args = ap.parse_args(argv)

    if args.list_devices:
        import sounddevice as sd

        print(sd.query_devices())
        return 0

    print(f"Recording {args.seconds:g} s at {SAMPLE_RATE} Hz from {args.device or 'default mic'}. Speak now.")
    try:
        path = record_clip(args.seconds, args.device, args.out_dir)
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    stats = clip_stats(path)
    for key, value in stats.items():
        print(f"{key}: {value}")
    if stats["silent"]:
        print("WARNING: clip is pure silence. Wrong device, or the mic is muted.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
