from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


from hive_planner.launcher.service import _hidden_subprocess_kwargs


def _repo_root() -> Path:
    from hive_planner.runtime_paths import default_hive_root

    return default_hive_root()


def _console_python() -> str:
    exe = Path(sys.executable)
    name = exe.name.lower()
    if name == "pythonw.exe":
        console_exe = exe.with_name("python.exe")
        if console_exe.is_file():
            return str(console_exe)
    if name == "pyw.exe":
        py_exe = exe.with_name("py.exe")
        if py_exe.is_file():
            return str(py_exe)
    return str(exe)


def _package_installed() -> bool:
    try:
        import importlib.metadata

        importlib.metadata.version("hive-planner")
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def _show_startup_error(message: str, detail: str = "") -> None:
    text = message if not detail else f"{message}\n\n{detail.strip()[:800]}"
    try:
        import tkinter as tk
        from tkinter import messagebox

        from hive_planner.launcher.theme import apply_app_icon
        from hive_planner.runtime_paths import APP_DISPLAY_NAME

        root = tk.Tk()
        root.withdraw()
        apply_app_icon(root)
        messagebox.showerror(APP_DISPLAY_NAME, text)
        root.destroy()
    except Exception:
        pass
    raise SystemExit(1)


def ensure_installed() -> None:
    from hive_planner.runtime_paths import is_portable_runtime

    if is_portable_runtime():
        return
    if _package_installed():
        return

    root = _repo_root()
    if not (root / "pyproject.toml").is_file():
        _show_startup_error("Hive planner source not found.", str(root))
        return

    proc = subprocess.run(
        [_console_python(), "-m", "pip", "install", "-e", ".[dev]"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        **_hidden_subprocess_kwargs(),
    )
    if _package_installed():
        return

    output = ((proc.stderr or "") + (proc.stdout or "")).strip()
    tail = output.splitlines()[-1] if output else f"pip exited with code {proc.returncode}"
    _show_startup_error("Could not install hive-planner.", tail)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hive-planner-ui",
        description="Hive Planner desktop app (native window, no browser)",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Show debug console on startup (Windows)",
    )
    args = parser.parse_args(argv)

    ensure_installed()

    if args.console:
        from hive_planner.launcher.console_win import show_console

        show_console()

    from hive_planner.launcher.app import run_app

    run_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
