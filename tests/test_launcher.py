from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from hive_planner.launcher.config import LauncherConfig, load_config, normalize_project_path, save_config
from hive_planner.launcher.service import (
    _python_command,
    get_setup_status,
    open_in_cursor,
    run_project_ci_check,
    run_project_init,
    run_project_map_sync,
    summarize_project,
)


def test_open_in_cursor_rejects_non_hive_project(tmp_path: Path) -> None:
    result = open_in_cursor(tmp_path)
    assert result["ok"] is False
    assert "START_HERE" in result["error"]


def test_open_in_cursor_launches_when_cursor_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    from hive_planner.project_profile import write_project_profile

    write_project_profile(project, profile="minimal", project_name="App")

    launched: dict[str, list] = {"cmd": []}

    def fake_popen(cmd, **kwargs):
        launched["cmd"] = cmd
        return None

    monkeypatch.setattr("hive_planner.launcher.service.find_cursor_executable", lambda: r"C:\Cursor\Cursor.exe")
    monkeypatch.setattr("hive_planner.launcher.service.subprocess.Popen", fake_popen)

    result = open_in_cursor(project)
    assert result["ok"] is True
    assert launched["cmd"][0] == r"C:\Cursor\Cursor.exe"
    assert launched["cmd"][1] == str(project.resolve())


def test_open_in_cursor_errors_when_cursor_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    monkeypatch.setattr("hive_planner.launcher.service.find_cursor_executable", lambda: None)
    result = open_in_cursor(project)
    assert result["ok"] is False
    assert "Cursor not found" in result["error"]


def test_load_config_prunes_missing_recent_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    alive = tmp_path / "alive"
    alive.mkdir()
    gone = tmp_path / "gone"
    cfg_dir = tmp_path / "cfg"
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    save_config(
        LauncherConfig(
            active_project=str(gone),
            recent_projects=[str(alive), str(gone)],
            project_profiles={str(alive): "minimal", str(gone): "full"},
        )
    )
    loaded = load_config()
    assert loaded.recent_projects == [str(alive.resolve())]
    assert loaded.active_project == ""
    assert str(gone.resolve()) not in loaded.project_profiles
    assert loaded.project_profiles[str(alive.resolve())] == "minimal"


def test_run_project_ci_check_rejects_invalid_project(tmp_path: Path) -> None:
    result = run_project_ci_check(tmp_path)
    assert result["ok"] is False
    assert "START_HERE" in result["error"]


def test_run_project_map_sync_rejects_invalid_project(tmp_path: Path) -> None:
    result = run_project_map_sync(tmp_path)
    assert result["ok"] is False
    assert "START_HERE" in result["error"]


def test_map_sync_done_formats_success() -> None:
    from hive_planner.launcher.app import HivePlannerApp
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.home_log = type("L", (), {"configure": lambda *a, **k: None})()
    lines: list[str] = []
    app._append_log = lambda _w, text: lines.append(text)  # type: ignore[method-assign]
    app._map_sync_done(
        {
            "ok": True,
            "project_added": ["a"],
            "test_added": [],
            "project_updated": ["b"],
            "test_updated": [],
        }
    )
    root.destroy()
    assert lines == ["Impact maps synced: 1 added, 1 updated."]


def test_config_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / "appdata"
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    proj = tmp_path / "proj-a"
    proj.mkdir()
    original = LauncherConfig(
        onboarding_complete=True,
        hive_planner_root=str(tmp_path),
        python_executable="py -3.11",
        recent_projects=[str(proj)],
    )
    save_config(original)
    loaded = load_config()
    assert loaded.onboarding_complete is True
    assert loaded.hive_planner_root == str(tmp_path)
    assert loaded.recent_projects == [str(proj.resolve())]


def test_add_recent_project_dedupes_and_stores_profile(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (b / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (b / "pyproject.toml").write_text("[project]\nname='b'\n", encoding="utf-8")
    cfg = LauncherConfig(recent_projects=[str(a), str(b)])
    cfg.add_recent_project(b)
    assert cfg.recent_projects[0] == str(b.resolve())
    assert len(cfg.recent_projects) == 2
    assert cfg.project_profiles[str(b.resolve())] == "full"


def test_recent_selection_uses_path_index_not_label_parse(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    import tkinter as tk

    tricky = tmp_path / "weird  [full]-name"
    tricky.mkdir()
    (tricky / "START_HERE.md").write_text("# start\n", encoding="utf-8")

    root = tk.Tk()
    root.withdraw()
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(recent_projects=[str(tricky)])
    app.root = root
    app._recent_project_paths = [str(tricky.resolve())]
    app.recent_list = type(
        "L",
        (),
        {"curselection": lambda self: (0,), "get": lambda self, i: f"{tricky}  [minimal]"},
    )()

    activated: dict[str, str] = {}

    def fake_add_recent(project_root: Path) -> None:
        activated["path"] = str(project_root)

    app.config.add_recent_project = fake_add_recent  # type: ignore[method-assign]
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    original_info = app_mod.messagebox.showinfo
    original_load = app_mod.load_config
    original_save = app_mod.save_config
    app_mod.messagebox.showinfo = lambda *a, **k: None
    app_mod.load_config = lambda: app.config
    app_mod.save_config = lambda cfg: None
    try:
        app._on_select_recent()
    finally:
        app_mod.messagebox.showinfo = original_info
        app_mod.load_config = original_load
        app_mod.save_config = original_save
    root.destroy()

    assert activated["path"] == str(tricky.resolve())


def test_load_config_normalizes_project_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "my-app"
    project.mkdir()
    cfg_dir = tmp_path / "cfg"
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    raw = str(project).replace("\\", "/") + "/"
    save_config(
        LauncherConfig(
            active_project=raw,
            recent_projects=[raw],
            project_profiles={raw: "minimal"},
        )
    )
    loaded = load_config()
    expected = str(project.resolve())
    assert loaded.active_project == expected
    assert loaded.recent_projects == [expected]
    assert loaded.project_profiles.get(expected) == "minimal"


def test_summarize_includes_profile(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    from hive_planner.project_profile import write_project_profile

    write_project_profile(project, profile="minimal", project_name="Demo")
    summary = summarize_project(project)
    assert summary.ok is True
    assert summary.bootstrap_profile == "minimal"
    assert summary.project_name == "Demo"


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
    app._recent_project_paths = [str(missing)]

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


def test_console_python_pyw_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher import __main__ as main_mod

    class PyExe:
        def is_file(self) -> bool:
            return True

        def __str__(self) -> str:
            return r"C:\Tools\py.exe"

    class FakeExe:
        name = "pyw.exe"

        def with_name(self, child: str):
            if child == "py.exe":
                return PyExe()
            return self

    monkeypatch.setattr(main_mod.sys, "executable", r"C:\Tools\pyw.exe")
    monkeypatch.setattr(main_mod, "Path", lambda _p: FakeExe())
    assert main_mod._console_python() == r"C:\Tools\py.exe"


def test_ensure_installed_exits_when_pip_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from hive_planner.launcher import __main__ as main_mod

    repo = tmp_path / "hive"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='hive-planner'\n", encoding="utf-8")
    monkeypatch.setattr(main_mod, "_repo_root", lambda: repo)
    monkeypatch.setattr(main_mod, "_package_installed", lambda: False)
    monkeypatch.setattr(
        main_mod.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 1, "stdout": "", "stderr": "pip boom"})(),
    )
    monkeypatch.setattr(main_mod, "_show_startup_error", lambda msg, detail="": (_ for _ in ()).throw(SystemExit(1)))

    with pytest.raises(SystemExit):
        main_mod.ensure_installed()


def test_console_visible_tracks_attachment_not_parent_console(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher import console_win as cw

    cw._console_attached = False
    monkeypatch.setattr(cw, "console_available", lambda: True)

    class FakeKernel:
        @staticmethod
        def GetConsoleWindow():
            return 1  # parent console present (e.g. dev launch)

        @staticmethod
        def AllocConsole():
            return 1

        @staticmethod
        def FreeConsole():
            return 1

    import ctypes

    monkeypatch.setattr(ctypes, "windll", type("W", (), {"kernel32": FakeKernel})())
    assert cw.is_console_visible() is False
    # Parent console present (e.g. dev launch) — visible but not app-owned.
    assert cw.show_console() is True
    assert cw.is_console_visible() is False
    assert cw.hide_console() is False

    cw._console_attached = False
    calls = {"alloc": 0, "free": 0, "has_console": False}

    class AllocKernel:
        @staticmethod
        def GetConsoleWindow():
            return 1 if calls["has_console"] else 0

        @staticmethod
        def AllocConsole():
            calls["alloc"] += 1
            calls["has_console"] = True
            return 1

        @staticmethod
        def FreeConsole():
            calls["free"] += 1
            calls["has_console"] = False
            return 1

    monkeypatch.setattr(ctypes, "windll", type("W", (), {"kernel32": AllocKernel})())
    assert cw.show_console() is True
    assert cw.is_console_visible() is True
    assert cw.hide_console() is True
    assert cw.is_console_visible() is False
    assert calls["alloc"] == 1
    assert calls["free"] == 1
    cw._console_attached = False


def test_toggle_console_keeps_show_label_for_parent_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher import console_win as cw
    from hive_planner.launcher.app import HivePlannerApp

    cw._console_attached = False
    monkeypatch.setattr(cw, "console_available", lambda: True)

    class FakeKernel:
        @staticmethod
        def GetConsoleWindow():
            return 1

    import ctypes

    monkeypatch.setattr(ctypes, "windll", type("W", (), {"kernel32": FakeKernel})())

    class FakeBtn:
        text = "Show console"

        def cget(self, key: str) -> str:
            return self.text

        def config(self, **kwargs) -> None:
            if "text" in kwargs:
                self.text = kwargs["text"]

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.console_btn = FakeBtn()
    app._on_toggle_console()
    assert app.console_btn.text == "Show console"
    cw._console_attached = False


def test_console_available_on_windows_only() -> None:
    import sys

    from hive_planner.launcher import console_win

    assert console_win.console_available() == (sys.platform == "win32")

