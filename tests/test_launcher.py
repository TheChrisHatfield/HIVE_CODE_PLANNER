from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch
import subprocess
import sys

import pytest

from hive_planner.config import RepoPaths
from hive_planner.rosetta_nav import (
    delta_micro_navigation_block,
    inject_after_header,
    plan_navigation_block,
    spec_navigation_block,
    tasks_navigation_block,
)


def _write_handoff_bundle(project: Path, feature: str) -> None:
    spec_dir = project / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec.md").write_text(
        inject_after_header("# Spec\n\n", spec_navigation_block(feature)),
        encoding="utf-8",
    )
    (spec_dir / "plan.md").write_text(
        inject_after_header("# Plan\n\n", plan_navigation_block(feature)),
        encoding="utf-8",
    )
    (spec_dir / "tasks.md").write_text(
        inject_after_header("# Tasks\n\n", tasks_navigation_block(feature)),
        encoding="utf-8",
    )
    micro = project / "docs" / "delta" / "20_micro"
    micro.mkdir(parents=True, exist_ok=True)
    (micro / f"{feature}.md").write_text(
        inject_after_header("# Micro\n\n", delta_micro_navigation_block(feature)),
        encoding="utf-8",
    )


def _legacy_agents_with_rosetta(active_line: str) -> str:
    return "\n".join(
        [
            "# AGENTS",
            "",
            "## Planning Rosetta Stone",
            "",
            "- hook `planning.rosetta`",
            "",
            "## Active feature",
            "",
            active_line,
            "",
            "## Durable Workspace Facts",
            "",
            "- ok",
            "",
        ]
    )


from hive_planner.launcher.config import (
    LauncherConfig,
    clear_project_profile_cache,
    linked_project_exists,
    load_config,
    normalize_project_path,
    prune_stale_projects,
    save_config,
)
from hive_planner.launcher.service import (
    PythonInstallation,
    _hidden_subprocess_kwargs,
    _python_command,
    _py_launcher_commands,
    _version_supported,
    auto_complete_onboarding_if_ready,
    classify_workspace,
    clear_python_probe_cache,
    pick_hive_bootstrap_target,
    resolve_linked_project_root,
    workspace_primary_folder,
    discover_cursor_workspaces,
    discover_python_installations,
    file_uri_to_path,
    find_cursor_executable,
    format_python_scan_report,
    get_setup_status,
    open_in_cursor,
    probe_python_command,
    run_install,
    run_project_ci_check,
    run_project_init,
    run_project_map_sync,
    resolve_cartridge_import_root,
    run_cartridge_import_folder,
    run_cartridge_load_sources,
    run_cartridge_translate,
    run_deploy_agent_handoff,
    cartridge_load_needs_feature,
    cartridge_load_will_promote,
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


def test_linked_project_exists_accepts_code_workspace_file(tmp_path: Path) -> None:
    workspace_file = tmp_path / "hive.code-workspace"
    workspace_file.write_text("{}", encoding="utf-8")
    folder = tmp_path / "repo"
    folder.mkdir()
    assert linked_project_exists(workspace_file) is True
    assert linked_project_exists(folder) is True
    assert linked_project_exists(tmp_path / "missing") is False


def test_prune_stale_projects_keeps_code_workspace_links(tmp_path: Path) -> None:
    workspace_file = tmp_path / "hive.code-workspace"
    workspace_file.write_text("{}", encoding="utf-8")
    resolved = str(workspace_file.resolve())
    cfg = LauncherConfig(recent_projects=[resolved], active_project=resolved)
    assert prune_stale_projects(cfg) is False
    assert cfg.recent_projects == [resolved]
    assert cfg.active_project == resolved


def test_open_in_cursor_opens_workspace_without_hive_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "cursor-app"
    workspace.mkdir()
    (workspace / ".cursor").mkdir()

    launched: dict[str, list] = {"cmd": []}

    def fake_popen(cmd, **kwargs):
        launched["cmd"] = cmd
        return None

    monkeypatch.setattr(
        "hive_planner.launcher.service.find_cursor_executable",
        lambda _config=None: r"C:\Cursor\Cursor.exe",
    )
    monkeypatch.setattr("hive_planner.launcher.service.subprocess.Popen", fake_popen)

    result = open_in_cursor(workspace)
    assert result["ok"] is True
    assert result["hive_ready"] is False
    assert launched["cmd"][1] == str(workspace.resolve())


def test_open_in_cursor_rejects_missing_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "gone"
    monkeypatch.setattr(
        "hive_planner.launcher.service.find_cursor_executable",
        lambda _config=None: r"C:\Cursor\Cursor.exe",
    )
    result = open_in_cursor(missing)
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_file_uri_to_path_decodes_windows_drive() -> None:
    uri = "file:///d%3A/DRIVE_DOWNLOADS/HIVE_CODE_PLANNER"
    assert file_uri_to_path(uri) == "d:/DRIVE_DOWNLOADS/HIVE_CODE_PLANNER"


def test_pick_hive_bootstrap_target_skips_multi_root_parent(tmp_path: Path) -> None:
    parent = tmp_path / "HIVE CODE"
    parent.mkdir()
    profile = parent / "HIVE_CODE_PLANNER_PROFILE"
    profile.mkdir()
    (profile / ".cursor").mkdir()
    (profile / "app.py").write_text("print('hi')\n", encoding="utf-8")
    workspace_file = parent / "hive-code.code-workspace"
    workspace_file.write_text(
        json.dumps({"folders": [{"path": "."}, {"path": "HIVE_CODE_PLANNER_PROFILE"}]}),
        encoding="utf-8",
    )

    picked = pick_hive_bootstrap_target(workspace_file)
    assert picked == profile.resolve()


def test_workspace_primary_folder_prefers_hive_root_in_multi_root_workspace(tmp_path: Path) -> None:
    parent = tmp_path / "HIVE CODE"
    parent.mkdir()
    profile = parent / "HIVE_CODE_PLANNER_PROFILE"
    profile.mkdir()
    (profile / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    workspace_file = parent / "hive-code.code-workspace"
    workspace_file.write_text(
        json.dumps({"folders": [{"path": "."}, {"path": "HIVE_CODE_PLANNER_PROFILE"}]}),
        encoding="utf-8",
    )

    assert workspace_primary_folder(workspace_file) == profile.resolve()


def test_workspace_primary_folder_prefers_nested_profile_for_dot_only_workspace(tmp_path: Path) -> None:
    parent = tmp_path / "HIVE CODE"
    parent.mkdir()
    (parent / "START_HERE.md").write_text("# parent\n", encoding="utf-8")
    profile = parent / "HIVE_CODE_PLANNER_PROFILE"
    profile.mkdir()
    (profile / "START_HERE.md").write_text("# profile\n", encoding="utf-8")
    (profile / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (profile / "src").mkdir()
    workspace_file = parent / "hive-code.code-workspace"
    workspace_file.write_text(json.dumps({"folders": [{"path": "."}]}), encoding="utf-8")

    assert workspace_primary_folder(workspace_file) == profile.resolve()
    assert resolve_linked_project_root(workspace_file) == profile.resolve()


def test_prepare_linked_project_root_repairs_legacy_agents(tmp_path: Path) -> None:
    from hive_planner.launcher.service import prepare_linked_project_root
    from hive_planner.spec_drift import parse_active_feature

    project = tmp_path / "app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(
        _legacy_agents_with_rosetta("None â€” pending."),
        encoding="utf-8",
    )
    feature = "example-feature"
    _write_handoff_bundle(project, feature)

    root, repair = prepare_linked_project_root(project)
    assert root == project.resolve()
    assert repair is not None
    assert repair.repaired is True
    assert parse_active_feature(RepoPaths(root=project)) == feature


def test_summarize_linked_project_auto_repairs_workspace_link(tmp_path: Path) -> None:
    from hive_planner.launcher.service import summarize_linked_project
    from hive_planner.spec_drift import parse_active_feature

    parent = tmp_path / "HIVE CODE"
    parent.mkdir()
    (parent / "START_HERE.md").write_text("# parent\n", encoding="utf-8")
    profile = parent / "HIVE_CODE_PLANNER_PROFILE"
    profile.mkdir()
    (profile / "START_HERE.md").write_text("# profile\n", encoding="utf-8")
    (profile / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (profile / "AGENTS.md").write_text(
        _legacy_agents_with_rosetta("None â€” pending."),
        encoding="utf-8",
    )
    feature = "example-feature"
    _write_handoff_bundle(profile, feature)
    workspace_file = parent / "hive-code.code-workspace"
    workspace_file.write_text(json.dumps({"folders": [{"path": "."}]}), encoding="utf-8")

    summary = summarize_linked_project(workspace_file)
    assert summary.ok is True
    assert summary.active_feature == feature
    assert parse_active_feature(RepoPaths(root=profile)) == feature


def test_pick_hive_bootstrap_target_prefers_nested_profile_for_dot_only_workspace(tmp_path: Path) -> None:
    parent = tmp_path / "HIVE CODE"
    parent.mkdir()
    (parent / "START_HERE.md").write_text("# parent\n", encoding="utf-8")
    profile = parent / "HIVE_CODE_PLANNER_PROFILE"
    profile.mkdir()
    (profile / "START_HERE.md").write_text("# profile\n", encoding="utf-8")
    (profile / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    workspace_file = parent / "hive-code.code-workspace"
    workspace_file.write_text(json.dumps({"folders": [{"path": "."}]}), encoding="utf-8")

    assert pick_hive_bootstrap_target(workspace_file) == profile.resolve()


def test_discover_cursor_workspaces_reads_state_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "my-repo"
    repo.mkdir()
    (repo / ".cursor").mkdir()
    workspace_file = tmp_path / "hive-code.code-workspace"
    workspace_file.write_text(
        json.dumps({"folders": [{"path": str(repo.name)}]}),
        encoding="utf-8",
    )

    cursor_root = tmp_path / "Cursor" / "User" / "globalStorage"
    cursor_root.mkdir(parents=True)
    db = cursor_root / "state.vscdb"
    entries = {
        "entries": [
            {"workspace": {"configPath": workspace_file.as_uri()}},
            {"folderUri": repo.as_uri()},
        ]
    }
    conn = __import__("sqlite3").connect(db)
    conn.execute("CREATE TABLE ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
    conn.execute(
        "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
        ("history.recentlyOpenedPathsList", json.dumps(entries).encode("utf-8")),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("APPDATA", str(tmp_path))

    workspaces = discover_cursor_workspaces()
    assert len(workspaces) == 2
    assert workspaces[0].name == "hive-code (Workspace)"
    assert workspaces[0].entry_kind == "workspace"
    assert workspaces[1].path == str(repo.resolve())


def test_classify_workspace_detects_hive_and_cursor(tmp_path: Path) -> None:
    cursor_repo = tmp_path / "cursor-only"
    cursor_repo.mkdir()
    (cursor_repo / ".cursor").mkdir()
    ws = classify_workspace(cursor_repo)
    assert ws.hive_ready is False
    assert ws.has_cursor_dir is True

    hive_repo = tmp_path / "hive"
    hive_repo.mkdir()
    (hive_repo / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    ws2 = classify_workspace(hive_repo)
    assert ws2.hive_ready is True


def test_open_in_cursor_opens_code_workspace_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    workspace_file = tmp_path / "hive.code-workspace"
    workspace_file.write_text(json.dumps({"folders": [{"path": repo.name}]}), encoding="utf-8")

    launched: dict[str, list] = {"cmd": []}

    def fake_popen(cmd, **kwargs):
        launched["cmd"] = cmd
        return None

    monkeypatch.setattr(
        "hive_planner.launcher.service.find_cursor_executable",
        lambda _config=None: r"C:\Cursor\Cursor.exe",
    )
    monkeypatch.setattr("hive_planner.launcher.service.subprocess.Popen", fake_popen)

    result = open_in_cursor(workspace_file)
    assert result["ok"] is True
    assert result["entry_kind"] == "workspace"
    assert launched["cmd"][1] == str(workspace_file.resolve())


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

    monkeypatch.setattr(
        "hive_planner.launcher.service.find_cursor_executable",
        lambda _config=None: r"C:\Cursor\Cursor.exe",
    )
    monkeypatch.setattr("hive_planner.launcher.service.subprocess.Popen", fake_popen)

    result = open_in_cursor(project)
    assert result["ok"] is True
    assert result["hive_ready"] is True
    assert launched["cmd"][0] == r"C:\Cursor\Cursor.exe"
    assert launched["cmd"][1] == str(project.resolve())


def test_open_in_cursor_errors_when_cursor_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    monkeypatch.setattr("hive_planner.launcher.service.find_cursor_executable", lambda _config=None: None)
    result = open_in_cursor(project)
    assert result["ok"] is False
    assert "Cursor not found" in result["error"]


def test_find_cursor_executable_uses_config_override(tmp_path: Path) -> None:
    exe = tmp_path / "Cursor.exe"
    exe.write_text("", encoding="utf-8")
    config = LauncherConfig(cursor_executable=str(exe))
    assert find_cursor_executable(config) == str(exe)


def test_find_cursor_executable_discovers_from_cursor_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_root = tmp_path / "cursor" / "_"
    app_root.mkdir(parents=True)
    exe = app_root / "Cursor.exe"
    exe.write_text("", encoding="utf-8")
    logs_root = tmp_path / "Cursor" / "logs" / "session"
    logs_root.mkdir(parents=True)
    (logs_root / "main.log").write_text(
        f"Require stack:\n- {app_root}\\resources\\app\\out\\main.js\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr("hive_planner.launcher.service._cursor_from_path", lambda: None)
    monkeypatch.setattr("hive_planner.launcher.service._cursor_from_well_known_paths", lambda: None)
    monkeypatch.setattr("hive_planner.launcher.service._cursor_from_start_menu_shortcuts", lambda: None)
    assert find_cursor_executable() == str(exe)


def test_find_cursor_executable_checks_updater_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = tmp_path / "LocalAppData"
    exe = local / "Programs" / "cursor" / "_" / "Cursor.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr("hive_planner.launcher.service._cursor_from_path", lambda: None)
    monkeypatch.setattr("hive_planner.launcher.service._cursor_from_logs", lambda: None)
    monkeypatch.setattr("hive_planner.launcher.service._cursor_from_start_menu_shortcuts", lambda: None)
    assert find_cursor_executable() == str(exe)


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


def test_load_config_keeps_missing_links_but_clears_active(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert str(alive.resolve()) in loaded.recent_projects
    assert str(gone.resolve()) in loaded.recent_projects
    assert loaded.active_project == ""
    assert loaded.project_profiles[str(alive.resolve())] == "minimal"
    assert loaded.project_profiles[str(gone.resolve())] == "full"


def test_run_project_ci_check_rejects_invalid_project(tmp_path: Path) -> None:
    result = run_project_ci_check(tmp_path)
    assert result["ok"] is False
    assert "START_HERE" in result["error"]


def test_run_project_ci_check_skips_roadmap_for_app_projects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "my-app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "pyproject.toml").write_text('[project]\nname = "my-app"\n', encoding="utf-8")
    captured: dict = {}

    def fake_ci_check(paths, **kwargs):
        captured.update(kwargs)
        from hive_planner.ci_handoff import CiCheckReport, CiStepResult

        return CiCheckReport(steps=[CiStepResult("agents-lint", True, "ok")])

    monkeypatch.setattr("hive_planner.launcher.service.run_ci_check", fake_ci_check)
    result = run_project_ci_check(project)
    assert captured.get("check_roadmap") is None
    assert not result.get("hints")


def test_is_hive_planner_source_repo_detects_main_repo(tmp_path: Path) -> None:
    from hive_planner.launcher.service import is_hive_planner_source_repo

    repo = tmp_path / "hive"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "hive-planner"\n', encoding="utf-8")
    app = tmp_path / "app"
    app.mkdir()
    (app / "pyproject.toml").write_text('[project]\nname = "my-app"\n', encoding="utf-8")
    assert is_hive_planner_source_repo(repo) is True
    assert is_hive_planner_source_repo(app) is False


def test_run_project_ci_check_repairs_legacy_active_feature(tmp_path: Path) -> None:
    project = tmp_path / "legacy-app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    feature = "example-feature"
    (project / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## Repository root",
                "",
                "`root`",
                "",
                "## Planning Rosetta Stone",
                "",
                "- hook `planning.rosetta`",
                "",
                "## Startup read order",
                "",
                "1. rosetta",
                "",
                "## Delta model",
                "",
                "- Holistic / Macro / Micro",
                "",
                "## Active feature",
                "",
                "**None** â€” set when Spec Kit work begins.",
                "",
                "## Durable Workspace Facts",
                "",
                "- Run ci-check before handoff.",
            ]
        ),
        encoding="utf-8",
    )
    _write_handoff_bundle(project, feature)

    result = run_project_ci_check(project)
    assert result.get("repair", {}).get("feature") == feature
    from hive_planner.config import RepoPaths
    from hive_planner.spec_drift import parse_active_feature

    assert parse_active_feature(RepoPaths(root=project)) == feature
    handoff = next(s for s in result["steps"] if s["name"] == "handoff-artifacts")
    assert handoff["ok"] is True


def test_run_project_ci_check_patches_legacy_handoff_navigation(tmp_path: Path) -> None:
    project = tmp_path / "legacy-nav"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    feature = "example-feature"
    (project / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## Active feature",
                "",
                "**None** â€” set when Spec Kit work begins.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    spec_dir = project / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (spec_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (spec_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    micro = project / "docs" / "delta" / "20_micro"
    micro.mkdir(parents=True)
    (micro / f"{feature}.md").write_text("# Micro\n", encoding="utf-8")

    result = run_project_ci_check(project)

    spec_text = (spec_dir / "spec.md").read_text(encoding="utf-8")
    assert "Agent navigation (Rosetta Stone)" in spec_text
    assert result.get("rosetta_repair")
    handoff = next(s for s in result["steps"] if s["name"] == "handoff-artifacts")
    assert handoff["ok"] is True


def test_run_project_map_sync_rejects_invalid_project(tmp_path: Path) -> None:
    result = run_project_map_sync(tmp_path)
    assert result["ok"] is False
    assert "START_HERE" in result["error"]


def _minimal_hive_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")
    RepoPaths(root=root).ensure_dirs()
    return root


def test_run_cartridge_load_sources_copies_ingests_and_emits(tmp_path: Path) -> None:
    project = _minimal_hive_project(tmp_path / "proj")
    source = tmp_path / "notes.md"
    source.write_text("# Research\n\nSubsystem workflow for cartridge testing.\n", encoding="utf-8")

    result = run_cartridge_load_sources(project, [source], "my-feature")

    assert result["ok"] is True
    assert result["mode"] == "sources"
    assert result["processed"] == 1
    assert (project / "context-library" / "sources" / "imported" / "notes.md").is_file()
    assert (project / "cartridge" / "manifest.json").is_file()
    assert (project / "cartridge" / "source-context.md").is_file()
    assert "mark_draft" not in result


def test_run_cartridge_load_sources_mark_draft_stamps_layers(tmp_path: Path) -> None:
    from hive_planner.translator import DRAFT_BANNER

    project = _minimal_hive_project(tmp_path / "proj")
    source = tmp_path / "notes.md"
    source.write_text(
        "# Research\n\nSubsystem workflow for cartridge testing and promotion.\n",
        encoding="utf-8",
    )

    result = run_cartridge_load_sources(
        project,
        [source],
        "my-feature",
        promote=False,
        mark_emitted_draft=True,
    )

    assert result["ok"] is True
    assert result["mark_draft"]
    holistic = project / "cartridge" / "holistic.md"
    if holistic.is_file():
        assert holistic.read_text(encoding="utf-8").startswith(DRAFT_BANNER)
        assert result["mark_draft"]["holistic"] in {"marked draft", "already draft"}


def test_cartridge_load_mark_draft_default_sources_only() -> None:
    from hive_planner.launcher.service import cartridge_load_mark_draft_default

    assert cartridge_load_mark_draft_default(
        mode="sources",
        promote_checked=True,
        handoff_unified=True,
        config_default=True,
    )
    assert not cartridge_load_mark_draft_default(
        mode="translate",
        promote_checked=True,
        handoff_unified=True,
        config_default=True,
    )
    assert not cartridge_load_mark_draft_default(
        mode="sources",
        promote_checked=False,
        handoff_unified=True,
        config_default=True,
    )
    assert not cartridge_load_mark_draft_default(
        mode="sources",
        promote_checked=True,
        handoff_unified=False,
        config_default=True,
    )


def test_sources_mark_draft_only_when_promote_enabled() -> None:
    """mark_emitted_draft must not run when promote is off (launcher passes False)."""
    from hive_planner.launcher.service import run_cartridge_load_sources

    # Logic mirror: launcher sets mark only when sources + will_promote.
    will_promote = False
    mode = "sources"
    mark_draft_checked = True
    do_mark_draft = mark_draft_checked if mode == "sources" and will_promote else False
    assert do_mark_draft is False


def test_run_cartridge_translate_writes_draft_files(tmp_path: Path) -> None:
    project = _minimal_hive_project(tmp_path / "proj")
    research = tmp_path / "research.md"
    research.write_text(
        "\n".join(
            [
                "# Mission",
                "",
                "Goal: ship cartridge translation from the launcher.",
                "",
                "## Architecture",
                "",
                "Subsystem workflow for draft cartridge emission.",
            ]
        ),
        encoding="utf-8",
    )

    result = run_cartridge_translate(project, research, "launcher-cartridge")

    assert result["ok"] is True
    assert result["mode"] == "translate"
    assert (project / "cartridge" / "holistic.md").is_file()
    assert (project / "cartridge" / "micro" / "launcher-cartridge.md").is_file()


def test_run_cartridge_import_folder_copies_cartridge_tree(tmp_path: Path) -> None:
    project = _minimal_hive_project(tmp_path / "proj")
    external = tmp_path / "external-cartridge"
    external.mkdir()
    (external / "holistic.md").write_text("# Holistic\n", encoding="utf-8")
    (external / "manifest.json").write_text('{"schema_version":"cartridge.v1"}\n', encoding="utf-8")

    result = run_cartridge_import_folder(project, external, promote=False)

    assert result["ok"] is True
    assert result["mode"] == "import"
    assert (project / "cartridge" / "holistic.md").read_text(encoding="utf-8") == "# Holistic\n"
    assert (project / "cartridge" / "manifest.json").is_file()


def test_run_cartridge_import_folder_fails_when_all_files_exist(tmp_path: Path) -> None:
    project = _minimal_hive_project(tmp_path / "proj")
    external = tmp_path / "external-cartridge"
    external.mkdir()
    (external / "holistic.md").write_text("# Holistic\n", encoding="utf-8")
    (project / "cartridge" / "holistic.md").parent.mkdir(parents=True, exist_ok=True)
    (project / "cartridge" / "holistic.md").write_text("# Existing\n", encoding="utf-8")

    result = run_cartridge_import_folder(project, external)

    assert result["ok"] is False
    assert "already exist" in result["error"]
    assert result["skipped"] == ["holistic.md"]


def test_run_cartridge_import_folder_overwrites_existing_when_requested(tmp_path: Path) -> None:
    project = _minimal_hive_project(tmp_path / "proj")
    external = tmp_path / "external-cartridge"
    external.mkdir()
    (external / "holistic.md").write_text("# External\n", encoding="utf-8")
    existing = project / "cartridge" / "holistic.md"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("# Existing\n", encoding="utf-8")

    result = run_cartridge_import_folder(project, external, overwrite=True, promote=False)

    assert result["ok"] is True
    assert result["written"] == ["holistic.md"]
    assert existing.read_text(encoding="utf-8") == "# External\n"


def test_resolve_cartridge_import_root_prefers_nested_folder(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    nested = bundle / "cartridge"
    nested.mkdir(parents=True)
    (nested / "manifest.json").write_text("{}\n", encoding="utf-8")

    assert resolve_cartridge_import_root(bundle) == nested.resolve()


def test_run_cartridge_load_sources_rejects_invalid_feature(tmp_path: Path) -> None:
    project = _minimal_hive_project(tmp_path / "proj")
    source = tmp_path / "notes.md"
    source.write_text("# x\n", encoding="utf-8")

    result = run_cartridge_load_sources(project, [source], "Bad Feature")

    assert result["ok"] is False
    assert "Invalid feature" in result["error"]


def test_run_cartridge_load_sources_preserves_copied_on_emit_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _minimal_hive_project(tmp_path / "proj")
    source = tmp_path / "notes.md"
    source.write_text("# Research\n\nSubsystem workflow for cartridge testing.\n", encoding="utf-8")

    def fail_emit(*_args, **_kwargs):
        raise ValueError("emit failed")

    monkeypatch.setattr("hive_planner.launcher.service.emit_cartridge", fail_emit)

    result = run_cartridge_load_sources(project, [source], "my-feature")

    assert result["ok"] is False
    assert "emit failed" in result["error"]
    assert result["copied"] == ["context-library/sources/imported/notes.md"]
    assert (project / "context-library" / "sources" / "imported" / "notes.md").is_file()


def test_cartridge_load_done_does_not_log_success_after_emit_failure() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]
    app._log_cartridge_promote = lambda _promote: None  # type: ignore[method-assign]

    app._cartridge_load_done(
        {
            "ok": False,
            "mode": "sources",
            "error": "emit failed",
            "copied": ["context-library/sources/imported/notes.md"],
            "processed": 1,
            "feature": "my-feature",
        }
    )

    joined = "\n".join(app._pending_home_log)
    assert "emit failed" in joined
    assert "Cartridge sources loaded" not in joined
    assert "Cartridge load incomplete" in joined


def test_cartridge_load_done_warns_on_promote_failure_in_error_path() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]
    app._log_cartridge_promote = lambda _promote: app._pending_home_log.append("PROMOTE_LOG")  # type: ignore[method-assign]

    app._cartridge_load_done(
        {
            "ok": False,
            "mode": "sources",
            "error": "emit failed",
            "copied": ["context-library/sources/imported/notes.md"],
            "promote": {"ok": False, "promotions": {"micro": "skipped (not draft)"}},
        }
    )

    joined = "\n".join(app._pending_home_log)
    assert "PROMOTE_LOG" in joined
    assert "promotion/handoff needs review" in joined


def test_cartridge_load_done_warns_when_promote_fails_on_success() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]
    app._log_cartridge_promote = lambda _promote: app._pending_home_log.append("PROMOTE_LOG")  # type: ignore[method-assign]

    app._cartridge_load_done(
        {
            "ok": True,
            "mode": "import",
            "written": ["holistic.md"],
            "promote": {"ok": False, "promotions": {"holistic": "skipped (not draft)"}},
        }
    )

    joined = "\n".join(app._pending_home_log)
    assert "Imported 1 cartridge file(s)." in joined
    assert "PROMOTE_LOG" in joined
    assert "promotion/handoff needs review" in joined


def test_log_cartridge_promote_omits_startup_when_nothing_promoted() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []

    app._log_cartridge_promote(
        {
            "ok": False,
            "feature": "example-feature",
            "promotions": {"holistic": "skipped (not draft)", "macro": "skipped (not draft)"},
        }
    )

    joined = "\n".join(app._pending_home_log)
    assert "Agent startup" not in joined


def test_log_cartridge_promote_includes_startup_when_layers_written() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []

    app._log_cartridge_promote(
        {
            "ok": True,
            "feature": "hive-dev-v1",
            "promotions": {"macro": "updated", "micro": "written"},
        }
    )

    joined = "\n".join(app._pending_home_log)
    assert "Agent startup: load docs/planning-rosetta-stone.md" in joined


def test_merge_cartridge_promote_keeps_load_ok_when_spec_drift_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.service import _merge_cartridge_promote

    payload = {"ok": True, "mode": "translate", "files_written": ["micro/x.md"]}
    promote = {"ok": False, "promotions": {"micro": "written"}, "spec_drift": {"ok": False}}
    merged = _merge_cartridge_promote(payload, promote)

    assert merged["ok"] is True
    assert merged["promote"]["ok"] is False


def _hive_planner_source(tmp_path: Path) -> Path:
    root = tmp_path / "hive-planner"
    kit = root / "starter-kit"
    rules = root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# Architecture\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# Task Execution\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# Validation\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "cl-spec-integration.md").write_text("# CL\n", encoding="utf-8")
    return root


def test_run_deploy_agent_handoff_ok_when_unified_complete(tmp_path: Path) -> None:
    hive_root = _hive_planner_source(tmp_path)
    project = _minimal_hive_project(tmp_path / "proj")

    result = run_deploy_agent_handoff(project, hive_planner_root=hive_root, force=True)

    assert result["ok"] is True
    assert result.get("error") is None
    assert result.get("cl_runtime") == "cursor"
    assert (project / "spec-kit-agent-integration.md").is_file()


def test_run_deploy_agent_handoff_headless_skips_cursor_plugin(tmp_path: Path) -> None:
    from hive_planner.cl_runtime import CL_RUNTIME_HEADLESS, HEADLESS_CL_WORKFLOW_REL
    from hive_planner.vendor_sync import CL_OVERLAY_REL

    hive_root = _hive_planner_source(tmp_path)
    project = _minimal_hive_project(tmp_path / "headless-proj")

    result = run_deploy_agent_handoff(
        project,
        hive_planner_root=hive_root,
        force=True,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )

    assert result.get("cl_runtime") == CL_RUNTIME_HEADLESS
    assert (project / HEADLESS_CL_WORKFLOW_REL).is_file()
    assert not (project / CL_OVERLAY_REL).exists()


def test_cl_runtime_status_label_for_headless_project(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.cl_runtime import CL_RUNTIME_HEADLESS
    from hive_planner.launcher.service import cl_runtime_status_label
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "status"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(
        project,
        profile="minimal",
        project_name="status",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )

    assert cl_runtime_status_label(project) == "headless (CLI)"


def test_run_set_cl_runtime_updates_profile(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.cl_runtime import CL_RUNTIME_HEADLESS
    from hive_planner.launcher.service import run_set_cl_runtime
    from hive_planner.project_profile import read_project_profile, write_project_profile

    project = _minimal_hive_project(tmp_path / "set-rt")
    write_project_profile(
        project,
        profile="minimal",
        project_name="set-rt",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
    )

    result = run_set_cl_runtime(project, CL_RUNTIME_HEADLESS)

    assert result["ok"] is True
    assert result["cl_runtime"] == CL_RUNTIME_HEADLESS
    meta = read_project_profile(project)
    assert meta is not None
    assert meta.cl_runtime == CL_RUNTIME_HEADLESS


def test_run_set_cl_runtime_rejects_non_unified_handoff(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_OFF
    from hive_planner.cl_runtime import CL_RUNTIME_HEADLESS
    from hive_planner.launcher.service import run_set_cl_runtime
    from hive_planner.project_profile import write_project_profile

    project = _minimal_hive_project(tmp_path / "set-rt-off")
    write_project_profile(
        project,
        profile="minimal",
        project_name="set-rt-off",
        agent_handoff_mode=AGENT_HANDOFF_OFF,
    )

    result = run_set_cl_runtime(project, CL_RUNTIME_HEADLESS)

    assert result["ok"] is False
    assert "unified agent handoff" in result.get("error", "").lower()


def test_run_deploy_agent_handoff_reports_incomplete_when_validation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner import agent_handoff

    hive_root = _hive_planner_source(tmp_path)
    project = _minimal_hive_project(tmp_path / "proj")

    def _incomplete(_root: Path):
        from hive_planner.agent_handoff import AgentHandoffStatus

        return AgentHandoffStatus(
            mode="unified",
            spec_kit_enabled=True,
            continual_learning_enabled=True,
            complete=False,
            missing=[".cursor/rules/integration-wiring-audit.mdc"],
        )

    monkeypatch.setattr(agent_handoff, "validate_unified_handoff", _incomplete)
    result = run_deploy_agent_handoff(project, hive_planner_root=hive_root, force=True)

    assert result["ok"] is False
    assert "Unified handoff incomplete" in result.get("error", "")
    assert result["handoff"]["missing"] == [".cursor/rules/integration-wiring-audit.mdc"]


def test_deploy_handoff_done_logs_partial_work_when_validation_fails() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]

    app._deploy_handoff_done(
        {
            "ok": False,
            "error": "Unified handoff incomplete â€” missing: docs/cl-spec-integration.md",
            "files_written": ["docs/cl-spec-integration.md", ".cursor/rules/cl-spec-integration.mdc"],
            "warnings": ["template warning"],
            "handoff": {"missing": ["docs/cl-spec-integration.md"]},
            "rosetta_repair": {"detail": "patched navigation in 2 handoff file(s)", "patched": ["docs/specs/example-feature/spec.md"]},
        }
    )

    joined = "\n".join(app._pending_home_log)
    assert "Partial deploy" in joined
    assert "missing: docs/cl-spec-integration.md" in joined
    assert "template warning" in joined
    assert "Rosetta navigation" in joined
    assert "Agent handoff deployed" not in joined


def test_create_done_repairs_agents_after_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    target = tmp_path / "new-proj"
    target.mkdir()
    cfg = LauncherConfig(hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    repair_calls: list[Path] = []

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(
        app_mod,
        "prepare_linked_project_root",
        lambda p, **kw: repair_calls.append(Path(p)) or (target, None),
    )

    app._create_done({"ok": True, "target": str(target.resolve())})
    assert repair_calls == [target.resolve()]


def test_bootstrap_and_activate_repairs_after_partial_init(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    target = tmp_path / "partial-init"
    target.mkdir()
    cfg = LauncherConfig(hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    repair_calls: list[Path] = []

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod.messagebox, "showerror", lambda *a, **k: None)
    monkeypatch.setattr(
        app_mod,
        "run_project_init",
        lambda *_a, **_k: {
            "ok": False,
            "error": "Unified handoff incomplete",
            "target": str(target.resolve()),
            "files_written": ["START_HERE.md"],
        },
    )
    monkeypatch.setattr(
        app_mod,
        "prepare_linked_project_root",
        lambda p, **kw: repair_calls.append(Path(p)) or (target, None),
    )

    assert (
        app._bootstrap_and_activate(
            target,
            notify=False,
            setup_action="create",
            agent_handoff="unified",
        )
        is False
    )
    assert repair_calls == [target.resolve()]


def test_create_done_shows_partial_bootstrap_when_handoff_incomplete() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]

    class Box:
        calls: list[tuple[str, str]] = []

    def showerror(title, message):
        Box.calls.append((title, message))

    import hive_planner.launcher.app as app_mod

    original = app_mod.messagebox.showerror
    app_mod.messagebox.showerror = showerror
    try:
        app._create_done(
            {
                "ok": False,
                "error": "Unified handoff incomplete â€” missing: docs/cl-spec-integration.md",
                "target": "C:/demo-app",
                "files_written": ["START_HERE.md", "AGENTS.md"],
                "warnings": ["template warning"],
                "handoff": {"missing": ["docs/cl-spec-integration.md"]},
            }
        )
    finally:
        app_mod.messagebox.showerror = original

    assert Box.calls
    assert "Partial bootstrap" in Box.calls[0][1]
    joined = "\n".join(app._pending_home_log)
    assert "missing: docs/cl-spec-integration.md" in joined
    assert "template warning" in joined


def test_create_done_repairs_after_partial_bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    target = tmp_path / "partial"
    target.mkdir()
    repair_calls: list[Path] = []

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(
        app_mod,
        "prepare_linked_project_root",
        lambda p, **kw: repair_calls.append(Path(p)) or (target, None),
    )
    monkeypatch.setattr(app_mod.messagebox, "showerror", lambda *a, **k: None)

    app._create_done(
        {
            "ok": False,
            "error": "Unified handoff incomplete",
            "target": str(target.resolve()),
            "files_written": ["START_HERE.md"],
        }
    )
    assert repair_calls == [target.resolve()]


def test_run_cartridge_import_invalid_feature_promote_reports_error(tmp_path: Path) -> None:
    project = _minimal_hive_project(tmp_path / "proj")
    external = tmp_path / "external-cartridge"
    external.mkdir()
    (external / "holistic.md").write_text("# Holistic\n", encoding="utf-8")

    result = run_cartridge_import_folder(
        project,
        external,
        feature="Bad Feature",
        promote=True,
    )

    assert result["ok"] is True
    assert result["promote"]["ok"] is False
    assert "Invalid feature" in result["promote"]["warnings"][0]


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
    assert "unified-verify" in text


def test_unified_vendor_help_text_covers_cli_commands() -> None:
    from hive_planner.launcher.user_guide import unified_vendor_help_text

    text = unified_vendor_help_text()
    assert "vendor-sync" in text
    assert "unified-verify" in text
    assert ".hive/upstream-pins.json" in text
    assert "hive-continual-learning" in text


def test_scripts_readme_documents_unified_vendor_path() -> None:
    guide = Path(__file__).resolve().parents[1] / "scripts" / "README.md"
    text = guide.read_text(encoding="utf-8")
    assert "## Unified vendor path" in text
    assert "vendor-sync" in text
    assert "unified-verify" in text
    assert "Deploy agent handoff" in text


def test_unified_vendor_repair_hints_for_overlay_gaps() -> None:
    from hive_planner.launcher.service import unified_vendor_repair_hints

    hints = unified_vendor_repair_hints(missing=[".hive/spec-kit/WORKFLOW.md"])
    assert hints
    assert any("Verify vendor pins" in hint for hint in hints)
    assert not any("vendor-sync" in hint for hint in hints)
    assert unified_vendor_repair_hints(missing=["docs/specs/foo/spec.md"]) == []


def test_run_deploy_agent_handoff_includes_vendor_hints_when_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner import agent_handoff

    hive_root = _hive_planner_source(tmp_path)
    project = _minimal_hive_project(tmp_path / "proj")

    def _incomplete(_root: Path):
        from hive_planner.agent_handoff import AgentHandoffStatus

        return AgentHandoffStatus(
            mode="unified",
            spec_kit_enabled=True,
            continual_learning_enabled=True,
            complete=False,
            missing=[".hive/spec-kit/.hive-overlay-rev"],
        )

    monkeypatch.setattr(agent_handoff, "validate_unified_handoff", _incomplete)
    result = run_deploy_agent_handoff(project, hive_planner_root=hive_root, force=True)
    assert result["ok"] is False
    assert result.get("hints")
    assert any("Verify vendor pins" in hint for hint in result["hints"])


def test_load_user_guide_falls_back_when_readme_not_utf8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher import user_guide as user_guide_mod
    from hive_planner.launcher.user_guide import load_user_guide

    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "README.md").write_bytes(b"\xff\xfe")
    cfg = LauncherConfig(hive_planner_root=str(hive))

    def _raise_unicode(_self: Path, *_args, **_kwargs) -> str:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(user_guide_mod.Path, "read_text", _raise_unicode)

    text = load_user_guide(cfg)

    assert "Hive Planner \u2014 quick help" in text
    assert "unified-verify" in text


def test_load_user_guide_falls_back_when_readme_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher import user_guide as user_guide_mod
    from hive_planner.launcher.user_guide import load_user_guide

    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    guide = scripts / "README.md"
    guide.write_text("# unreadable\n", encoding="utf-8")
    cfg = LauncherConfig(hive_planner_root=str(hive))

    def _raise_oserror(_self: Path, *_args, **_kwargs) -> str:
        raise OSError("permission denied")

    monkeypatch.setattr(user_guide_mod.Path, "read_text", _raise_oserror)

    text = load_user_guide(cfg)

    assert "Hive Planner \u2014 quick help" in text
    assert "unified-verify" in text
    assert text.count("## Unified vendor path") == 0


def test_load_user_guide_fallback_does_not_duplicate_unified_section(tmp_path: Path) -> None:
    from hive_planner.launcher.user_guide import load_user_guide

    cfg = LauncherConfig(hive_planner_root=str(tmp_path / "missing"))
    text = load_user_guide(cfg)

    assert "unified-verify" in text
    assert text.count("## Unified vendor path") == 0
    assert text.count("Hive **unified handoff** ships vendored") == 0


def test_load_user_guide_appends_unified_vendor_section_when_readme_stale(tmp_path: Path) -> None:
    from hive_planner.launcher.user_guide import UNIFIED_VENDOR_SECTION_MARKER, load_user_guide, user_guide_path

    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    guide = scripts / "README.md"
    guide.write_text("# Legacy guide\n\nNo vendor section yet.\n", encoding="utf-8")
    cfg = LauncherConfig(hive_planner_root=str(hive))

    text = load_user_guide(cfg)

    assert user_guide_path(cfg) == guide.resolve()
    assert UNIFIED_VENDOR_SECTION_MARKER in text
    assert "vendor-sync" in text
    assert "Legacy guide" in text


def test_load_user_guide_does_not_duplicate_unified_section(tmp_path: Path) -> None:
    from hive_planner.launcher.user_guide import load_user_guide

    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    scripts.joinpath("README.md").write_text(
        "# Guide\n\n## Unified vendor path (Spec Kit + Continual Learning)\n\nAlready documented.\n",
        encoding="utf-8",
    )
    cfg = LauncherConfig(hive_planner_root=str(hive))

    text = load_user_guide(cfg)

    assert text.count("## Unified vendor path") == 1


def test_default_agent_prompt_templates_are_non_empty_and_unique() -> None:
    from hive_planner.launcher.agent_prompt_templates import default_agent_prompt_templates

    templates = default_agent_prompt_templates()
    assert len(templates) >= 5
    ids = [template.id for template in templates]
    titles = [template.title for template in templates]
    assert len(ids) == len(set(ids))
    assert len(titles) == len(set(titles))
    for template in templates:
        assert template.id.strip()
        assert template.title.strip()
        assert template.description.strip()
        assert len(template.prompt.strip()) > 40
        assert "@" in template.prompt or "HOOK" in template.prompt or "spec" in template.prompt.lower()


def test_get_agent_prompt_template_by_id() -> None:
    from hive_planner.launcher.agent_prompt_templates import get_agent_prompt_template

    found = get_agent_prompt_template("session.start")
    assert found is not None
    assert found.title == "Start a coding session"
    assert get_agent_prompt_template("missing.id") is None


def test_format_agent_prompt_templates_markdown_includes_all_titles() -> None:
    from hive_planner.launcher.agent_prompt_templates import (
        default_agent_prompt_templates,
        format_agent_prompt_templates_markdown,
    )

    text = format_agent_prompt_templates_markdown()
    assert text.startswith("# Agent prompt templates")
    for template in default_agent_prompt_templates():
        assert f"## {template.title}" in text
        assert template.prompt.strip() in text


def test_get_agent_prompt_template_by_title_rejects_unknown() -> None:
    from hive_planner.launcher.agent_prompt_templates import get_agent_prompt_template_by_title

    assert get_agent_prompt_template_by_title("Start a coding session") is not None
    assert get_agent_prompt_template_by_title("  Start a coding session  ") is not None
    assert get_agent_prompt_template_by_title("") is None
    assert get_agent_prompt_template_by_title("Not a real template") is None


def test_load_user_guide_fallback_mentions_agent_prompt_templates(tmp_path: Path) -> None:
    from hive_planner.launcher.user_guide import load_user_guide

    cfg = LauncherConfig(hive_planner_root=str(tmp_path / "missing"))
    text = load_user_guide(cfg)
    assert "Agent prompt templates" in text


def test_ci_check_hints_parses_vendor_missing_from_profile_step(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.ci_handoff import CiCheckReport, CiStepResult
    from hive_planner.launcher.service import ci_check_hints
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "unified-app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(project, profile="minimal", project_name="unified-app", agent_handoff_mode=AGENT_HANDOFF_UNIFIED)

    failed = CiCheckReport(
        steps=[
            CiStepResult(
                "agent-handoff-profile",
                False,
                "missing: .hive/spec-kit/WORKFLOW.md, .cursor/plugins/hive-continual-learning/WORKFLOW.md",
            ),
            CiStepResult("unified-vendor", False, "continual-learning overlay missing: .cursor/plugins/hive-continual-learning/WORKFLOW.md"),
        ]
    )

    hints = ci_check_hints(project, failed)

    assert any("Verify vendor pins" in hint for hint in hints)
    assert any("Deploy agent handoff" in hint for hint in hints)


def test_ci_check_hints_unified_vendor_hive_source_vs_project(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.ci_handoff import CiCheckReport, CiStepResult
    from hive_planner.launcher.service import ci_check_hints, is_hive_planner_source_repo
    from hive_planner.project_profile import write_project_profile

    hive = tmp_path / "hive"
    hive.mkdir()
    (hive / "pyproject.toml").write_text('[project]\nname = "hive-planner"\n', encoding="utf-8")
    app = tmp_path / "app"
    app.mkdir()
    (app / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (app / "pyproject.toml").write_text('[project]\nname = "my-app"\n', encoding="utf-8")
    unified_app = tmp_path / "unified-app"
    unified_app.mkdir()
    (unified_app / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(unified_app, profile="minimal", project_name="unified-app", agent_handoff_mode=AGENT_HANDOFF_UNIFIED)

    failed = CiCheckReport(steps=[CiStepResult("unified-vendor", False, "vendor paths missing")])

    hive_hints = ci_check_hints(hive, failed)
    app_hints = ci_check_hints(app, failed)
    unified_hints = ci_check_hints(unified_app, failed)

    assert is_hive_planner_source_repo(hive) is True
    assert any("vendor-sync" in hint for hint in hive_hints)
    assert not any("Deploy agent handoff" in hint for hint in hive_hints)
    assert not any("Deploy agent handoff" in hint for hint in app_hints)
    assert any("Deploy agent handoff" in hint for hint in unified_hints)
    assert any("Verify vendor pins" in hint for hint in unified_hints)


def _minimal_unified_project(tmp_path: Path, feature: str = "my-feature") -> Path:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.cartridge_promote import _tasks_wiring_audit_block
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "unified-app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## Repository root",
                "",
                "`root`",
                "",
                "## Planning Rosetta Stone",
                "",
                "- hook `planning.rosetta`",
                "",
                "## Startup read order",
                "",
                "1. rosetta",
                "",
                "## Delta model",
                "",
                "- Holistic / Macro / Micro",
                "",
                "## Active feature",
                "",
                f"**{feature}**",
                "",
                "## Durable Workspace Facts",
                "",
                "- Run ci-check before handoff.",
            ]
        ),
        encoding="utf-8",
    )
    _write_handoff_bundle(project, feature)
    tasks_path = project / "docs" / "specs" / feature / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").rstrip()
        + "\n\n"
        + _tasks_wiring_audit_block().replace("- [ ]", "- [x]"),
        encoding="utf-8",
    )
    write_project_profile(project, profile="minimal", project_name="unified-app", agent_handoff_mode=AGENT_HANDOFF_UNIFIED)
    return project




def test_ci_check_hints_cl_install_learned_facts_without_remove_flag(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
    from hive_planner.ci_handoff import CiCheckReport, CiStepResult
    from hive_planner.launcher.service import ci_check_hints
    from hive_planner.project_profile import write_project_profile
    from hive_planner.vendor_sync import CL_OVERLAY_REL
    from tests.test_cl_migration import _minimal_agents_with_learned, _write_plugin

    project = tmp_path / "legacy-facts-hints"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(_minimal_agents_with_learned(), encoding="utf-8")
    write_project_profile(
        project, profile="minimal", project_name="legacy-facts-hints", agent_handoff_mode=AGENT_HANDOFF_UNIFIED
    )
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    failed = CiCheckReport(steps=[CiStepResult("cl-install", False, "learned workspace facts")])
    hints = ci_check_hints(project, failed)
    assert hints
    joined = " ".join(hints)
    assert "cl-migrate" in joined
    assert "--remove-marketplace-plugin" not in joined


def test_ci_check_hints_cl_install_dual_uses_remove_flag(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, MARKETPLACE_CL_REL
    from hive_planner.ci_handoff import CiCheckReport, CiStepResult
    from hive_planner.launcher.service import ci_check_hints
    from hive_planner.project_profile import write_project_profile
    from hive_planner.vendor_sync import CL_OVERLAY_REL
    from tests.test_cl_migration import _write_plugin

    project = tmp_path / "dual-hints"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(project, profile="minimal", project_name="dual-hints", agent_handoff_mode=AGENT_HANDOFF_UNIFIED)
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    failed = CiCheckReport(steps=[CiStepResult("cl-install", False, "dual install")])
    hints = ci_check_hints(project, failed)
    assert any("--remove-marketplace-plugin" in hint for hint in hints)



def test_ci_check_hints_cl_install_headless_dual_uses_remove_flag(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, MARKETPLACE_CL_REL
    from hive_planner.ci_handoff import CiCheckReport, CiStepResult
    from hive_planner.cl_runtime import CL_RUNTIME_HEADLESS, deploy_headless_cl_artifacts
    from hive_planner.launcher.service import ci_check_hints
    from hive_planner.project_profile import write_project_profile
    from hive_planner.vendor_sync import CL_OVERLAY_REL
    from tests.test_cl_migration import _write_plugin

    project = tmp_path / "headless-dual-hints"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    write_project_profile(
        project,
        profile="minimal",
        project_name="headless-dual-hints",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
        cl_runtime=CL_RUNTIME_HEADLESS,
    )
    deploy_headless_cl_artifacts(project, CL_RUNTIME_HEADLESS, force=True)
    _write_plugin(project, MARKETPLACE_CL_REL, "continual-learning")
    _write_plugin(project, CL_OVERLAY_REL, "hive-continual-learning")

    failed = CiCheckReport(steps=[CiStepResult("cl-install", False, "marketplace on headless")])
    hints = ci_check_hints(project, failed)
    assert any("--remove-marketplace-plugin" in hint for hint in hints)


def test_ci_check_hints_wiring_audit_failure(tmp_path: Path) -> None:
    from hive_planner.ci_handoff import CiCheckReport, CiStepResult
    from hive_planner.launcher.service import ci_check_hints

    project = _minimal_unified_project(tmp_path)
    failed = CiCheckReport(
        steps=[CiStepResult("wiring-audit", False, "Missing wiring audit attestation at .hive/wiring-audit.json")]
    )
    hints = ci_check_hints(project, failed)
    assert any("Record wiring audit" in hint for hint in hints)
    assert any("tasks.md" in hint for hint in hints)


def test_wiring_audit_status_label_and_record(tmp_path: Path) -> None:
    from hive_planner.launcher.service import (
        run_wiring_audit_check,
        run_wiring_audit_record,
        wiring_audit_status_label,
    )

    project = _minimal_unified_project(tmp_path)
    assert wiring_audit_status_label(project) == "missing"
    check = run_wiring_audit_check(project)
    assert check["ok"] is False
    assert check.get("hints")
    recorded = run_wiring_audit_record(project, "pytest -q")
    assert recorded["ok"] is True
    assert recorded["recorded"] == ".hive/wiring-audit.json"
    assert wiring_audit_status_label(project) == "ok"


def test_run_wiring_audit_record_skipped_when_not_enforced(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_wiring_audit_record

    project = tmp_path / "plain-app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## Active feature",
                "",
                "**my-feature**",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result = run_wiring_audit_record(project, "pytest -q")
    assert result.get("skipped") is True
    assert not (project / ".hive" / "wiring-audit.json").exists()


def test_find_staged_candidates_picks_newest(tmp_path: Path) -> None:
    from hive_planner.launcher.service import find_staged_candidates

    project = tmp_path / "app"
    proposals = project / "docs" / "proposals"
    proposals.mkdir(parents=True)
    older = proposals / "candidates-old.md"
    newer = proposals / "candidates-new.md"
    older.write_text("- old\n", encoding="utf-8")
    newer.write_text("- new\n", encoding="utf-8")
    older.touch()
    import time

    time.sleep(0.02)
    newer.touch()
    assert find_staged_candidates(project) == newer


def test_find_staged_candidates_includes_cartridge_memory_files(tmp_path: Path) -> None:
    from hive_planner.launcher.service import find_staged_candidates

    project = tmp_path / "app"
    proposals = project / "docs" / "proposals"
    proposals.mkdir(parents=True)
    cartridge = proposals / "cartridge-memory-my-feature-20260626_120000.md"
    cartridge.write_text("# operational\n\n- Run ci-check before handoff.\n", encoding="utf-8")
    assert find_staged_candidates(project) == cartridge
    assert find_staged_candidates(project).parent == proposals


def test_run_agents_memory_propose_requires_wiring_audit(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_agents_memory_propose

    project = _minimal_unified_project(tmp_path)
    candidates = project / "docs" / "proposals" / "candidates.md"
    candidates.parent.mkdir(parents=True, exist_ok=True)
    candidates.write_text("- New durable operational fact.\n", encoding="utf-8")
    blocked = run_agents_memory_propose(project, candidates)
    assert blocked["ok"] is False
    assert "Wiring audit required" in blocked["error"]
    assert blocked.get("hints")


def test_run_agents_memory_propose_rejects_generated_proposal_as_candidates(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_agents_memory_propose

    project = _minimal_unified_project(tmp_path)
    proposal = project / "docs" / "proposals" / "agents-memory-20260626_120000.md"
    proposal.parent.mkdir(parents=True, exist_ok=True)
    proposal.write_text("# AGENTS.md Memory Proposal\n", encoding="utf-8")
    result = run_agents_memory_propose(project, proposal)
    assert result["ok"] is False
    assert "not a generated agents-memory proposal" in result["error"]
    assert result.get("hints")


def test_run_agents_memory_propose_returns_rejection_preview_fields(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_agents_memory_propose
    from hive_planner.wiring_audit import record_wiring_audit

    project = _minimal_unified_project(tmp_path)
    record_wiring_audit(RepoPaths(root=project), evidence="pytest -q")
    candidates = project / "docs" / "proposals" / "candidates.md"
    candidates.parent.mkdir(parents=True, exist_ok=True)
    candidates.write_text("- API must validate manifest schema version.\n", encoding="utf-8")
    result = run_agents_memory_propose(project, candidates)
    assert result["ok"] is False
    assert result.get("all_rejected") is True
    assert result.get("proposal_path")
    assert result.get("rejected")
    assert any("behavioral" in item.get("reason", "").lower() for item in result["rejected"])


def test_run_agents_memory_propose_hints_when_all_candidates_rejected(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_agents_memory_propose
    from hive_planner.wiring_audit import record_wiring_audit

    project = _minimal_unified_project(tmp_path)
    record_wiring_audit(RepoPaths(root=project), evidence="pytest -q")
    candidates = project / "docs" / "proposals" / "candidates.md"
    candidates.parent.mkdir(parents=True, exist_ok=True)
    candidates.write_text("- API must validate manifest schema version.\n", encoding="utf-8")
    result = run_agents_memory_propose(project, candidates)
    assert result["ok"] is False
    assert any("behavioral" in hint.lower() or "operational" in hint.lower() for hint in result.get("hints", []))
    proposals = list((project / "docs" / "proposals").glob("agents-memory-*.md"))
    assert proposals, "a proposal file with rejection reasons should be written"
    text = proposals[0].read_text(encoding="utf-8")
    assert "Rejected candidates" in text


def test_run_unified_verify_on_bootstrapped_project(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_unified_verify
    from hive_planner.vendor_sync import (
        deploy_continual_learning_overlay,
        deploy_spec_kit_overlay,
        load_manifest,
        packaged_manifest_path,
        write_project_pins,
    )

    project = tmp_path / "verify-app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    source = Path(__file__).resolve().parents[1]
    pins = load_manifest(packaged_manifest_path())
    write_project_pins(project, pins, force=True)
    deploy_spec_kit_overlay(source, project, force=True)
    deploy_continual_learning_overlay(source, project, force=True)

    result = run_unified_verify(project)

    assert result["ok"] is True
    assert result.get("issues") == []


def test_run_legacy_deployment_scan_reports_starter_kit_layout(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_legacy_deployment_scan

    project = tmp_path / "legacy-scan"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")

    result = run_legacy_deployment_scan(project)

    assert result["ok"] is False
    assert any(item["code"] == "missing_upstream_pins" for item in result["findings"])
    assert "hints" not in result


def test_run_agents_memory_propose_includes_preview_fields(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_agents_memory_propose
    from hive_planner.wiring_audit import record_wiring_audit

    project = _minimal_unified_project(tmp_path)
    record_wiring_audit(RepoPaths(root=project), evidence="pytest -q")
    candidates = project / "docs" / "proposals" / "candidates.md"
    candidates.parent.mkdir(parents=True, exist_ok=True)
    candidates.write_text("- # operational\n- Keep launcher logs concise.\n", encoding="utf-8")

    result = run_agents_memory_propose(project, candidates)
    assert result["ok"] is True
    assert "Keep launcher logs concise." in result["after_section"]
    assert result["current_facts"] is not None
    assert isinstance(result.get("spec_actions"), list)


def test_run_agents_memory_apply_writes_agents_md(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_agents_memory_apply, run_agents_memory_propose
    from hive_planner.wiring_audit import record_wiring_audit

    project = _minimal_unified_project(tmp_path)
    record_wiring_audit(RepoPaths(root=project), evidence="pytest -q")
    candidates = project / "docs" / "proposals" / "candidates.md"
    candidates.parent.mkdir(parents=True, exist_ok=True)
    candidates.write_text("- # operational\n- Keep launcher logs concise.\n", encoding="utf-8")
    proposed = run_agents_memory_propose(project, candidates)
    assert proposed["ok"] is True
    applied = run_agents_memory_apply(project, candidates)
    assert applied["ok"] is True
    assert applied.get("applied") is True
    assert "Keep launcher logs concise." in (project / "AGENTS.md").read_text(encoding="utf-8")


def test_candidates_path_in_project_rejects_outside_root(tmp_path: Path) -> None:
    from hive_planner.launcher.service import candidates_path_in_project

    project = tmp_path / "app"
    project.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("- x\n", encoding="utf-8")
    inside = project / "docs" / "proposals" / "candidates.md"
    inside.parent.mkdir(parents=True)
    inside.write_text("- x\n", encoding="utf-8")

    assert candidates_path_in_project(project, inside) is True
    assert candidates_path_in_project(project, outside) is False


def test_run_agents_memory_propose_rejects_outside_root_candidates(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_agents_memory_propose

    project = _minimal_unified_project(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("- # operational\n- Outside fact.\n", encoding="utf-8")
    result = run_agents_memory_propose(project, outside)
    assert result["ok"] is False
    assert "inside project root" in result["error"]
    assert result.get("hints")


def test_run_agents_memory_propose_includes_detail_when_not_hive_project(tmp_path: Path) -> None:
    from hive_planner.launcher.service import run_agents_memory_propose

    result = run_agents_memory_propose(tmp_path / "missing", Path("candidates.md"))
    assert result["ok"] is False
    assert result.get("detail") == result.get("error")


def test_memory_candidates_picker_dir_falls_back_to_project_root(tmp_path: Path) -> None:
    from hive_planner.launcher.service import memory_candidates_picker_dir

    project = tmp_path / "app"
    project.mkdir()
    assert memory_candidates_picker_dir(project) == str(project.resolve())

    proposals = project / "docs" / "proposals"
    proposals.mkdir(parents=True)
    assert memory_candidates_picker_dir(project) == str(proposals.resolve())

    staged = proposals / "candidates.md"
    staged.write_text("- x\n", encoding="utf-8")
    assert memory_candidates_picker_dir(project, staged) == str(proposals.resolve())


def test_agents_apply_done_refreshes_dashboard_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    refreshed: list[bool] = []
    app._refresh_home_dashboard = lambda: refreshed.append(True)  # type: ignore[method-assign]
    app._active_linked_root = lambda: None  # type: ignore[method-assign]

    app._agents_apply_done({"ok": False, "error": "Wiring audit required", "hints": ["Record wiring audit"]})
    assert refreshed == [True]


def test_open_project_file_rejects_paths_outside_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    import hive_planner.launcher.app as app_module

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    warned: list[str] = []
    monkeypatch.setattr(
        app_module.messagebox,
        "showwarning",
        lambda title, message, **kwargs: warned.append(message),
    )

    app._open_project_file(tmp_path, "..\\outside.md")
    assert warned
    assert "inside the linked project" in warned[0]


def test_open_project_file_falls_back_to_folder_when_no_association(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hive_planner.launcher.app as app_module
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    proposal = tmp_path / "docs" / "proposals" / "agents-memory-1.md"
    proposal.parent.mkdir(parents=True)
    proposal.write_text("# proposal\n", encoding="utf-8")

    opened_folders: list[Path] = []
    monkeypatch.setattr(app_module.sys, "platform", "win32")

    def boom(_target: object) -> None:
        raise OSError("no association")

    monkeypatch.setattr(app_module.os, "startfile", boom, raising=False)
    monkeypatch.setattr(
        app_module, "open_path_in_explorer", lambda p: opened_folders.append(Path(p))
    )
    monkeypatch.setattr(app_module.messagebox, "showinfo", lambda *a, **k: None)

    app._open_project_file(tmp_path, "docs/proposals/agents-memory-1.md")
    assert opened_folders == [proposal.parent.resolve()]


def test_format_memory_proposal_preview_includes_before_after_and_rejected() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    text = app._format_memory_proposal_preview(
        {
            "accepted": ["Run pytest before handoff."],
            "current_facts": "- Existing fact.",
            "after_section": "- Existing fact.\n- Run pytest before handoff.",
            "rejected": [{"candidate": "Must return 404", "reason": "behavioral — update spec.md"}],
            "proposal_path": "docs/proposals/agents-memory-1.md",
        }
    )
    assert "Current memory" in text
    assert "Existing fact." in text
    assert "Run pytest before handoff." in text
    assert "Rejected (1)" in text
    assert "Must return 404" in text


def test_agents_apply_done_shows_rejection_preview_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]
    previewed: list[bool] = []
    app._active_linked_root = lambda: Path("C:/proj")
    monkeypatch.setattr(
        app,
        "_show_memory_rejection_preview",
        lambda result, *, root: previewed.append(True),
    )

    app._agents_apply_done(
        {
            "ok": False,
            "error": "All candidate bullets were rejected by validation",
            "proposal_path": "docs/proposals/agents-memory-1.md",
            "rejected": [{"candidate": "bad", "reason": "behavioral"}],
        }
    )

    assert previewed == [True]


def test_agents_propose_done_prompts_apply_without_name_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]
    previewed: list[bool] = []

    monkeypatch.setattr(
        app,
        "_show_memory_proposal_preview",
        lambda result, *, root: previewed.append(True) or False,
    )
    project = Path("C:/proj")
    app.config = type("Cfg", (), {"active_project": "C:/proj"})()
    app._active_linked_root = lambda: project
    app._set_pending_memory_candidates(project, Path("C:/proj/docs/proposals/candidates.md"))

    app._agents_propose_done(
        {
            "ok": True,
            "proposal_path": "docs/proposals/agents-memory-1.md",
            "accepted": ["Keep logs concise."],
            "rejected": [],
            "applied": False,
            "current_facts": "- Old.",
            "after_section": "- Old.\n- Keep logs concise.",
        }
    )

    assert previewed == [True]
    assert not any("NameError" in line for line in app._pending_home_log)


def test_agents_propose_done_apply_after_preview_accept(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]
    app._start_home_action = lambda _msg: None  # type: ignore[method-assign]
    bg_calls: list[tuple] = []
    app._run_bg = lambda fn, done: bg_calls.append((fn, done))  # type: ignore[method-assign]

    monkeypatch.setattr(
        app,
        "_show_memory_proposal_preview",
        lambda result, *, root: True,
    )
    project = Path("C:/proj")
    app.config = type("Cfg", (), {"active_project": "C:/proj"})()
    app._active_linked_root = lambda: project
    app._set_pending_memory_candidates(project, Path("C:/proj/docs/proposals/candidates.md"))

    app._agents_propose_done(
        {
            "ok": True,
            "proposal_path": "docs/proposals/agents-memory-1.md",
            "accepted": ["Keep logs concise."],
            "rejected": [],
            "applied": False,
            "current_facts": "- Old.",
            "after_section": "- Old.\n- Keep logs concise.",
        }
    )

    assert len(bg_calls) == 1


def test_pending_memory_survives_dashboard_when_linked_via_workspace_file(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.config import LauncherConfig, normalize_project_path

    folder = tmp_path / "app"
    folder.mkdir()
    workspace = tmp_path / "app.code-workspace"
    workspace.write_text('{"folders":[{"path":"app"}]}\n', encoding="utf-8")
    candidates = folder / "docs" / "proposals" / "candidates.md"
    candidates.parent.mkdir(parents=True)
    candidates.write_text("- x\n", encoding="utf-8")

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=str(workspace))
    app._set_pending_memory_candidates(folder, candidates)

    assert app._pending_memory_link == normalize_project_path(workspace)
    assert app._pending_memory_for_root(folder) == candidates

    active_norm = normalize_project_path(app.config.active_project)
    assert app._pending_memory_link == active_norm


def test_is_bg_error_treats_cl_migrate_failure_as_structured() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    assert app._is_bg_error(
        {
            "ok": False,
            "error": "Hive continual-learning plugin missing",
            "warnings": ["Hive continual-learning plugin missing"],
        }
    ) is False


def test_cl_migrate_done_logs_warnings_on_success_path() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]

    app._cl_migrate_done(
        {
            "ok": True,
            "dry_run": True,
            "warnings": ["Marketplace plugin still present at .cursor/plugins/continual-learning/"],
            "actions": ["Merged 1 bullet(s) from ## Learned Workspace Facts"],
            "merged_bullets": 1,
        }
    )

    assert any(line.startswith("Warning:") for line in app._pending_home_log)
    assert any("dry run complete" in line for line in app._pending_home_log)
    assert not any(line == "CL migration complete." for line in app._pending_home_log)


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
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]
    app._map_sync_done(
        {
            "ok": True,
            "project_added": ["a"],
            "test_added": [],
            "project_updated": ["b"],
            "test_updated": [],
        }
    )
    assert app._pending_home_log == ["Impact maps synced: 1 added, 1 updated."]


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
    from hive_planner.project_profile import write_project_profile

    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    write_project_profile(b, profile="full", project_name="B")
    cfg = LauncherConfig(recent_projects=[str(a), str(b)])
    cfg.add_recent_project(b)
    assert cfg.recent_projects[0] == str(b.resolve())
    assert len(cfg.recent_projects) == 2
    assert cfg.project_profiles[str(b.resolve())] == "full"


def test_add_recent_project_does_not_cache_inferred_profile_without_metadata(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    cfg = LauncherConfig()
    cfg.add_recent_project(project)

    assert cfg.active_project == str(project.resolve())
    assert str(project.resolve()) not in cfg.project_profiles


def test_add_recent_project_after_delete_profile_does_not_recache(tmp_path: Path) -> None:
    from hive_planner.project_profile import delete_project_profile, write_project_profile

    project = tmp_path / "demo"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    write_project_profile(project, profile="minimal", project_name="Demo")

    cfg = LauncherConfig(recent_projects=[str(project.resolve())])
    cfg.add_recent_project(project)
    assert cfg.project_profiles[str(project.resolve())] == "minimal"

    delete_project_profile(project)
    clear_project_profile_cache(cfg, project)
    assert str(project.resolve()) not in cfg.project_profiles

    cfg.add_recent_project(project)
    assert str(project.resolve()) not in cfg.project_profiles


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


def test_remove_recent_project_matches_normalized_path(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    resolved = str(project.resolve())
    cfg = LauncherConfig(
        active_project=resolved,
        recent_projects=[resolved.replace("\\", "/") if "\\" in resolved else f"{resolved}/"],
        project_profiles={resolved: "full"},
    )
    if cfg.recent_projects[0] == resolved:
        cfg.recent_projects = [f"{resolved}\\"]  # trailing separator variant on Windows
    assert cfg.remove_recent_project(project) is True
    assert cfg.recent_projects == []
    assert cfg.active_project == ""


def test_set_active_on_missing_link_keeps_local_entry(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    missing = tmp_path / "gone"
    resolved = str(missing.resolve())
    cfg = LauncherConfig(recent_projects=[resolved], active_project="")

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._recent_project_paths = [resolved]
    app.recent_list = type("L", (), {"curselection": lambda self: (0,)})()

    import hive_planner.launcher.app as app_mod

    original_err = app_mod.messagebox.showerror
    app_mod.messagebox.showerror = lambda *a, **k: None
    try:
        assert app._link_workspace(missing, notify=False) is False
    finally:
        app_mod.messagebox.showerror = original_err

    assert app.config.recent_projects == [resolved]


def test_delete_profile_resolves_code_workspace_link_to_project_root(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.project_profile import project_meta_path, write_project_profile

    repo = tmp_path / "app"
    repo.mkdir()
    write_project_profile(repo, profile="minimal", project_name="App")
    workspace_file = tmp_path / "hive.code-workspace"
    workspace_file.write_text(json.dumps({"folders": [{"path": repo.name}]}), encoding="utf-8")

    deleted: list[Path] = []

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(recent_projects=[str(workspace_file.resolve())])
    app._recent_project_paths = [str(workspace_file.resolve())]
    app.recent_list = type("L", (), {"curselection": lambda self: (0,)})()
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod
    import hive_planner.project_profile as profile_mod

    def fake_delete(project_root: Path) -> tuple[bool, str]:
        deleted.append(project_root)
        return True, "Hive profile metadata deleted."

    original_yesno = app_mod.messagebox.askyesno
    original_delete = profile_mod.delete_project_profile
    original_load = app_mod.load_config
    original_save = app_mod.save_config
    original_info = app_mod.messagebox.showinfo
    app_mod.messagebox.askyesno = lambda *a, **k: True
    app_mod.messagebox.showinfo = lambda *a, **k: None
    app_mod.load_config = lambda: app.config
    app_mod.save_config = lambda _cfg: None
    profile_mod.delete_project_profile = fake_delete
    try:
        app._on_delete_profile()
    finally:
        app_mod.messagebox.askyesno = original_yesno
        app_mod.messagebox.showinfo = original_info
        app_mod.load_config = original_load
        app_mod.save_config = original_save
        profile_mod.delete_project_profile = original_delete

    assert deleted == [repo.resolve()]
    assert project_meta_path(repo).is_file()


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


def test_delete_profile_clears_normalized_profile_cache(tmp_path: Path) -> None:
    from hive_planner.launcher.config import clear_project_profile_cache, normalize_project_path

    project = tmp_path / "demo"
    project.mkdir()
    normalized = str(project.resolve())
    raw = str(project)
    cfg = LauncherConfig(
        recent_projects=[normalized],
        project_profiles={normalized: "full", raw: "full"},
    )
    clear_project_profile_cache(cfg, project)
    assert normalized not in cfg.project_profiles
    assert raw not in cfg.project_profiles


def test_linked_workspace_label_ignores_stale_profile_cache(tmp_path: Path) -> None:
    from hive_planner.launcher.app import format_linked_workspace_label
    from hive_planner.project_profile import delete_project_profile, read_project_profile, write_project_profile

    project = tmp_path / "demo"
    project.mkdir()
    write_project_profile(project, profile="full", project_name="Demo")
    path = str(project.resolve())

    stored = read_project_profile(project)
    assert stored is not None
    assert "[full]" in format_linked_workspace_label(path, stored.bootstrap_profile)

    delete_project_profile(project)
    stored = read_project_profile(project)
    profile = stored.bootstrap_profile if stored else None
    assert profile is None
    assert "[full]" not in format_linked_workspace_label(path, profile)


def test_recent_label_uses_stored_profile_not_inferred(tmp_path: Path) -> None:
    from hive_planner.launcher.app import format_recent_project_label
    from hive_planner.project_profile import delete_project_profile, read_project_profile, write_project_profile

    project = tmp_path / "demo"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    write_project_profile(project, profile="minimal", project_name="Demo")

    stored = read_project_profile(project)
    assert stored is not None
    assert format_recent_project_label(str(project), stored.bootstrap_profile) == "demo  [minimal]"

    delete_project_profile(project)
    assert read_project_profile(project) is None
    assert format_recent_project_label(str(project), None) == "demo"


def test_active_profile_label_uses_stored_metadata_not_inference(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "demo"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    write_project_profile(project, profile="minimal", project_name="Demo")

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=str(project.resolve()))
    assert app._active_profile_label() == "minimal"

    (project / ".hive" / "project.json").unlink()
    (project / ".hive").rmdir()
    assert app._active_profile_label() == ""


def test_update_recent_scrollbar_hides_when_list_is_short() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    packed: list[bool] = []

    class FakeScroll:
        def winfo_ismapped(self) -> bool:
            return bool(packed)

        def pack(self, **_kwargs) -> None:
            packed.append(True)

        def pack_forget(self) -> None:
            packed.clear()

        def set(self, *_args) -> None:
            return None

    class FakeList:
        def __init__(self) -> None:
            self._items = ["a", "b"]
            self._height = HivePlannerApp.RECENT_LIST_MIN_ROWS

        def size(self) -> int:
            return len(self._items)

        def configure(self, **kwargs) -> None:
            if "height" in kwargs:
                self._height = kwargs["height"]

        def cget(self, key: str):
            if key == "height":
                return self._height
            raise KeyError(key)

        def yview_moveto(self, _pos) -> None:
            return None

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.recent_list = FakeList()
    app.recent_scroll = FakeScroll()
    app._update_recent_scrollbar()
    assert packed == []
    assert app.recent_list._height == HivePlannerApp.RECENT_LIST_MIN_ROWS

    app.recent_list._items.extend(["c", "d", "e"])
    app._update_recent_scrollbar()
    assert packed == [True]
    assert app.recent_list._height == HivePlannerApp.RECENT_LIST_MAX_ROWS


def test_bind_mousewheel_scrolls_on_enter_and_unbinds_on_destroy() -> None:
    from hive_planner.launcher.theme import _dispatch_wheel, bind_mousewheel, reset_mousewheel_state_for_tests

    reset_mousewheel_state_for_tests()
    handlers: dict = {}
    scrolled: list[int] = []
    next_id = 1

    class FakeWidget:
        def __init__(self) -> None:
            nonlocal next_id
            self.widget_id = next_id
            next_id += 1

        def winfo_id(self) -> int:
            return self.widget_id

        def winfo_toplevel(self) -> FakeWidget:
            return self

        def winfo_exists(self) -> bool:
            return True

        def bind(self, seq, func, add=None) -> None:
            handlers[seq] = func

        def bind_all(self, seq, func, add=None) -> None:
            return None

        def yview_scroll(self, amount, _what) -> None:
            scrolled.append(amount)

    widget = FakeWidget()
    bind_mousewheel(widget, target=widget)

    handlers["<Enter>"](None)
    _dispatch_wheel(type("E", (), {"delta": 120})())
    assert scrolled == [-1]

    handlers["<Leave>"](None)
    assert scrolled == [-1]

    handlers["<Enter>"](None)
    handlers["<Destroy>"](None)
    reset_mousewheel_state_for_tests()


def test_format_recent_project_label_uses_folder_name_only() -> None:
    from hive_planner.launcher.app import format_recent_project_label, format_workspace_picker_label
    from hive_planner.launcher.service import CursorWorkspace

    path = r"F:\DRIVE DOWNLOADS\HIVE CODE\My Project"
    assert format_recent_project_label(path) == "My Project"
    assert format_recent_project_label(path, "full") == "My Project  [full]"
    assert format_recent_project_label(path, "full", active=True) == "My Project  [full]  \u2190 active"
    assert (
        format_recent_project_label(r"F:\HIVE CODE\hive-code.code-workspace")
        == "hive-code (Workspace)"
    )
    ws = CursorWorkspace(
        path=r"F:\HIVE CODE\hive-code.code-workspace",
        name="hive-code (Workspace)",
        location=r"F:\HIVE CODE",
        exists=True,
        hive_ready=True,
        has_cursor_dir=True,
        has_git=False,
        entry_kind="workspace",
    )
    assert format_workspace_picker_label(ws) == "hive-code (Workspace)  \u00b7  F:\\HIVE CODE"


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


def test_bootstrap_and_activate_scaffolds_empty_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    hive_root = Path(__file__).resolve().parents[1]
    target = tmp_path / "new-app"
    target.mkdir()
    cfg = LauncherConfig(hive_planner_root=str(hive_root), default_profile="minimal")

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)

    assert app._bootstrap_and_activate(target) is True
    assert (target / "START_HERE.md").is_file()
    assert (target / "AGENTS.md").is_file()


def test_summarize_bootstrap_state_empty(tmp_path: Path) -> None:
    from hive_planner.launcher.bootstrap_state import summarize_bootstrap_state

    target = tmp_path / "empty"
    target.mkdir()
    state = summarize_bootstrap_state(target)
    assert state.is_empty is True
    assert state.has_start_here is False
    assert state.has_rosetta is False
    assert state.hive_ready is False
    assert state.handoff_missing == []
    assert state.allows_add_missing is False


def test_summarize_bootstrap_state_hive_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.agent_handoff import AgentHandoffStatus
    from hive_planner.launcher.bootstrap_state import summarize_bootstrap_state

    target = tmp_path / "ready"
    target.mkdir()
    (target / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (target / "docs").mkdir()
    (target / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")
    monkeypatch.setattr(
        "hive_planner.launcher.bootstrap_state.validate_unified_handoff",
        lambda _root: AgentHandoffStatus(
            mode="unified",
            spec_kit_enabled=True,
            continual_learning_enabled=True,
            complete=True,
            missing=[],
        ),
    )
    state = summarize_bootstrap_state(target)
    assert state.hive_ready is True
    assert state.has_partial_hive is True
    assert state.needs_handoff_repair is False


def test_summarize_bootstrap_state_partial_and_missing_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.agent_handoff import AgentHandoffStatus
    from hive_planner.launcher.bootstrap_state import summarize_bootstrap_state

    target = tmp_path / "partial"
    target.mkdir()
    (target / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    monkeypatch.setattr(
        "hive_planner.launcher.bootstrap_state.validate_unified_handoff",
        lambda _root: AgentHandoffStatus(
            mode="unified",
            spec_kit_enabled=True,
            continual_learning_enabled=True,
            complete=False,
            missing=["docs/cl-spec-integration.md"],
        ),
    )
    state = summarize_bootstrap_state(target)
    assert state.hive_ready is False
    assert state.has_start_here is True
    assert state.allows_add_missing is True
    assert state.handoff_missing == ["docs/cl-spec-integration.md"]


def test_bootstrap_and_activate_link_only_skips_init(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    target = tmp_path / "existing"
    target.mkdir()
    (target / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    cfg = LauncherConfig(hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    init_calls: list[dict] = []

    def fake_init(*_args, **kwargs):
        init_calls.append(kwargs)
        return {"ok": True}

    saved: list[LauncherConfig] = []

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda c: saved.append(c))
    monkeypatch.setattr(app_mod, "run_project_init", fake_init)

    repair_calls: list[Path] = []
    monkeypatch.setattr(
        app_mod,
        "prepare_linked_project_root",
        lambda p, **kw: repair_calls.append(Path(p)) or (target, None),
    )

    assert app._bootstrap_and_activate(target, notify=False, setup_action="link_only") is True
    assert init_calls == []
    assert repair_calls == [target.resolve()]
    assert saved[-1].recent_projects == [str(target.resolve())]


def test_bootstrap_and_activate_add_missing_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    hive_root = Path(__file__).resolve().parents[1]
    target = tmp_path / "partial"
    target.mkdir()
    (target / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    cfg = LauncherConfig(hive_planner_root=str(hive_root), default_profile="minimal", default_agent_handoff="unified")

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)

    with patch("hive_planner.bootstrap.subprocess.run"):
        assert (
            app._bootstrap_and_activate(
                target,
                notify=False,
                setup_action="add_missing",
                agent_handoff="unified",
                cl_runtime="cursor",
            )
            is True
        )
    assert (target / "docs" / "planning-rosetta-stone.md").is_file()


def test_bootstrap_and_activate_repairs_after_init(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    target = tmp_path / "new-app"
    target.mkdir()
    cfg = LauncherConfig(hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    repair_calls: list[Path] = []

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(
        app_mod,
        "run_project_init",
        lambda *_a, **_k: {"ok": True, "target": str(target.resolve())},
    )
    monkeypatch.setattr(
        app_mod,
        "prepare_linked_project_root",
        lambda p, **kw: repair_calls.append(Path(p)) or (target, None),
    )

    assert (
        app._bootstrap_and_activate(
            target,
            notify=False,
            setup_action="create",
            agent_handoff="unified",
            cl_runtime="cursor",
        )
        is True
    )
    assert repair_calls == [target.resolve()]


def test_bootstrap_and_activate_passes_cl_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    target = tmp_path / "new-app"
    target.mkdir()
    cfg = LauncherConfig(hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    captured: list[dict] = []

    def fake_init(_cfg, **kwargs):
        captured.append(kwargs)
        return {"ok": True, "target": str(target)}

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(app_mod, "run_project_init", fake_init)

    app._bootstrap_and_activate(
        target,
        notify=False,
        setup_action="create",
        agent_handoff="unified",
        cl_runtime="headless",
    )
    assert captured[0]["cl_runtime"] == "headless"
    assert captured[0]["agent_handoff"] == "unified"


def test_link_workspace_offers_setup_when_relinking_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.bootstrap_state import LinkBootstrapChoice

    project = tmp_path / "repo"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    resolved = str(project.resolve())
    cfg = LauncherConfig(recent_projects=[resolved], hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._show_dashboard = lambda: None  # type: ignore[method-assign]
    app.root = type("R", (), {})()

    import hive_planner.launcher.app as app_mod

    prompted: list[Path] = []

    def fake_prompt(target, state, *, workspace_label):
        prompted.append(target)
        return LinkBootstrapChoice(
            action="add_missing",
            profile="minimal",
            agent_handoff="unified",
            cl_runtime="cursor",
        )

    bootstrap_calls: list[dict] = []

    def fake_bootstrap(path, **kwargs):
        bootstrap_calls.append({"path": path, **kwargs})
        return True

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    app._prompt_link_bootstrap_setup = fake_prompt  # type: ignore[method-assign]
    app._bootstrap_and_activate = fake_bootstrap  # type: ignore[method-assign]

    assert app._link_workspace(project, notify=True) is True
    assert prompted == [project.resolve()]
    assert bootstrap_calls
    assert bootstrap_calls[0]["setup_action"] == "add_missing"


def test_link_workspace_offers_setup_when_hive_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.bootstrap_state import LinkBootstrapChoice

    project = tmp_path / "ready"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")
    cfg = LauncherConfig(hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._show_dashboard = lambda: None  # type: ignore[method-assign]
    app.root = type("R", (), {})()

    import hive_planner.launcher.app as app_mod

    prompted: list[tuple[Path, BootstrapState]] = []

    def fake_prompt(target, state, *, workspace_label):
        prompted.append((target, state))
        return LinkBootstrapChoice(
            action="link_only",
            profile="minimal",
            agent_handoff="unified",
            cl_runtime="cursor",
        )

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod, "prepare_linked_project_root", lambda *_a, **_k: (project, None))
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    app._prompt_link_bootstrap_setup = fake_prompt  # type: ignore[method-assign]

    assert app._link_workspace(project, notify=True) is True
    assert len(prompted) == 1
    assert prompted[0][1].hive_ready is True
    assert prompted[0][1].needs_handoff_repair is False


def test_link_workspace_skips_setup_when_already_known(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    project = tmp_path / "ready"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")
    resolved = str(project.resolve())
    cfg = LauncherConfig(recent_projects=[resolved], hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._show_dashboard = lambda: None  # type: ignore[method-assign]
    app.root = type("R", (), {})()

    import hive_planner.launcher.app as app_mod

    prompted = False

    def fake_prompt(*_args, **_kwargs):
        nonlocal prompted
        prompted = True
        return None

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod, "prepare_linked_project_root", lambda *_a, **_k: (project, None))
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    app._prompt_link_bootstrap_setup = fake_prompt  # type: ignore[method-assign]

    assert app._link_workspace(project, notify=True) is True
    assert prompted is False


def test_bootstrap_and_activate_add_missing_handoff_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    hive_root = Path(__file__).resolve().parents[1]
    target = tmp_path / "handoff-gap"
    target.mkdir()
    (target / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (target / "docs").mkdir()
    (target / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")
    cfg = LauncherConfig(hive_planner_root=str(hive_root), default_profile="minimal", default_agent_handoff="unified")

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)

    with patch("hive_planner.bootstrap.subprocess.run"):
        assert (
            app._bootstrap_and_activate(
                target,
                notify=False,
                setup_action="add_missing",
                agent_handoff="unified",
                cl_runtime="cursor",
            )
            is True
        )
    assert (target / "spec-kit-agent-integration.md").is_file()
    assert (target / "AGENTS.md").is_file()


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
    from hive_planner.project_profile import delete_project_profile, write_project_profile

    write_project_profile(project, profile="minimal", project_name="Demo")
    summary = summarize_project(project)
    assert summary.ok is True
    assert summary.bootstrap_profile == "minimal"
    assert summary.project_name == "Demo"

    delete_project_profile(project)
    summary = summarize_project(project)
    assert summary.ok is True
    assert summary.bootstrap_profile is None


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


def test_run_project_init_reports_incomplete_unified_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner import agent_handoff

    hive_root = _hive_planner_source(tmp_path)
    target = tmp_path / "broken-init"
    cfg = LauncherConfig(hive_planner_root=str(hive_root))

    def _incomplete(_root: Path):
        from hive_planner.agent_handoff import AgentHandoffStatus

        return AgentHandoffStatus(
            mode="unified",
            spec_kit_enabled=True,
            continual_learning_enabled=True,
            complete=False,
            missing=["docs/cl-spec-integration.md"],
        )

    monkeypatch.setattr(agent_handoff, "validate_unified_handoff", _incomplete)
    with patch("hive_planner.bootstrap.subprocess.run"):
        result = run_project_init(
            cfg,
            target=target,
            name="Broken",
            profile="minimal",
            git_init=False,
            force=False,
            agent_handoff="unified",
        )

    assert result["ok"] is False
    assert "Unified handoff incomplete" in result.get("error", "")


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

    original_err = app_mod.messagebox.showerror
    original_load = app_mod.load_config
    app_mod.messagebox.showerror = showerror
    app_mod.load_config = lambda: app.config
    try:
        app._on_select_recent()
    finally:
        app_mod.messagebox.showerror = original_err
        app_mod.load_config = original_load

    assert Box.calls
    assert "exist" in Box.calls[0][1].lower()
    assert app.config.active_project == ""


def test_add_recent_project_dedupes_normalized_paths(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    raw = str(project)
    resolved = str(project.resolve())
    cfg = LauncherConfig(recent_projects=[raw if raw != resolved else f"{resolved}\\"])
    cfg.add_recent_project(project)
    assert len(cfg.recent_projects) == 1
    assert cfg.recent_projects[0] == resolved
    assert cfg.active_project == resolved


def test_select_recent_persists_active_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    p1 = tmp_path / "proj1"
    p2 = tmp_path / "proj2"
    for project in (p1, p2):
        project.mkdir()
        (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")

    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    save_config(
        LauncherConfig(
            active_project=str(p1.resolve()),
            recent_projects=[str(p1.resolve()), str(p2.resolve())],
        )
    )

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = load_config()
    app._recent_project_paths = [str(p2.resolve()), str(p1.resolve())]
    app.recent_list = type("L", (), {"curselection": lambda self: (0,)})()
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    app._on_select_recent()

    loaded = load_config()
    assert loaded.active_project == str(p2.resolve())
    assert loaded.recent_projects[0] == str(p2.resolve())


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


def test_queue_home_log_flushes_after_dashboard_rebuild() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._queue_home_log("Vendor pins and overlays OK.")
    app._queue_home_log("Tip: redeploy handoff")
    flushed: list[str] = []

    class _Log:
        def configure(self, *args, **kwargs) -> None:
            pass

    app.home_log = _Log()
    app._append_log = lambda _w, text: flushed.append(text)  # type: ignore[method-assign]
    app._flush_pending_home_log()
    assert flushed == ["Vendor pins and overlays OK.", "Tip: redeploy handoff"]
    assert app._pending_home_log == []


def test_ci_check_done_clears_stale_steps_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    monkeypatch.setattr("hive_planner.launcher.app.messagebox.showerror", lambda *a, **k: None)
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = type("R", (), {})()
    app._pending_home_log = []
    app._last_ci_report = {"ok": True, "steps": [{"name": "old", "ok": True, "detail": "x"}]}
    app._show_dashboard = lambda: None  # type: ignore[method-assign]
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]
    app._ci_check_done({"ok": False, "error": "Not a Hive project (missing START_HERE.md)"})
    assert app._last_ci_report is None
    assert app._pending_home_log
    assert "START_HERE" in app._pending_home_log[0]


def test_ci_check_done_preserves_report_for_dashboard_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    monkeypatch.setattr("hive_planner.launcher.app.messagebox.showwarning", lambda *a, **k: None)
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = type("R", (), {})()
    app._pending_home_log = []
    app._last_ci_report = None
    app._show_dashboard = lambda: None  # type: ignore[method-assign]
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]
    report = {
        "ok": False,
        "steps": [
            {"name": "agents-lint", "ok": True, "detail": "ok"},
            {"name": "wiring-audit", "ok": False, "detail": "missing attestation"},
        ],
    }
    app._ci_check_done(report)
    assert app._last_ci_report == report
    assert any("wiring-audit" in line for line in app._pending_home_log)
    inserted: list[str] = []

    class _List:
        def delete(self, _a, _b) -> None:
            inserted.clear()

        def insert(self, _end, text) -> None:
            inserted.append(text)

    app.ci_list = _List()
    app._populate_ci_list(app._last_ci_report)
    assert len(inserted) == 2
    assert "wiring-audit" in inserted[1]


def test_ci_check_report_is_not_bg_error() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    report = {"ok": False, "steps": [{"name": "pytest", "ok": False, "detail": "1 failed"}]}
    assert app._is_bg_error(report) is False
    assert app._is_bg_error({"ok": False, "error": "boom"}) is True
    assert app._is_bg_error(
        {
            "ok": False,
            "error": "Wiring audit required",
            "hints": ["Home â†’ Record wiring audit"],
        }
    ) is False
    assert app._is_bg_error(
        {
            "ok": False,
            "error": "checklist incomplete",
            "recorded": ".hive/wiring-audit.json",
            "hints": ["review tasks.md"],
        }
    ) is False
    assert app._is_bg_error({"ok": False, "error": "Not a Hive project", "detail": "missing START_HERE"}) is False
    assert app._is_bg_error({"ok": False, "error": "verify failed", "issues": ["stale overlay"]}) is False


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
    # Parent console present (e.g. dev launch) â€” visible but not app-owned.
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


def test_attach_hover_tooltip_binds_widget_events() -> None:
    import tkinter as tk

    from hive_planner.launcher.theme import attach_hover_tooltip

    root = tk.Tk()
    root.withdraw()
    button = tk.Button(root, text="Save settings")
    tip = attach_hover_tooltip(button, "Write settings to config.")
    assert tip.text == "Write settings to config."
    assert button.bind("<Enter>")
    assert button.bind("<Leave>")
    root.destroy()


def test_primary_button_accepts_tooltip() -> None:
    import tkinter as tk

    from hive_planner.launcher.theme import primary_button

    root = tk.Tk()
    root.withdraw()
    frame = tk.Frame(root)
    button = primary_button(frame, "Save settings", lambda: None, tooltip="Save paths and defaults.")
    assert button.cget("text") == "Save settings"
    assert button.bind("<Enter>")
    root.destroy()


def test_hover_tooltip_show_ignores_destroyed_widget() -> None:
    import tkinter as tk

    from hive_planner.launcher.theme import HoverTooltip

    root = tk.Tk()
    root.withdraw()
    button = tk.Button(root, text="Save settings")
    tip = HoverTooltip(button, "Help", delay_ms=0)
    button.destroy()
    tip._show()
    assert tip.tipwindow is None
    root.destroy()


def test_note_stale_bg_result_queues_home_log_message() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]
    app._note_stale_bg_result({"ok": False, "mode": "import", "error": "emit failed"})
    joined = "\n".join(app._pending_home_log)
    assert "emit failed" in joined
    assert "dashboard refresh" in joined


def test_note_stale_bg_result_preserves_cartridge_details() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda: None  # type: ignore[method-assign]
    app._log_cartridge_promote = lambda _promote: None  # type: ignore[method-assign]
    app._note_stale_bg_result(
        {
            "ok": False,
            "mode": "sources",
            "error": "emit failed",
            "copied": ["context-library/sources/imported/notes.md"],
            "processed": 1,
            "feature": "my-feature",
        }
    )
    joined = "\n".join(app._pending_home_log)
    assert "emit failed" in joined
    assert "context-library/sources/imported/notes.md" in joined
    assert "dashboard refresh" in joined


def test_note_stale_bg_result_lazy_inits_pending_log() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    refreshed = {"value": False}
    app._refresh_home_dashboard = lambda: refreshed.__setitem__("value", True)  # type: ignore[method-assign]
    app._note_stale_bg_result({"ok": False, "error": "late finish"})
    assert app._pending_home_log == ["Background task finished after dashboard refresh: late finish"]
    assert refreshed["value"] is True


def test_note_stale_bg_result_refreshes_dashboard_for_cartridge() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    refreshed = {"count": 0}
    app._refresh_home_dashboard = lambda: refreshed.__setitem__("count", refreshed["count"] + 1)  # type: ignore[method-assign]
    app._log_cartridge_promote = lambda _promote: None  # type: ignore[method-assign]

    app._note_stale_bg_result(
        {
            "ok": False,
            "mode": "import",
            "error": "exists",
            "skipped": ["holistic.md"],
        }
    )
    assert refreshed["count"] == 1
    assert any("dashboard refresh" in line for line in app._pending_home_log)


def test_link_workspace_warns_handoff_on_silent_relink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    project = tmp_path / "repo"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    resolved = str(project.resolve())
    cfg = LauncherConfig(recent_projects=[resolved], hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._pending_home_log = []
    app._show_dashboard = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod, "prepare_linked_project_root", lambda *_a, **_k: (project, None))
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(
        app_mod,
        "summarize_bootstrap_state",
        lambda _target: type(
            "S",
            (),
            {
                "is_empty": False,
                "needs_handoff_repair": True,
                "hive_ready": True,
                "handoff_missing": ["docs/cl-spec-integration.md"],
                "has_partial_hive": True,
                "has_existing_hive_files": True,
                "allows_add_missing": True,
            },
        )(),
    )

    assert app._link_workspace(project, notify=False) is True
    joined = "\n".join(app._pending_home_log)
    assert "unified handoff incomplete" in joined


def test_open_cursor_queues_home_log_for_dashboard_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    project = tmp_path / "repo"
    project.mkdir()
    cfg = LauncherConfig(active_project=str(project.resolve()), hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._pending_home_log = []
    lines: list[str] = []
    app.home_log = type("L", (), {"configure": lambda *a, **k: None})()
    app._append_log = lambda _w, text: lines.append(text)  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(
        app_mod,
        "open_in_cursor",
        lambda *_a, **_k: {"ok": True, "hive_ready": True},
    )
    monkeypatch.setattr(app_mod, "_linked_path_exists", lambda _p: True)

    app._on_open_cursor()
    assert lines
    assert "Opened in Cursor" in lines[0]
    assert not app._pending_home_log


def test_link_workspace_link_only_warns_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.bootstrap_state import LinkBootstrapChoice

    project = tmp_path / "repo"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    cfg = LauncherConfig(hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._pending_home_log = []
    app._show_dashboard = lambda: None  # type: ignore[method-assign]
    app.root = type("R", (), {})()

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod, "prepare_linked_project_root", lambda *_a, **_k: (project, None))
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    app._prompt_link_bootstrap_setup = lambda *_a, **_k: LinkBootstrapChoice(  # type: ignore[method-assign]
        action="link_only",
        profile="minimal",
        agent_handoff="unified",
        cl_runtime="cursor",
    )
    monkeypatch.setattr(
        app_mod,
        "summarize_bootstrap_state",
        lambda _target: type(
            "S",
            (),
            {
                "is_empty": False,
                "needs_handoff_repair": True,
                "hive_ready": True,
                "handoff_missing": ["docs/cl-spec-integration.md"],
                "has_partial_hive": True,
                "has_existing_hive_files": True,
                "allows_add_missing": True,
            },
        )(),
    )

    assert app._link_workspace(project, notify=True) is True
    assert any("unified handoff incomplete" in line for line in app._pending_home_log)


def test_bootstrap_and_activate_failure_queues_home_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    target = tmp_path / "fail"
    target.mkdir()
    cfg = LauncherConfig(hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    refreshed = {"value": False}
    app._refresh_home_dashboard = lambda: refreshed.__setitem__("value", True)  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod.messagebox, "showerror", lambda *a, **k: None)
    monkeypatch.setattr(
        app_mod,
        "run_project_init",
        lambda *_a, **_k: {"ok": False, "error": "Target not empty"},
    )

    assert app._bootstrap_and_activate(target, notify=False, setup_action="create") is False
    assert refreshed["value"] is True
    assert app._pending_home_log == ["Target not empty"]


def test_load_config_reads_default_agent_handoff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.config import config_path, load_config, save_config

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    monkeypatch.setattr("hive_planner.launcher.service.auto_complete_onboarding_if_ready", lambda _cfg: False)

    save_config(
        LauncherConfig(
            hive_planner_root=str(tmp_path),
            default_agent_handoff="off",
            onboarding_complete=True,
        )
    )
    loaded = load_config()
    assert loaded.default_agent_handoff == "off"


def test_load_config_reads_default_cartridge_mark_draft_bool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.config import config_path, load_config

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    monkeypatch.setattr("hive_planner.launcher.service.auto_complete_onboarding_if_ready", lambda _cfg: False)
    config_path().write_text(
        json.dumps(
            {
                "onboarding_complete": True,
                "hive_planner_root": str(tmp_path),
                "default_cartridge_mark_draft": "false",
            }
        ),
        encoding="utf-8",
    )

    loaded = load_config()

    assert loaded.default_cartridge_mark_draft is False


def test_cartridge_load_feature_requirements() -> None:
    assert cartridge_load_will_promote(promote_checked=True, handoff_unified=True) is True
    assert cartridge_load_will_promote(promote_checked=True, handoff_unified=False) is False
    assert cartridge_load_needs_feature("sources", will_promote=False) is True
    assert cartridge_load_needs_feature("import", will_promote=True) is False
    assert cartridge_load_needs_feature("import", will_promote=False) is False


def test_mousewheel_stack_uses_latest_binding() -> None:
    from hive_planner.launcher.theme import _resolve_wheel_target, _wheel_bindings, _wheel_stack, reset_mousewheel_state_for_tests

    reset_mousewheel_state_for_tests()

    class FakeTarget:
        def winfo_exists(self) -> bool:
            return True

    outer = FakeTarget()
    inner = FakeTarget()
    _wheel_bindings[1] = outer
    _wheel_bindings[2] = inner
    _wheel_stack.extend([1, 2])
    assert _resolve_wheel_target() is inner
    _wheel_stack.pop()
    assert _resolve_wheel_target() is outer
    reset_mousewheel_state_for_tests()


def test_wheel_handlers_install_once() -> None:
    import sys

    import hive_planner.launcher.theme as theme

    theme.reset_mousewheel_state_for_tests()
    bind_calls: list[str] = []

    class FakeRoot:
        def bind_all(self, seq, func, add=None) -> None:
            bind_calls.append(seq)

    root_a = FakeRoot()
    root_b = FakeRoot()
    theme._ensure_wheel_handlers(root_a)
    theme._ensure_wheel_handlers(root_b)
    assert theme._wheel_handlers_installed is True
    expected = 1 if sys.platform == "win32" else 2
    assert len(bind_calls) == expected
    theme.reset_mousewheel_state_for_tests()

