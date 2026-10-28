from __future__ import annotations

import pytest

from hive_planner.launcher.config import LauncherConfig
from hive_planner.runtime_paths import FROZEN_CLI_FLAG, hive_cli_argv


def test_portable_env_without_frozen_exe_uses_module_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("hive_planner.runtime_paths.is_frozen", lambda: False)
    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    argv = hive_cli_argv(LauncherConfig(python_executable="py -3.11"), "mcp-serve")
    assert FROZEN_CLI_FLAG not in argv
    assert argv[:3] == ["py", "-3.11", "-m"]
    assert "hive_planner" in argv
    assert argv[-1] == "mcp-serve"
