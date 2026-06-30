"""PyInstaller entrypoint — GUI by default; CLI via subcommand or --hive-cli."""

from __future__ import annotations

import sys


def run() -> int:
    from hive_planner.runtime_paths import is_cli_invocation, is_portable_runtime, portable_app_root, strip_cli_dispatch_argv

    if is_portable_runtime():
        from hive_planner.portable_runtime import ensure_portable_runtime

        ensure_portable_runtime(portable_app_root(), force=False)

    if is_portable_runtime() and is_cli_invocation():
        sys.argv = strip_cli_dispatch_argv()
        from hive_planner.cli import main

        return main()

    from hive_planner.launcher.__main__ import main as gui_main

    return gui_main()


if __name__ == "__main__":
    raise SystemExit(run())
