"""Shared pytest hooks for this repo."""

from __future__ import annotations


def pytest_configure(config) -> None:
    from hive_planner.portable_runtime import clear_stale_tk_library_env

    clear_stale_tk_library_env()


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_moshi_spawn(monkeypatch):
    """Tests never start a real `moshi.server` (GPU model). Tests that need a child process
    replace `SERVER` with their own `MoshiServerProcess` using a stub command."""
    from hive_planner import voice_moshi_server

    def _refuse(*_args, **_kwargs):
        raise AssertionError("test tried to start the real moshi.server")

    monkeypatch.setattr(voice_moshi_server.SERVER, "_popen", _refuse)
