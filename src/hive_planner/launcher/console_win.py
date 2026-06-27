from __future__ import annotations

import sys

_console_attached = False


def console_available() -> bool:
    return sys.platform == "win32"


def is_console_visible() -> bool:
    """True when the user (or --console) attached our debug console."""
    return _console_attached if console_available() else False


def show_console() -> bool:
    """Attach a visible console window (Windows only)."""
    global _console_attached
    if not console_available():
        return False
    if _console_attached:
        return True

    import ctypes

    kernel32 = ctypes.windll.kernel32
    if kernel32.GetConsoleWindow():
        _console_attached = True
        return True

    if not kernel32.AllocConsole():
        return False

    sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdin = open("CONIN$", "r", encoding="utf-8")  # noqa: SIM115
    _console_attached = True
    print("Hive Planner debug console")
    return True


def hide_console() -> bool:
    """Detach a console this app attached via show_console."""
    global _console_attached
    if not console_available() or not _console_attached:
        _console_attached = False
        return False

    import ctypes

    kernel32 = ctypes.windll.kernel32
    if kernel32.GetConsoleWindow():
        kernel32.FreeConsole()
    _console_attached = False
    return True
