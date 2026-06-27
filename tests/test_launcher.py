from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from hive_planner.launcher.config import LauncherConfig, load_config, save_config
from hive_planner.launcher.service import (
    _python_command,
    get_setup_status,
    run_project_init,
    summarize_project,
)


def test_config_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / "appdata"
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    original = LauncherConfig(
        onboarding_complete=True,
        hive_planner_root=str(tmp_path),
        python_executable="py -3.11",
        recent_projects=[str(tmp_path / "proj-a")],
    )
    save_config(original)
    loaded = load_config()
    assert loaded.onboarding_complete is True
    assert loaded.hive_planner_root == str(tmp_path)
    assert loaded.recent_projects == [str(tmp_path / "proj-a")]


def test_add_recent_project_dedupes(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    cfg = LauncherConfig(recent_projects=[str(a), str(b)])
    cfg.add_recent_project(b)
    assert cfg.recent_projects[0] == str(b.resolve())
    assert len(cfg.recent_projects) == 2


def test_summarize_non_hive_project(tmp_path: Path) -> None:
    summary = summarize_project(tmp_path)
    assert summary.ok is False
    assert "START_HERE" in summary.detail


def test_get_setup_status_reads_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / "cfg"
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    save_config(LauncherConfig(hive_planner_root=str(tmp_path), onboarding_complete=True))
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    cfg = load_config()
    status = get_setup_status(cfg)
    assert status.onboarding_complete is True
    assert status.hive_root_ok is True


def test_run_project_init_minimal(tmp_path: Path) -> None:
    hive_root = Path(__file__).resolve().parents[1]
    target = tmp_path / "demo-app"
    cfg = LauncherConfig(hive_planner_root=str(hive_root))
    with patch("hive_planner.bootstrap.subprocess.run"):
        result = run_project_init(
            cfg,
            target=target,
            name="Demo App",
            profile="minimal",
            git_init=False,
            force=False,
        )
    assert result["ok"] is True
    assert (target / "START_HERE.md").is_file()


def test_python_command_preserves_quoted_paths() -> None:
    cfg = LauncherConfig(python_executable=r'"C:\Program Files\Python311\python.exe"')
    assert _python_command(cfg) == [r"C:\Program Files\Python311\python.exe"]

    cfg2 = LauncherConfig(python_executable="py -3.11")
    assert _python_command(cfg2) == ["py", "-3.11"]


def test_select_recent_rejects_missing_project(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    import tkinter as tk

    missing = tmp_path / "gone"
    root = tk.Tk()
    root.withdraw()
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(recent_projects=[str(missing)])
    app.root = root

    class Box:
        calls: list[tuple[str, str]] = []

    def showerror(title, message):
        Box.calls.append((title, message))

    app.recent_list = type("L", (), {"curselection": lambda self: (0,), "get": lambda self, i: str(missing)})()
    import hive_planner.launcher.app as app_mod

    original = app_mod.messagebox.showerror
    app_mod.messagebox.showerror = showerror
    try:
        app._on_select_recent()
    finally:
        app_mod.messagebox.showerror = original
    root.destroy()

    assert Box.calls
    assert "Directory not found" in Box.calls[0][1]
    assert app.config.active_project == ""


def test_ci_check_report_is_not_bg_error() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    report = {"ok": False, "steps": [{"name": "pytest", "ok": False, "detail": "1 failed"}]}
    assert app._is_bg_error(report) is False
    assert app._is_bg_error({"ok": False, "error": "boom"}) is True


def test_install_result_failure_dict() -> None:
    from hive_planner.launcher.app import HivePlannerApp
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    app = HivePlannerApp.__new__(HivePlannerApp)
    assert app._result_failed({"ok": False, "error": "pip failed"}) is True
    assert app._result_failed({"ok": True}) is False
    assert "pip failed" in app._result_detail({"ok": False, "error": "pip failed"})
    root.destroy()


def test_bg_generation_invalidates_stale_callbacks() -> None:
    from hive_planner.launcher.app import HivePlannerApp
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    app = HivePlannerApp.__new__(HivePlannerApp)
    app._bg_generation = 0
    app.root = root
    called = {"value": False}

    def on_done(_result) -> None:
        called["value"] = True

    generation = app._bg_generation

    def finish() -> None:
        if generation != app._bg_generation:
            return
        on_done({})

    app._invalidate_bg_callbacks()
    finish()
    assert called["value"] is False

    app._bg_generation = generation
    finish()
    assert called["value"] is True
    root.destroy()


def test_load_config_recovers_corrupt_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    cfg_dir = tmp_path / "cfg"
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    bad = cfg_dir / "config.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not-json", encoding="utf-8")
    cfg = load_config()
    assert cfg.hive_planner_root
    json.loads(bad.read_text(encoding="utf-8"))

