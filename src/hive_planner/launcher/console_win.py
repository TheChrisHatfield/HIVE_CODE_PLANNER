from __future__ import annotations

import sys

_console_attached = False
_console_visible = False

SW_HIDE = 0
SW_SHOW = 5


def console_available() -> bool:
    return sys.platform == "win32"


def is_console_visible() -> bool:
    """True when this app attached a debug console and it is shown."""
    return _console_attached and _console_visible if console_available() else False


def show_console() -> bool:
    """Attach or reveal a visible console window (Windows only)."""
    global _console_attached, _console_visible
    if not console_available():
        return False

    import ctypes

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    if kernel32.GetConsoleWindow() and not _console_attached:
        # Dev launches from an existing terminal already have a console; do not
        # mark it as app-owned or hide would affect the parent shell.
        return True

    if _console_attached:
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, SW_SHOW)
        _console_visible = bool(hwnd)
        return _console_visible

    if not kernel32.AllocConsole():
        return False

    sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdin = open("CONIN$", "r", encoding="utf-8")  # noqa: SIM115
    _console_attached = True
    hwnd = kernel32.GetConsoleWindow()
    if hwnd:
        user32.ShowWindow(hwnd, SW_SHOW)
    _console_visible = bool(hwnd)
    print("Hive Planner debug console")
    return _console_visible


def hide_console() -> bool:
    """Hide a console this app attached via show_console."""
    global _console_visible
    if not console_available() or not _console_attached:
        _console_visible = False
        return False

    import ctypes

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    hwnd = kernel32.GetConsoleWindow()
    if hwnd:
        user32.ShowWindow(hwnd, SW_HIDE)
    _console_visible = False
    return True
