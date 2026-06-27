from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import subprocess
import sys

import pytest

from hive_planner.launcher.config import LauncherConfig, load_config, normalize_project_path, save_config
from hive_planner.launcher.service import (
    PythonInstallation,
    _hidden_subprocess_kwargs,
    _python_command,
    _py_launcher_commands,
    _version_supported,
    auto_complete_onboarding_if_ready,
    clear_python_probe_cache,
    discover_python_installations,
    format_python_scan_report,
    get_setup_status,
    open_in_cursor,
    probe_python_command,
    run_install,
    run_project_ci_check,
    run_project_init,
    run_project_map_sync,
    summarize_project,
)


def test_version_supported() -> None:
    assert _version_supported("3.11.4") is True
    assert _version_supported("3.10.0") is True
    assert _version_supported("3.9.13") is False


def test_format_python_scan_report_empty() -> None:
    report = format_python_scan_report([])
    assert "No Python installations found" in report


def test_format_python_scan_report_lists_entries() -> None:
    report = format_python_scan_report(
        [
            PythonInstallation(
                command="py -3.11",
                version="3.11.4",
                executable=r"C:\Python311\python.exe",
                supported=True,
            )
        ]
    )
    assert "3.11.4" in report
    assert "py -3.11" in report


def test_discover_python_installations_includes_current() -> None:
    installs = discover_python_installations()
    assert installs
    assert any(Path(inst.executable).resolve() == Path(sys.executable).resolve() for inst in installs)


def test_py_launcher_commands_parses_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exe311 = tmp_path / "python311.exe"
    exe311.write_text("", encoding="utf-8")
    monkeypatch.setattr("hive_planner.launcher.service.sys.platform", "win32")
    monkeypatch.setattr("hive_planner.launcher.service.shutil.which", lambda name: "py" if name == "py" else None)
    monkeypatch.setattr(
        "hive_planner.launcher.service.subprocess.run",
        lambda *a, **k: type(
            "R",
            (),
            {
                "returncode": 0,
                "stdout": f" -V:3.11 *        {exe311}\n -V:3.12          C:\\Python312\\python.exe\n",
                "stderr": "",
            },
        )(),
    )
    commands = _py_launcher_commands()
    assert [str(exe311)] in commands
    assert ["py", "-3.11"] in commands
    assert ["py", "-3.12"] in commands


def test_probe_python_command_reads_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hive_planner.launcher.service.subprocess.run",
        lambda *a, **k: type(
            "R",
            (),
            {"returncode": 0, "stdout": "3.11.4\nC:\\Python311\\python.exe\n", "stderr": ""},
        )(),
    )
    clear_python_probe_cache()
    inst = probe_python_command(["py", "-3.11"], use_cache=False)
    assert inst is not None
    assert inst.version == "3.11.4"
    assert inst.supported is True
    assert inst.command == "py -3.11"


def test_probe_python_command_does_not_cache_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_run(*args, **kwargs):
        calls["count"] += 1
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "nope"})()

    monkeypatch.setattr("hive_planner.launcher.service.subprocess.run", fake_run)
    clear_python_probe_cache()
    assert probe_python_command(["py", "-3.11"], use_cache=True) is None
    assert probe_python_command(["py", "-3.11"], use_cache=True) is None
    assert calls["count"] == 2


def test_probe_python_command_caches_results(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_run(*args, **kwargs):
        calls["count"] += 1
        return type("R", (), {"returncode": 0, "stdout": "3.11.4\nC:\\Python311\\python.exe\n", "stderr": ""})()

    monkeypatch.setattr("hive_planner.launcher.service.subprocess.run", fake_run)
    clear_python_probe_cache()
    first = probe_python_command(["py", "-3.11"])
    second = probe_python_command(["py", "-3.11"])
    assert first is not None
    assert second == first
    assert calls["count"] == 1


def test_hidden_subprocess_kwargs_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("hive_planner.launcher.service.sys.platform", "win32")
    kwargs = _hidden_subprocess_kwargs()
    assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert kwargs["startupinfo"].wShowWindow == subprocess.SW_HIDE


def test_probe_python_uses_hidden_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return type("R", (), {"returncode": 0, "stdout": "3.11.4\nC:\\Python311\\python.exe\n", "stderr": ""})()

    monkeypatch.setattr("hive_planner.launcher.service.subprocess.run", fake_run)
    monkeypatch.setattr("hive_planner.launcher.service.sys.platform", "win32")
    clear_python_probe_cache()
    inst = probe_python_command(["py", "-3.11"], use_cache=False)
    assert inst is not None
    assert captured.get("creationflags") == subprocess.CREATE_NO_WINDOW


def test_discover_python_reports_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, int, str]] = []

    monkeypatch.setattr(
        "hive_planner.launcher.service._collect_probe_candidates",
        lambda: [["py", "-3.11"], [sys.executable]],
    )
    monkeypatch.setattr(
        "hive_planner.launcher.service.probe_python_command",
        lambda _cmd, use_cache=True: PythonInstallation(
            command="py -3.11",
            version="3.11.4",
            executable=sys.executable,
            supported=True,
        ),
    )
    discover_python_installations(on_progress=lambda c, t, m: calls.append((c, t, m)))
    assert calls[0][2] == "Collecting candidates"
    assert calls[-1] == (2, 2, "Done")
    assert any(msg == "py -3.11" for _, _, msg in calls)


def test_python_scan_ignores_duplicate_clicks() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._python_scan_active = True
    app._run_bg = lambda work, done: (_ for _ in ()).throw(AssertionError("should not run"))  # type: ignore[method-assign]
    app._on_scan_python()


def test_python_scan_resets_when_ui_rebuilds() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._bg_generation = 0
    app._python_scan_active = True
    app._invalidate_bg_callbacks()
    assert app._python_scan_active is False


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


def test_save_config_clears_probe_cache_when_python_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_dir = tmp_path / "cfg"
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    cleared: list[bool] = []
    monkeypatch.setattr(
        "hive_planner.launcher.service.clear_python_probe_cache",
        lambda: cleared.append(True),
    )

    save_config(LauncherConfig(python_executable="py -3.11"))
    save_config(LauncherConfig(python_executable="py -3.11", hive_planner_root=str(tmp_path)))
    assert cleared == []

    save_config(LauncherConfig(python_executable="py -3.12"))
    assert cleared == [True]


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


def test_load_user_guide_reads_scripts_readme(tmp_path: Path) -> None:
    from hive_planner.launcher.user_guide import load_user_guide, user_guide_path

    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    guide = scripts / "README.md"
    guide.write_text("# Test guide\n\nWhat is Hive Planner?\n", encoding="utf-8")
    cfg = LauncherConfig(hive_planner_root=str(hive))

    assert user_guide_path(cfg) == guide.resolve()
    text = load_user_guide(cfg)
    assert "Test guide" in text
    assert "What is Hive Planner?" in text


def test_load_user_guide_fallback_when_missing(tmp_path: Path) -> None:
    from hive_planner.launcher.user_guide import load_user_guide

    cfg = LauncherConfig(hive_planner_root=str(tmp_path / "missing"))
    text = load_user_guide(cfg)
    assert "Hive Planner" in text
    assert "First time?" in text


def test_auto_complete_onboarding_when_setup_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hive = tmp_path / "hive"
    hive.mkdir()
    (hive / "pyproject.toml").write_text("[project]\nname='hive-planner'\n", encoding="utf-8")
    cfg = LauncherConfig(
        hive_planner_root=str(hive),
        python_executable="py -3.11",
        onboarding_complete=False,
    )
    monkeypatch.setattr(
        "hive_planner.launcher.service.probe_python_command",
        lambda _cmd: PythonInstallation(
            command="py -3.11",
            version="3.11.4",
            executable=r"C:\Python311\python.exe",
            supported=True,
        ),
    )
    monkeypatch.setattr("hive_planner.launcher.service.importlib.metadata.version", lambda _name: "1.2.0")

    assert auto_complete_onboarding_if_ready(cfg) is True
    assert cfg.onboarding_complete is True


def test_auto_complete_onboarding_skips_when_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = LauncherConfig(onboarding_complete=False, hive_planner_root=str(tmp_path))
    monkeypatch.setattr(
        "hive_planner.launcher.service.get_setup_status",
        lambda _cfg: type(
            "S",
            (),
            {
                "python_ok": True,
                "hive_root_ok": True,
                "hive_installed": False,
            },
        )(),
    )
    assert auto_complete_onboarding_if_ready(cfg) is False
    assert cfg.onboarding_complete is False


def test_load_config_auto_completes_onboarding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hive = tmp_path / "hive"
    hive.mkdir()
    (hive / "pyproject.toml").write_text("[project]\nname='hive-planner'\n", encoding="utf-8")
    cfg_dir = tmp_path / "cfg"
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    save_config(
        LauncherConfig(
            hive_planner_root=str(hive),
            python_executable="py -3.11",
            onboarding_complete=False,
        )
    )
    monkeypatch.setattr(
        "hive_planner.launcher.service.probe_python_command",
        lambda _cmd: PythonInstallation(
            command="py -3.11",
            version="3.11.4",
            executable=r"C:\Python311\python.exe",
            supported=True,
        ),
    )
    monkeypatch.setattr("hive_planner.launcher.service.importlib.metadata.version", lambda _name: "1.2.0")

    loaded = load_config()
    assert loaded.onboarding_complete is True


def test_map_sync_done_formats_success() -> None:
    from hive_planner.launcher.app import HivePlannerApp

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
    assert lines == ["Impact maps synced: 1 added, 1 updated."]


def test_stale_scan_callback_cleans_progress_state() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._bg_generation = 1
    app._python_scan_active = True
    hidden = {"called": False}
    app._hide_python_scan_progress = lambda: hidden.update(called=True)  # type: ignore[method-assign]

    generation = 0

    def finish() -> None:
        if generation != app._bg_generation:
            if app._python_scan_active:
                app._python_scan_active = False
                app._hide_python_scan_progress()
            return

    finish()
    assert app._python_scan_active is False
    assert hidden["called"] is True


def test_run_install_uses_hidden_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hive_root = tmp_path / "hive"
    hive_root.mkdir()
    (hive_root / "pyproject.toml").write_text("[project]\nname='hive-planner'\n", encoding="utf-8")
    captured: dict = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr("hive_planner.launcher.service.subprocess.run", fake_run)
    monkeypatch.setattr("hive_planner.launcher.service.sys.platform", "win32")
    monkeypatch.setattr("hive_planner.launcher.service.importlib.metadata.version", lambda _name: "1.2.0")

    cfg = LauncherConfig(hive_planner_root=str(hive_root), python_executable="py -3.11")
    result = run_install(cfg)
    assert result.ok is True
    assert captured.get("creationflags") == subprocess.CREATE_NO_WINDOW


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


def test_remove_recent_project_updates_active_and_profiles(tmp_path: Path) -> None:
    alive = tmp_path / "alive"
    other = tmp_path / "other"
    alive.mkdir()
    other.mkdir()
    cfg = LauncherConfig(
        active_project=str(alive.resolve()),
        recent_projects=[str(alive.resolve()), str(other.resolve())],
        project_profiles={str(alive.resolve()): "full", str(other.resolve()): "minimal"},
    )
    assert cfg.remove_recent_project(alive) is True
    assert cfg.recent_projects == [str(other.resolve())]
    assert cfg.active_project == ""
    assert str(alive.resolve()) not in cfg.project_profiles
    assert cfg.remove_recent_project(tmp_path / "missing") is False


def test_delete_project_profile_removes_metadata(tmp_path: Path) -> None:
    from hive_planner.project_profile import delete_project_profile, project_meta_path, write_project_profile

    project = tmp_path / "demo"
    project.mkdir()
    write_project_profile(project, profile="minimal", project_name="Demo")
    meta = project_meta_path(project)
    assert meta.is_file()

    ok, msg = delete_project_profile(project)
    assert ok is True
    assert not meta.is_file()
    assert not (project / ".hive").exists()

    ok2, msg2 = delete_project_profile(project)
    assert ok2 is False
    assert "No Hive profile" in msg2


def test_bind_mousewheel_uses_widget_binding_not_bind_all() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    bindings: dict[str, list[str]] = {"bind": [], "bind_all": []}

    class FakeListbox:
        def bind(self, seq, _func) -> None:
            bindings["bind"].append(seq)

        def bind_all(self, seq, _func) -> None:
            bindings["bind_all"].append(seq)

    app._bind_mousewheel(FakeListbox())  # type: ignore[arg-type]
    assert "<MouseWheel>" in bindings["bind"]
    assert bindings["bind_all"] == []


def test_format_recent_project_label_uses_folder_name_only() -> None:
    from hive_planner.launcher.app import format_recent_project_label

    path = r"F:\DRIVE DOWNLOADS\HIVE CODE\My Project"
    assert format_recent_project_label(path) == "My Project"
    assert format_recent_project_label(path, "full") == "My Project  [full]"


def test_recent_selection_uses_path_index_not_label_parse(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    tricky = tmp_path / "weird  [full]-name"
    tricky.mkdir()
    (tricky / "START_HERE.md").write_text("# start\n", encoding="utf-8")

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(recent_projects=[str(tricky)])
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


def test_get_setup_status_uses_configured_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hive_planner.launcher.service.probe_python_command",
        lambda _cmd: PythonInstallation(
            command="py -3.12",
            version="3.12.1",
            executable=r"C:\Python312\python.exe",
            supported=True,
        ),
    )
    cfg = LauncherConfig(python_executable="py -3.12")
    status = get_setup_status(cfg)
    assert status.python_ok is True
    assert "3.12.1" in status.python_version
    assert "py -3.12" in status.python_version


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

    missing = tmp_path / "gone"
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(recent_projects=[str(missing)])
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

    assert Box.calls
    assert "Directory not found" in Box.calls[0][1]
    assert app.config.active_project == ""


def test_recent_double_click_opens_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    project = tmp_path / "demo-app"
    project.mkdir()
    opened: list[str] = []
    monkeypatch.setattr(
        "hive_planner.launcher.app.open_path_in_explorer",
        lambda path: opened.append(str(path)) or {"ok": True, "path": str(path)},
    )

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._recent_project_paths = [str(project)]
    app.recent_list = type("L", (), {"curselection": lambda self: (0,)})()

    app._on_recent_double_click()
    assert opened == [str(project.resolve())]


def test_ci_check_done_clears_stale_steps_on_error() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.home_log = type("L", (), {"configure": lambda *a, **k: None})()
    app.ci_list = type(
        "L",
        (),
        {
            "items": ["old"],
            "delete": lambda self, a, b: setattr(self, "items", []),
            "insert": lambda self, *a, **k: None,
        },
    )()
    lines: list[str] = []
    app._append_log = lambda _w, text: lines.append(text)  # type: ignore[method-assign]
    app._ci_check_done({"ok": False, "error": "Not a Hive project (missing START_HERE.md)"})
    assert app.ci_list.items == []
    assert "START_HERE" in lines[0]


def test_ci_check_report_is_not_bg_error() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    report = {"ok": False, "steps": [{"name": "pytest", "ok": False, "detail": "1 failed"}]}
    assert app._is_bg_error(report) is False
    assert app._is_bg_error({"ok": False, "error": "boom"}) is True


def test_install_result_failure_dict() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    assert app._result_failed({"ok": False, "error": "pip failed"}) is True
    assert app._result_failed({"ok": True}) is False
    assert "pip failed" in app._result_detail({"ok": False, "error": "pip failed"})


def test_bg_generation_invalidates_stale_callbacks() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._bg_generation = 0
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


def test_ensure_installed_uses_hidden_subprocess(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from hive_planner.launcher import __main__ as main_mod

    repo = tmp_path / "hive"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='hive-planner'\n", encoding="utf-8")
    captured: dict = {}
    install_checks = iter([False, True])
    monkeypatch.setattr(main_mod, "_repo_root", lambda: repo)
    monkeypatch.setattr(main_mod, "_package_installed", lambda: next(install_checks))

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(main_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(main_mod.sys, "platform", "win32")
    main_mod.ensure_installed()
    assert captured.get("creationflags") == subprocess.CREATE_NO_WINDOW


def test_console_visible_tracks_attachment_not_parent_console(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher import console_win as cw

    cw._console_attached = False
    cw._console_visible = False
    monkeypatch.setattr(cw, "console_available", lambda: True)

    class FakeKernel:
        @staticmethod
        def GetConsoleWindow():
            return 1  # parent console present (e.g. dev launch)

        @staticmethod
        def AllocConsole():
            return 1

    class FakeUser:
        @staticmethod
        def ShowWindow(_hwnd, _cmd):
            return 1

    import ctypes

    monkeypatch.setattr(
        ctypes,
        "windll",
        type("W", (), {"kernel32": FakeKernel, "user32": FakeUser})(),
    )
    assert cw.is_console_visible() is False
    # Parent console present (e.g. dev launch) — visible but not app-owned.
    assert cw.show_console() is True
    assert cw.is_console_visible() is False
    assert cw.hide_console() is False

    cw._console_attached = False
    cw._console_visible = False
    calls = {"alloc": 0, "show": 0, "hide": 0, "has_console": False, "visible": False}

    class AllocKernel:
        @staticmethod
        def GetConsoleWindow():
            return 1 if calls["has_console"] else 0

        @staticmethod
        def AllocConsole():
            calls["alloc"] += 1
            calls["has_console"] = True
            calls["visible"] = True
            return 1

    class AllocUser:
        @staticmethod
        def ShowWindow(_hwnd, cmd):
            if cmd == cw.SW_SHOW:
                calls["show"] += 1
                calls["visible"] = True
            elif cmd == cw.SW_HIDE:
                calls["hide"] += 1
                calls["visible"] = False
            return 1

    monkeypatch.setattr(
        ctypes,
        "windll",
        type("W", (), {"kernel32": AllocKernel, "user32": AllocUser})(),
    )
    assert cw.show_console() is True
    assert cw.is_console_visible() is True
    assert calls["alloc"] == 1
    assert calls["show"] == 1
    assert cw.hide_console() is True
    assert cw.is_console_visible() is False
    assert calls["hide"] == 1
    assert cw.show_console() is True
    assert cw.is_console_visible() is True
    assert calls["alloc"] == 1
    assert calls["show"] == 2
    cw._console_attached = False
    cw._console_visible = False


def test_on_explore_shows_error_for_missing_path(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    missing = tmp_path / "gone"
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=str(missing))

    errors: list[tuple[str, str]] = []

    import hive_planner.launcher.app as app_mod

    original = app_mod.messagebox.showerror
    app_mod.messagebox.showerror = lambda title, message: errors.append((title, message))
    try:
        app._on_explore()
    finally:
        app_mod.messagebox.showerror = original

    assert errors
    assert errors[0][0] == "Open in Explorer"
    assert "exist" in errors[0][1].lower()


def test_toggle_console_keeps_show_label_for_parent_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher import console_win as cw
    from hive_planner.launcher.app import HivePlannerApp

    cw._console_attached = False
    cw._console_visible = False
    monkeypatch.setattr(cw, "console_available", lambda: True)

    class FakeKernel:
        @staticmethod
        def GetConsoleWindow():
            return 1

    class FakeUser:
        @staticmethod
        def ShowWindow(_hwnd, _cmd):
            return 1

    import ctypes

    monkeypatch.setattr(
        ctypes,
        "windll",
        type("W", (), {"kernel32": FakeKernel, "user32": FakeUser})(),
    )

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
    cw._console_visible = False


def test_console_available_on_windows_only() -> None:
    import sys

    from hive_planner.launcher import console_win

    assert console_win.console_available() == (sys.platform == "win32")

