from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hive_planner.runtime_paths import (
    FROZEN_CLI_FLAG,
    default_config_dir,
    default_hive_root,
    is_cli_invocation,
    is_portable_runtime,
    strip_cli_dispatch_argv,
)


def test_is_portable_runtime_env_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    assert is_portable_runtime() is True


def test_portable_config_dir_uses_app_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path / "app"))
    assert default_config_dir() == (tmp_path / "app" / "config").resolve()
    assert default_hive_root() == (tmp_path / "app").resolve()


def test_frozen_cli_argv_normalization() -> None:
    argv = ["HivePlanner.exe", FROZEN_CLI_FLAG, "ci-check", "--root", "."]
    assert strip_cli_dispatch_argv(argv) == ["HivePlanner.exe", "ci-check", "--root", "."]


def test_is_cli_invocation_detects_subcommands() -> None:
    assert is_cli_invocation(["HivePlanner.exe", "ci-check"]) is True
    assert is_cli_invocation(["HivePlanner.exe"]) is False
    assert is_cli_invocation(["HivePlanner.exe", "--console"]) is False
    assert is_cli_invocation(["HivePlanner.exe", FROZEN_CLI_FLAG, "init"]) is True


def test_frozen_entry_bootstraps_before_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import hive_planner.frozen_entry as entry
    import hive_planner.portable_runtime as pr
    import hive_planner.runtime_paths as rp

    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path))
    calls: list[bool] = []

    def _ensure(root: Path, *, force: bool = False):
        calls.append(force)
        return pr.PortableRuntimeReport(
            ok=True,
            bundled_ok=True,
            deployed_ok=True,
            detail="ok",
        )

    monkeypatch.setattr(pr, "ensure_portable_runtime", _ensure)
    monkeypatch.setattr(rp, "is_cli_invocation", lambda _argv=None: True)
    monkeypatch.setattr(
        rp,
        "strip_cli_dispatch_argv",
        lambda _argv=None: ["HivePlanner.exe", "roadmap-status"],
    )

    def _cli_main():
        return 0

    monkeypatch.setattr("hive_planner.cli.main", _cli_main)

    assert entry.run() == 0
    assert calls == [False]


def test_auto_complete_onboarding_portable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from hive_planner.launcher.config import LauncherConfig
    from hive_planner.launcher.service import auto_complete_onboarding_if_ready
    from hive_planner.portable_runtime import ensure_portable_runtime

    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path))
    ensure_portable_runtime(tmp_path, force=True)
    cfg = LauncherConfig()
    assert auto_complete_onboarding_if_ready(cfg) is True
    assert cfg.onboarding_complete is True


def test_run_install_portable_deploys_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from hive_planner.launcher.config import LauncherConfig
    from hive_planner.launcher.service import run_install

    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path))
    result = run_install(LauncherConfig())
    assert result.ok is True
    assert "Spec Kit" in result.detail or "Portable runtime ready" in result.detail
    assert (tmp_path / ".hive" / "spec-kit" / "WORKFLOW.md").is_file()


def test_normalized_hive_root_ignores_stale_path_in_portable_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from hive_planner.launcher.config import LauncherConfig

    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path))
    cfg = LauncherConfig(hive_planner_root=r"D:\wrong\hive-checkout")

    assert cfg.normalized_hive_root() == tmp_path.resolve()


def test_save_settings_preserves_portable_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.config import LauncherConfig, save_config
    from hive_planner.launcher.service import get_setup_status

    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path))
    cfg = LauncherConfig(
        hive_planner_root=str(tmp_path),
        python_executable="py -3.11",
        cursor_executable=r"C:\Cursor\Cursor.exe",
    )
    save_config(cfg)

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app.setup = get_setup_status(cfg)
    app.cfg_hive = type("V", (), {"get": lambda self: "D:\\wrong\\path"})()
    app.cfg_python = type("V", (), {"get": lambda self: "py -3.9"})()
    app.cfg_cursor = type("V", (), {"get": lambda self: r"C:\Cursor\Cursor.exe"})()
    app.cfg_profile = type("V", (), {"get": lambda self: "full"})()
    app.cfg_agent_handoff = type("V", (), {"get": lambda self: "unified"})()
    app._show_dashboard = lambda: None  # type: ignore[method-assign]
    import tkinter.messagebox as messagebox

    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)

    app._on_save_settings()

    assert cfg.hive_planner_root == str(tmp_path)
    assert cfg.python_executable == "py -3.11"
    assert cfg.cursor_executable == r"C:\Cursor\Cursor.exe"
