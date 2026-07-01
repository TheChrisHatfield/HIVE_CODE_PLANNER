"""Frozen / portable path resolution for standalone Hive Planner builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN_CLI_FLAG = "--hive-cli"

_GUI_ONLY_ARGS = frozenset({"--console"})


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_portable_runtime() -> bool:
    """True when running as a PyInstaller build or explicit portable mode."""
    if is_frozen():
        return True
    flag = os.environ.get("HIVE_PLANNER_PORTABLE", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def portable_app_root() -> Path:
    """Directory containing the portable app (exe folder or dev repo root)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    override = os.environ.get("HIVE_PLANNER_APP_ROOT", "").strip()
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[2]


def bundle_root() -> Path | None:
    """PyInstaller extract dir; None when not frozen."""
    if not is_frozen():
        return None
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass).resolve() if meipass else None


def default_hive_root() -> Path:
    if is_portable_runtime():
        return portable_app_root()
    return Path(__file__).resolve().parents[2]


def default_config_dir() -> Path:
    if is_portable_runtime():
        return portable_app_root() / "config"
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "HivePlanner"
    return Path.home() / ".hive-planner"


def bundled_resource(*parts: str) -> Path | None:
    """Resolve a file shipped inside a frozen bundle."""
    root = bundle_root()
    if root is None:
        return None
    candidate = root.joinpath(*parts)
    return candidate if candidate.is_file() else None


def frozen_cli_prefix() -> list[str]:
    return [sys.executable, FROZEN_CLI_FLAG]


def hive_cli_argv(config, *cli_args: str) -> list[str]:
    """Build argv for a hive_planner CLI subprocess (or in-process dispatch when frozen)."""
    if is_portable_runtime():
        return frozen_cli_prefix() + list(cli_args)
    from hive_planner.launcher.service import _python_command

    return _python_command(config) + ["-m", "hive_planner", *cli_args]


def is_cli_invocation(argv: list[str] | None = None) -> bool:
    args = list(argv if argv is not None else sys.argv)
    if len(args) < 2:
        return False
    first = args[1]
    if first in _GUI_ONLY_ARGS:
        return False
    if first == FROZEN_CLI_FLAG:
        return True
    if first.startswith("-"):
        return first in {"-h", "--help"}
    return True


def strip_cli_dispatch_argv(argv: list[str] | None = None) -> list[str]:
    """Normalize argv for hive_planner.cli.main after frozen dispatch."""
    args = list(argv if argv is not None else sys.argv)
    if len(args) > 1 and args[1] == FROZEN_CLI_FLAG:
        rest = args[2:]
        if not rest:
            return [args[0], "--help"]
        return [args[0], *rest]
    return args
