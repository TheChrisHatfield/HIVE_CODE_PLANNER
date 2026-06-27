from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


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


def ensure_installed() -> None:
    try:
        import importlib.metadata

        importlib.metadata.version("hive-planner")
        return
    except Exception:
        pass

    root = _repo_root()
    if not (root / "pyproject.toml").is_file():
        return

    subprocess.run(
        [_console_python(), "-m", "pip", "install", "-e", ".[dev]"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


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
