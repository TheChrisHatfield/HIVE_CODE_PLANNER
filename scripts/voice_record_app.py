"""Press-to-record mic app for Voice_Bot debugging (Tkinter, no countdown).

Window: Start recording -> speak -> Stop & save. Each stop writes:
  .hive/voice-bot/recordings/clip-<stamp>.wav     the audio
  .hive/voice-bot/recordings/last-clip.json       stats for the last clip (path, peak, silent)

Usage (double-click or run in a terminal):
  py -3.11 scripts\\voice_record_app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SCRIPTS))

from voice_record_clip import DEFAULT_OUT_DIR, clip_stats, save_clip  # noqa: E402
from hive_planner.launcher.voice_mic_recorder import WavMicRecorder  # noqa: E402

LAST_CLIP_JSON = "last-clip.json"


def finish_clip(wav_bytes: bytes, out_dir: Path = DEFAULT_OUT_DIR) -> dict:
    """Save a finished clip and its stats (no UI). Returns the stats dict that was also written to JSON."""
    path = save_clip(wav_bytes, out_dir)
    stats = clip_stats(path)
    (out_dir / LAST_CLIP_JSON).write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def run_app() -> None:
    import time
    import tkinter as tk

    recorder = WavMicRecorder(lambda: None)  # system default mic
    state = {"started_at": 0.0, "recording": False}

    root = tk.Tk()
    root.title("Voice clip recorder")
    root.geometry("460x300")

    status = tk.Label(root, text="Ready. Press Start, then speak.", font=("Segoe UI", 12))
    status.pack(pady=(14, 4))
    timer = tk.Label(root, text="0.0 s", font=("Segoe UI", 28, "bold"))
    timer.pack()
    result = tk.Label(root, text="", font=("Segoe UI", 10), justify="left", wraplength=420)
    result.pack(pady=8)

    def tick() -> None:
        if state["recording"]:
            timer.config(text=f"{time.monotonic() - state['started_at']:.1f} s")
            root.after(100, tick)

    def start() -> None:
        try:
            recorder.start()
        except OSError as exc:
            status.config(text="Could not open the mic.")
            result.config(text=str(exc))
            return
        state.update(recording=True, started_at=time.monotonic())
        status.config(text="RECORDING. Speak now, then press Stop & save.")
        result.config(text="")
        start_btn.config(state="disabled")
        stop_btn.config(state="normal")
        tick()

    def stop() -> None:
        state["recording"] = False
        wav = recorder.stop()
        stats = finish_clip(wav)
        start_btn.config(state="normal")
        stop_btn.config(state="disabled")
        timer.config(text=f"{stats['seconds']:.1f} s")
        if stats["silent"]:
            status.config(text="Saved, but the clip is pure silence.")
        elif stats["peak_int16"] < 2000:
            status.config(text="Saved. Very quiet. Speak closer to the mic.")
        else:
            status.config(text="Saved.")
        result.config(text=f"peak {stats['peak_int16']} / 32767\n{stats['path']}")

    start_btn = tk.Button(root, text="Start recording", width=18, height=2, command=start)
    start_btn.pack(pady=4)
    stop_btn = tk.Button(root, text="Stop & save", width=18, height=2, command=stop, state="disabled")
    stop_btn.pack(pady=4)

    root.protocol("WM_DELETE_WINDOW", lambda: (stop() if state["recording"] else None, root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    run_app()
