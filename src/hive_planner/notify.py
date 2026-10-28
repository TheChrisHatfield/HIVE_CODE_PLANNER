"""Desktop notices that do not enter an IDE chat."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from hive_planner.runtime_paths import APP_DISPLAY_NAME

NOTICE_TITLE = APP_DISPLAY_NAME
MEMORY_CHECK_BODY = (
    "Automatic memory check. You did not type this. "
    "Hive left your chat on the task you were doing."
)


def notifier_script() -> Path:
    return (
        Path(__file__).resolve().parent
        / "vendor_templates"
        / "continual-learning"
        / "hooks"
        / "hive_notify.py"
    )


# A real window stays in its event loop. A crash exits inside this window.
_NOTICE_SETTLE_S = 0.6


def _stayed_open(proc: subprocess.Popen[bytes]) -> bool:
    """True only while the notice process is still running.

    A real window lasts at least a second. Exiting inside the settle window
    means the window never stayed up, including an exit code of 0.
    """
    try:
        proc.wait(timeout=_NOTICE_SETTLE_S)
    except subprocess.TimeoutExpired:
        return True
    return False


def failure_message() -> str:
    if notifier_script().is_file():
        return "Error: Hive notice exited before it stayed open."
    return "Error: Hive notify script is missing."


def notify(title: str, body: str, *, seconds: int = 12, script: Path | None = None) -> bool:
    """Show a popup. True only while the notice process is still running."""
    path = script if script is not None else notifier_script()
    if not path.is_file():
        return False
    cmd = [
        sys.executable,
        str(path),
        "--title",
        title,
        "--body",
        body,
        "--seconds",
        str(max(1, seconds)),
    ]
    env = os.environ.copy()
    dry = env.get("HIVE_NOTIFY_DRY_RUN") == "1"
    try:
        if dry:
            completed = subprocess.run(cmd, check=False, env=env, capture_output=True, text=True)
            return completed.returncode == 0
        kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
            "env": env,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
            )
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **kwargs)
    except OSError:
        return False
    return _stayed_open(proc)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="hive_planner.notify")
    parser.add_argument("--title", default=NOTICE_TITLE)
    parser.add_argument("--body", required=True)
    parser.add_argument("--seconds", type=int, default=12)
    args = parser.parse_args(argv)
    ok = notify(args.title, args.body, seconds=args.seconds)
    if not ok:
        sys.stderr.write(failure_message() + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
