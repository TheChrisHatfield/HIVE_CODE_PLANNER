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


def _bottom_right(
    work: tuple[int, int, int, int],
    width: int,
    height: int,
    *,
    margin_x: int = 24,
    margin_y: int = 72,
) -> tuple[int, int]:
    """Bottom-right of one monitor's work area, inside that rectangle."""
    left, top, right, bottom = work
    x = min(max(right - width - margin_x, left), max(left, right - width))
    y = min(max(bottom - height - margin_y, top), max(top, bottom - height))
    return x, y


def _geometry(width: int, height: int, work: tuple[int, int, int, int]) -> str:
    x, y = _bottom_right(work, width, height)
    # Tk wants a sign on a negative origin, as in ``400x130+-424+1190``.
    return f"{width}x{height}+{x}+{y}"


def _foreground_work_area() -> tuple[int, int, int, int] | None:
    """Work area of the monitor that holds the window in front.

    The primary screen origin is not that monitor when the IDE sits on
    another display. A minimized window lives far off the desktop, so the
    pointer is the fallback.
    """
    if sys.platform != "win32":
        return None
    import ctypes

    user = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", ctypes.c_ulong),
        ]

    point = POINT()
    hwnd = user.GetForegroundWindow()
    if hwnd:
        rect = RECT()
        if user.GetWindowRect(hwnd, ctypes.byref(rect)):
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width > 0 and height > 0 and rect.left > -20000 and rect.top > -20000:
                point.x = rect.left + width // 2
                point.y = rect.top + height // 2
    if point.x == 0 and point.y == 0 and not user.GetCursorPos(ctypes.byref(point)):
        return None
    monitor = user.MonitorFromPoint(point, 2)
    if not monitor:
        return None
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    work = info.rcWork
    if work.right <= work.left or work.bottom <= work.top:
        return None
    return int(work.left), int(work.top), int(work.right), int(work.bottom)


def _tk_popup(title: str, body: str, seconds: int) -> None:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()
    # Tk becomes the foreground window, so the monitor is read before Tk().
    work = _foreground_work_area()
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
    if work is None:
        work = (0, 0, int(root.winfo_screenwidth()), int(root.winfo_screenheight()))
    root.geometry(_geometry(width, height, work))
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
