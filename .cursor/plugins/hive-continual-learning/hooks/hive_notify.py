"""IDE-agnostic Hive Planner popup.

This process is not an IDE and not a chat prompt. A stop hook or
``hive_planner notify`` starts it, and the window appears over whatever
program is in front.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def show_popup(title: str, body: str, *, seconds: int = 12) -> bool:
    """True when a window was shown. A log-only fallback is not a shown notice."""
    if os.environ.get("HIVE_NOTIFY_DRY_RUN") == "1":
        payload = json.dumps({"ok": True, "title": title, "body": body}) + "\n"
        log = os.environ.get("HIVE_NOTIFY_LOG")
        if log:
            Path(log).write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
        return True
    try:
        _tk_popup(title, body, seconds)
    except Exception:
        return _fallback(title, body)
    return True


def _tk_popup(title: str, body: str, seconds: int) -> None:
    import tkinter as tk

    root = tk.Tk()
    root.title(title)
    root.attributes("-topmost", True)
    root.resizable(False, False)
    frame = tk.Frame(root, padx=16, pady=12)
    frame.pack(fill="both", expand=True)
    tk.Label(frame, text=title, font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x")
    tk.Label(
        frame,
        text=body,
        wraplength=360,
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(8, 12))
    tk.Button(frame, text="OK", command=root.destroy, width=10).pack(anchor="e")
    root.update_idletasks()
    width = max(root.winfo_reqwidth(), 400)
    height = max(root.winfo_reqheight(), 130)
    margin_x = 24
    margin_y = 72
    x = max(0, root.winfo_screenwidth() - width - margin_x)
    y = max(0, root.winfo_screenheight() - height - margin_y)
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.after(max(1, seconds) * 1000, root.destroy)
    root.mainloop()


def _fallback(title: str, body: str) -> bool:
    if sys.platform == "win32":
        import ctypes

        # MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND. Zero means the dialog did not open.
        shown = ctypes.windll.user32.MessageBoxW(0, body, title, 0x00000040 | 0x00040000 | 0x00010000)
        return shown != 0
    sys.stderr.write(f"{title}: {body}\n")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hive_notify")
    parser.add_argument("--title", default="Hive Planner")
    parser.add_argument("--body", required=True)
    parser.add_argument("--seconds", type=int, default=12)
    args = parser.parse_args(argv)
    return 0 if show_popup(args.title, args.body, seconds=max(1, args.seconds)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
