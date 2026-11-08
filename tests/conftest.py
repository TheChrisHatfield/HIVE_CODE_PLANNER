"""Shared pytest hooks for this repo."""

from __future__ import annotations


def pytest_configure(config) -> None:
    from hive_planner.portable_runtime import clear_stale_tk_library_env

    clear_stale_tk_library_env()
