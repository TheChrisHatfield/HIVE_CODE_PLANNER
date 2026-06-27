from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hive-planner-ui",
        description="Hive Planner desktop app (native window, no browser)",
    )
    parser.parse_args(argv)

    from hive_planner.launcher.app import run_app

    run_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
