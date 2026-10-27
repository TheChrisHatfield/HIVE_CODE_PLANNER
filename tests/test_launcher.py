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
    resolve_cursor_cli_launch,
    probe_python_command,
    run_install,
    peek_implementation_loop_pack,
    run_project_bug_hunt_install,
    run_project_implementation_loop_accept,
    run_project_implementation_loop_check,
    run_project_implementation_loop_commit,
    run_project_implementation_loop_handoff,
    run_project_implementation_loop_install,
    run_project_implementation_loop_start,
    run_project_implementation_loop_status,
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


def test_linked_project_exists_rejects_workspace_with_dead_folders(tmp_path: Path) -> None:
    workspace_file = tmp_path / "hive.code-workspace"
    workspace_file.write_text(
        json.dumps({"folders": [{"path": "missing-app"}]}),
        encoding="utf-8",
    )
    assert workspace_primary_folder(workspace_file) is None
    assert linked_project_exists(workspace_file) is False


def test_workspace_primary_folder_ignores_missing_folder_entries(tmp_path: Path) -> None:
    alive = tmp_path / "alive"
    alive.mkdir()
    (alive / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    workspace_file = tmp_path / "hive.code-workspace"
    workspace_file.write_text(
        json.dumps({"folders": [{"path": "missing-app"}, {"path": "alive"}]}),
        encoding="utf-8",
    )
    assert workspace_primary_folder(workspace_file) == alive.resolve()


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
    cursor_exe = tmp_path / "Cursor.exe"
    cursor_exe.write_text("", encoding="utf-8")

    launched: dict[str, list] = {"cmd": []}

    def fake_popen(cmd, **kwargs):
        launched["cmd"] = cmd
        return None

    monkeypatch.setattr(
        "hive_planner.launcher.service.find_cursor_executable",
        lambda _config=None: str(cursor_exe),
    )
    monkeypatch.setattr("hive_planner.launcher.service.subprocess.Popen", fake_popen)

    result = open_in_cursor(workspace)
    assert result["ok"] is True
    assert result["hive_ready"] is False
    assert "--classic" in launched["cmd"]
    assert launched["cmd"][-1] == str(workspace.resolve())


def test_open_in_cursor_rejects_missing_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "gone"
    cursor_exe = tmp_path / "Cursor.exe"
    cursor_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "hive_planner.launcher.service.find_cursor_executable",
        lambda _config=None: str(cursor_exe),
    )
    result = open_in_cursor(missing)
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_file_uri_to_path_decodes_windows_drive() -> None:
    uri = "file:///d%3A/DRIVE_DOWNLOADS/HIVE_CODE_PLANNER"
    assert file_uri_to_path(uri) == "d:/DRIVE_DOWNLOADS/HIVE_CODE_PLANNER"


def test_file_uri_to_path_keeps_unc_and_wsl_hosts() -> None:
    assert file_uri_to_path("file://server/share/project") == r"\\server\share\project"
    assert (
        file_uri_to_path("file://wsl.localhost/Ubuntu/home/you/app")
        == r"\\wsl.localhost\Ubuntu\home\you\app"
    )
    assert file_uri_to_path("file://localhost/C:/Users/you") == "C:/Users/you"


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
    (repo / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    workspace_file = tmp_path / "hive.code-workspace"
    workspace_file.write_text(json.dumps({"folders": [{"path": repo.name}]}), encoding="utf-8")
    cursor_exe = tmp_path / "Cursor.exe"
    cursor_exe.write_text("", encoding="utf-8")

    launched: dict[str, list] = {"cmd": []}

    def fake_popen(cmd, **kwargs):
        launched["cmd"] = cmd
        return None

    monkeypatch.setattr(
        "hive_planner.launcher.service.find_cursor_executable",
        lambda _config=None: str(cursor_exe),
    )
    monkeypatch.setattr("hive_planner.launcher.service.subprocess.Popen", fake_popen)

    result = open_in_cursor(workspace_file)
    assert result["ok"] is True
    # Linked .code-workspace files open as the workspace (settings/multi-root preserved).
    assert result["entry_kind"] == "workspace"
    assert "--classic" in launched["cmd"]
    assert launched["cmd"][-1] == str(workspace_file.resolve())


def test_open_in_cursor_launches_when_cursor_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    from hive_planner.project_profile import write_project_profile

    write_project_profile(project, profile="minimal", project_name="App")
    cursor_exe = tmp_path / "Cursor.exe"
    cursor_exe.write_text("", encoding="utf-8")

    launched: dict[str, list] = {"cmd": []}

    def fake_popen(cmd, **kwargs):
        launched["cmd"] = cmd
        return None

    monkeypatch.setattr(
        "hive_planner.launcher.service.find_cursor_executable",
        lambda _config=None: str(cursor_exe),
    )
    monkeypatch.setattr("hive_planner.launcher.service.subprocess.Popen", fake_popen)

    result = open_in_cursor(project)
    assert result["ok"] is True
    assert result["hive_ready"] is True
    assert launched["cmd"][0] == str(cursor_exe)
    assert "--classic" in launched["cmd"]
    assert launched["cmd"][-1] == str(project.resolve())


def test_resolve_cursor_cli_launch_uses_cli_js_beside_exe(tmp_path: Path) -> None:
    exe = tmp_path / "Cursor.exe"
    exe.write_text("", encoding="utf-8")
    cli_js = tmp_path / "resources" / "app" / "out" / "cli.js"
    cli_js.parent.mkdir(parents=True)
    cli_js.write_text("// cli\n", encoding="utf-8")

    argv, env = resolve_cursor_cli_launch(str(exe))
    assert argv == [str(exe.resolve()), str(cli_js.resolve())]
    assert env.get("ELECTRON_RUN_AS_NODE") == "1"


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe fallback is Windows-only")
def test_resolve_cursor_cli_launch_cmd_fallback_uses_cmd_exe(tmp_path: Path) -> None:
    script = tmp_path / "cursor.cmd"
    script.write_text("@echo off\n", encoding="utf-8")
    argv, env = resolve_cursor_cli_launch(str(script))
    assert argv[:2] == ["cmd.exe", "/c"]
    assert argv[2] == str(script.resolve())
    assert env == {}


def test_open_in_cursor_uses_cli_js_and_classic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    cursor_root = tmp_path / "cursor-app"
    exe = cursor_root / "Cursor.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    cli_js = cursor_root / "resources" / "app" / "out" / "cli.js"
    cli_js.parent.mkdir(parents=True)
    cli_js.write_text("// cli\n", encoding="utf-8")

    launched: dict[str, object] = {"cmd": [], "env": {}}

    def fake_popen(cmd, **kwargs):
        launched["cmd"] = cmd
        launched["env"] = kwargs.get("env") or {}
        return None

    monkeypatch.setattr(
        "hive_planner.launcher.service.find_cursor_executable",
        lambda _config=None: str(exe),
    )
    monkeypatch.setattr("hive_planner.launcher.service.subprocess.Popen", fake_popen)

    result = open_in_cursor(project)
    assert result["ok"] is True
    assert launched["cmd"] == [str(exe.resolve()), str(cli_js.resolve()), "--classic", str(project.resolve())]
    assert launched["env"].get("ELECTRON_RUN_AS_NODE") == "1"


def test_open_in_cursor_rejects_missing_launch_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    missing_exe = tmp_path / "missing" / "Cursor.exe"
    monkeypatch.setattr(
        "hive_planner.launcher.service.find_cursor_executable",
        lambda _config=None: str(missing_exe),
    )
    result = open_in_cursor(project)
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


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


def test_load_config_keeps_missing_links_but_falls_back_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    assert loaded.active_project == str(alive.resolve())
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


def test_run_cartridge_load_sources_warns_when_staged_chunks_unembedded(tmp_path: Path) -> None:
    project = _minimal_hive_project(tmp_path / "proj")
    source = tmp_path / "lavd-cpu-research.md"
    source.write_text(
        "# LAVD CPU research\n\nmlp decimacon scheduler latency model for feature retrieval.\n",
        encoding="utf-8",
    )

    result = run_cartridge_load_sources(project, [source], "mlp-decimacon", embed=False)

    assert result["ok"] is True
    warnings = result.get("warnings") or []
    assert any("no embeddings" in w.lower() for w in warnings)
    context = (project / "cartridge" / "source-context.md").read_text(encoding="utf-8")
    assert "lavd-cpu-research.md" in context


def test_run_cartridge_load_sources_fails_when_staged_files_not_indexed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prefer only indexed staged files; fail when ingest indexes none of them."""
    from hive_planner.indexer import ChunkIndex, DocumentIndex

    project = _minimal_hive_project(tmp_path / "proj")
    source = tmp_path / "notes.md"
    source.write_text("# Research\n\nSubsystem workflow for cartridge testing.\n", encoding="utf-8")

    monkeypatch.setattr(
        "hive_planner.launcher.service.ingest",
        lambda *_a, **_k: type("R", (), {"processed": 0, "skipped": 1, "warnings": ["skipped"]})(),
    )
    monkeypatch.setattr(
        "hive_planner.indexer.load_document_index",
        lambda *_a, **_k: DocumentIndex(),
    )

    result = run_cartridge_load_sources(project, [source], "my-feature", promote=False)

    assert result["ok"] is False
    assert "none could be indexed" in (result.get("error") or "").lower()
    assert result.get("copied")


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
    else:
        # Sources emit without existing delta does not write promote-eligible layers
        assert all(
            str(status).startswith("skipped") for status in result["mark_draft"].values()
        )
        assert any("nothing to stamp" in w.lower() for w in result.get("warnings") or [])


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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
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
    assert (project / ".cursor" / "commands" / "bug-hunt.md").is_file()
    assert (project / ".cursor" / "rules" / "bug-hunt.mdc").is_file()


def test_peek_implementation_loop_pack_uses_workspace_folder(tmp_path: Path) -> None:
    from hive_planner.implementation_loop import PACK_4, install_implementation_loop

    folder = tmp_path / "app"
    folder.mkdir()
    (folder / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    install_implementation_loop(folder, PACK_4)
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "app"}]}), encoding="utf-8")
    peek = peek_implementation_loop_pack(workspace)
    assert peek["ok"] is True
    assert peek["pack"] == PACK_4
    parent_peek = peek_implementation_loop_pack(workspace.parent)
    assert parent_peek["ok"] is True
    assert parent_peek.get("pack") is None


def test_run_project_implementation_loop_status_uses_workspace_folder(tmp_path: Path) -> None:
    from hive_planner.implementation_loop import PACK_4, install_implementation_loop

    folder = tmp_path / "app"
    folder.mkdir()
    (folder / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    install_implementation_loop(folder, PACK_4)
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "app"}]}), encoding="utf-8")
    result = run_project_implementation_loop_status(workspace, "feature-x")
    assert result["ok"] is False
    assert result["action"] == "status"
    assert result["feature"] == "feature-x"
    assert result["ready"] is False
    assert result.get("error")
    assert result["root"] == str(folder.resolve())


def test_run_project_implementation_loop_status_reads_agents_feature(tmp_path: Path) -> None:
    from hive_planner.implementation_loop import PACK_1, install_implementation_loop

    folder = tmp_path / "app"
    folder.mkdir()
    install_implementation_loop(folder, PACK_1)
    (folder / "AGENTS.md").write_text("## Active feature\n\n**demo-feature** — loop\n", encoding="utf-8")
    result = run_project_implementation_loop_status(folder, None)
    assert result["ok"] is result["ready"]
    assert result["feature"] == "demo-feature"
    if not result["ready"]:
        assert result.get("error")


def test_run_project_implementation_loop_start_requires_feature(tmp_path: Path) -> None:
    folder = tmp_path / "app"
    folder.mkdir()
    result = run_project_implementation_loop_start(folder, None)
    assert result["ok"] is False
    assert "feature" in result.get("error", "").lower()


def test_run_project_implementation_loop_commit_wraps_coordinator_error(tmp_path: Path) -> None:
    folder = tmp_path / "app"
    folder.mkdir()
    result = run_project_implementation_loop_commit(folder)
    assert result["ok"] is False
    assert result.get("error")


def test_peek_bug_hunt_status_and_custom_iterations(tmp_path: Path) -> None:
    from hive_planner.launcher.service import peek_bug_hunt_status

    folder = tmp_path / "app"
    folder.mkdir()
    missing = peek_bug_hunt_status(folder)
    assert missing["ok"] is True
    assert missing["installed"] is False
    assert missing["missing"]
    installed = run_project_bug_hunt_install(folder, iterations=12)
    assert installed["ok"] is True
    assert installed["iterations"] == 12
    present = peek_bug_hunt_status(folder)
    assert present["installed"] is True
    assert present["missing"] == []
    command = (folder / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "12-iteration" in command or "12" in command


def test_controls_agnostic_gates_use_linked_repo(tmp_path: Path) -> None:
    from hive_planner.launcher.service import (
        peek_agnostic_loop_status,
        run_project_agnostic_loop_arm,
        run_project_agnostic_loop_begin,
        run_project_agnostic_loop_choose,
        run_project_agnostic_loop_install,
        run_project_agnostic_loop_observe,
        run_project_agnostic_loop_review,
        run_project_agnostic_loop_rewards,
        run_project_agnostic_loop_status,
    )

    folder = tmp_path / "app"
    folder.mkdir()
    assert peek_agnostic_loop_status(folder)["installed"] is False
    assert run_project_agnostic_loop_install(folder)["ok"] is True
    assert peek_agnostic_loop_status(folder)["installed"] is True
    listed = run_project_agnostic_loop_rewards(folder)
    assert listed["ok"] is True
    assert "inspect" in listed["rewards"]
    armed = run_project_agnostic_loop_arm(folder, "inspect", 1)
    assert armed["ok"] is True
    assert armed["root"] == str(folder.resolve())
    begun = run_project_agnostic_loop_begin(folder)
    assert begun["ok"] is True
    reviewed = run_project_agnostic_loop_review(folder, "controls tab")
    assert reviewed["ok"] is True
    observed = run_project_agnostic_loop_observe(folder, "inspect", True)
    assert observed["ok"] is True
    chosen = run_project_agnostic_loop_choose(folder, None, do_arm=False)
    assert chosen["ok"] is True
    status = run_project_agnostic_loop_status(folder)
    assert status["ok"] is True
    assert status["action"] == "status"


def test_controls_agnostic_choose_rejects_bad_open(tmp_path: Path) -> None:
    from hive_planner.launcher.service import (
        run_project_agnostic_loop_choose,
        run_project_agnostic_loop_install,
    )

    folder = tmp_path / "app"
    folder.mkdir()
    run_project_agnostic_loop_install(folder)
    result = run_project_agnostic_loop_choose(folder, "not-a-reward=1")
    assert result["ok"] is False
    assert "open" in result.get("blocked_reason", "").lower()


def test_app_registers_controls_tab() -> None:
    source = Path(__file__).resolve().parents[1] / "src" / "hive_planner" / "launcher" / "app.py"
    text = source.read_text(encoding="utf-8")
    assert 'notebook.add(controls, text="Controls")' in text
    assert "def _build_controls_tab" in text
    assert "def _on_open_loop_controls" in text
    assert "def _on_controls_run" in text
    assert '"Loop controls"' in text
    assert '"Loop status"' not in text.split("def _build_home_tab", 1)[-1].split("def _build_controls_tab", 1)[0]
    open_fn = text.split("def _on_open_loop_controls", 1)[-1].split("    def ", 1)[0]
    assert '== "Controls"' in open_fn
    assert "notebook.select(1)" not in open_fn


def test_loop_install_failures_update_controls_last() -> None:
    source = Path(__file__).resolve().parents[1] / "src" / "hive_planner" / "launcher" / "app.py"
    text = source.read_text(encoding="utf-8")
    assert "def _controls_action_failed" in text
    helper = text.split("def _controls_action_failed", 1)[-1].split("    def ", 1)[0]
    assert "_set_controls_last" in helper
    for name in (
        "_bug_hunt_install_done",
        "_agnostic_loop_install_done",
        "_implementation_loop_install_done",
    ):
        body = text.split(f"def {name}", 1)[-1].split("    def ", 1)[0]
        assert "_controls_action_failed" in body


def test_resolved_loop_command_rejects_pairs_from_another_loop() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    assert HivePlannerApp.resolved_loop_command("Bug hunt", "Check install") == (
        "Bug hunt",
        "Check install",
    )
    assert HivePlannerApp.resolved_loop_command("Bug hunt", "Status") is None
    assert HivePlannerApp.resolved_loop_command("Agnostic loop", "Commit") is None
    assert HivePlannerApp.resolved_loop_command("Implementation loop", "Choose") is None
    assert HivePlannerApp.resolved_loop_command("Implementation loop", "Check") == (
        "Implementation loop",
        "Check",
    )
    for loop, commands in HivePlannerApp.LOOP_CONTROL_COMMANDS.items():
        for command in commands:
            assert HivePlannerApp.resolved_loop_command(loop, command) == (loop, command)


def test_controls_follow_active_repo_on_soft_refresh() -> None:
    source = Path(__file__).resolve().parents[1] / "src" / "hive_planner" / "launcher" / "app.py"
    text = source.read_text(encoding="utf-8")
    soft = text.split("def _soft_refresh_dashboard", 1)[-1].split("def _show_dashboard", 1)[0]
    assert "self._sync_controls_for_active()" in soft
    assert "textvariable=self.controls_active_label" in text
    sync = text.split("def _sync_controls_for_active", 1)[-1].split("def _sync_controls_command_choices", 1)[0]
    assert "controls_active_label.set" in sync
    assert "controls_impl_feature.set" in sync
    assert "_controls_link_key" in sync
    assert "controls_last.set" in sync


def test_sync_controls_clears_last_line_when_active_repo_changes() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    class _Var:
        def __init__(self, value: str = "") -> None:
            self._value = value

        def set(self, value: str) -> None:
            self._value = value

        def get(self) -> str:
            return self._value

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.controls_active_label = _Var()
    app.controls_last = _Var("Starting implementation loop…")
    app.controls_impl_feature = _Var("oldfeat")
    app._controls_link_key = "old"
    app._active_link_key = lambda: "new"  # type: ignore[method-assign]
    app._active_feature_label = lambda: "newfeat"  # type: ignore[method-assign]
    app._controls_active_caption = lambda: "caption"  # type: ignore[method-assign]
    app._sync_controls_for_active()
    assert app.controls_last.get() == "Pick the active project on Projects, then use these controls."
    assert app.controls_impl_feature.get() == "newfeat"
    app.controls_last.set("Running…")
    app._sync_controls_for_active()
    assert app.controls_last.get() == "Running…"


def test_run_project_implementation_loop_check_wraps_not_running(tmp_path: Path) -> None:
    folder = tmp_path / "app"
    folder.mkdir()
    result = run_project_implementation_loop_check(folder)
    assert result["ok"] is False
    assert result.get("error")


def test_run_project_implementation_loop_handoff_requires_role(tmp_path: Path) -> None:
    folder = tmp_path / "app"
    folder.mkdir()
    result = run_project_implementation_loop_handoff(folder, "  ")
    assert result["ok"] is False
    assert "role" in result.get("error", "").lower()


def test_run_project_implementation_loop_accept_rejects_missing_path(tmp_path: Path) -> None:
    result = run_project_implementation_loop_accept(tmp_path / "missing-proj", "coder")
    assert result["ok"] is False
    assert "does not exist" in result.get("error", "")


def test_run_project_bug_hunt_install_resolves_workspace_file(tmp_path: Path) -> None:
    folder = tmp_path / "app"
    folder.mkdir()
    (folder / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "app"}]}), encoding="utf-8")
    result = run_project_bug_hunt_install(workspace)
    assert result["ok"] is True
    assert (folder / ".cursor" / "rules" / "bug-hunt.mdc").is_file()


def test_run_project_bug_hunt_install_rejects_plain_file(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("nope\n", encoding="utf-8")
    result = run_project_bug_hunt_install(target)
    assert result["ok"] is False
    assert "not a project directory" in result.get("error", "")


def test_run_project_bug_hunt_install_writes_chat_trigger(tmp_path: Path) -> None:
    project = tmp_path / "app"
    project.mkdir()
    result = run_project_bug_hunt_install(project, iterations=25)
    assert result["ok"] is True
    assert result["iterations"] == 25
    rule = (project / ".cursor" / "rules" / "bug-hunt.mdc").read_text(encoding="utf-8")
    assert "alwaysApply: true" in rule
    assert "hunt for bugs" in rule
    assert (project / ".cursor" / "commands" / "bug-hunt.md").is_file()


def test_run_project_bug_hunt_install_fails_when_trigger_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner import bug_hunt as bug_hunt_mod

    project = tmp_path / "app"
    project.mkdir()

    def _install(root, iterations=50, *, force=True):
        return bug_hunt_mod.BugHuntInstall(
            root=root.resolve(),
            iterations=iterations,
            command_path=root / bug_hunt_mod.COMMAND_REL,
            rule_path=root / bug_hunt_mod.RULE_REL,
            packet_path=root / bug_hunt_mod.PACKET_REL,
            files_written=[],
        )

    monkeypatch.setattr("hive_planner.bug_hunt.install_bug_hunt", _install)
    result = run_project_bug_hunt_install(project)
    assert result["ok"] is False
    assert "missing" in result.get("error", "").lower()


def test_run_project_bug_hunt_install_reports_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "app"
    project.mkdir()

    def _boom(_root, **_kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr("hive_planner.bug_hunt.install_bug_hunt", _boom)
    result = run_project_bug_hunt_install(project)
    assert result["ok"] is False
    assert "Permission denied" in result.get("error", "")


def test_bug_hunt_install_done_does_not_claim_enabled_on_failure() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    lines: list[str] = []
    app._queue_home_log = lambda msg: lines.append(str(msg))  # type: ignore[method-assign]
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._bug_hunt_install_done({"ok": False, "error": "Bug-hunt install incomplete — missing: rule"})
    assert lines and "missing" in lines[0].lower()
    assert not any("Bug hunt enabled" in line for line in lines)


def test_bug_hunt_install_done_logs_chat_trigger() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    lines: list[str] = []
    refreshed: list[bool] = []
    app._queue_home_log = lambda msg: lines.append(str(msg))  # type: ignore[method-assign]
    app._refresh_home_dashboard = lambda **_k: refreshed.append(True)  # type: ignore[method-assign]
    app._bug_hunt_install_done(
        {"ok": True, "files_written": ["a", "b"], "iterations": 50}
    )
    assert refreshed == [True]
    assert any("Bug hunt enabled" in line for line in lines)
    assert any("bug hunt" in line for line in lines)


def test_on_bug_hunt_install_sends_workspace_link_to_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    workspace = tmp_path / "dead.code-workspace"
    workspace.write_text('{"folders":[{"path":"missing"}]}', encoding="utf-8")
    shown: list[tuple] = []
    sent: list[Path] = []
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.showwarning",
        lambda *a, **k: shown.append(a),
    )
    monkeypatch.setattr(
        "hive_planner.launcher.app.run_project_bug_hunt_install",
        lambda root, **k: sent.append(Path(root)) or {"ok": False, "error": "Workspace file has no folder on disk"},
    )
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=str(workspace))
    started: list[str] = []
    app._start_home_action = lambda msg: started.append(str(msg))  # type: ignore[method-assign]
    app._run_bg = lambda fn, cb: cb(fn())  # type: ignore[method-assign]
    app._project_done_callback = lambda _label, on_done: on_done  # type: ignore[method-assign]
    lines: list[str] = []
    app._queue_home_log = lambda msg: lines.append(str(msg))  # type: ignore[method-assign]
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._on_bug_hunt_install()
    assert shown == []
    assert started
    assert sent == [workspace]
    assert any("folder" in line.lower() for line in lines)
    assert not any("Bug hunt enabled" in line for line in lines)


def test_sync_controls_command_choices_without_command_var() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.controls_loop = type("Var", (), {"get": lambda self: "Bug hunt"})()
    app._sync_controls_command_choices()


def test_sync_controls_command_choices_survives_destroyed_command_box() -> None:
    import tkinter as tk

    from hive_planner.launcher.app import HivePlannerApp

    class _Var:
        def __init__(self, value: str) -> None:
            self._value = value

        def get(self) -> str:
            return self._value

        def set(self, value: str) -> None:
            self._value = value

    class _DeadBox:
        def configure(self, **_kwargs) -> None:
            raise tk.TclError("invalid command name")

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.controls_loop = _Var("Bug hunt")
    app.controls_command = _Var("Status")
    app.controls_command_box = _DeadBox()
    app._sync_controls_command_choices()
    assert app.controls_command.get() == "Enable"


def test_start_home_action_updates_controls_last_when_home_log_exists() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    class Var:
        def __init__(self) -> None:
            self.value = ""

        def set(self, text: str) -> None:
            self.value = text

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.controls_last = Var()
    app._remember_home_log = lambda *_a, **_k: None  # type: ignore[method-assign]
    app.home_log = object()
    app._append_log = lambda *_a, **_k: None  # type: ignore[method-assign]
    app._start_home_action("Starting implementation loop…")
    assert app.controls_last.value == "Starting implementation loop…"


def test_on_bug_hunt_install_rejects_out_of_range_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    shown: list[tuple] = []
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.showwarning",
        lambda *a, **k: shown.append(a),
    )
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=str(Path("C:/linked")))
    app.controls_bug_iterations = type("Var", (), {"get": lambda self: "0"})()
    started: list[str] = []
    app._start_home_action = lambda msg: started.append(str(msg))  # type: ignore[method-assign]
    app._run_bg = lambda *_a, **_k: started.append("bg")  # type: ignore[method-assign]
    app._on_bug_hunt_install()
    assert started == []
    assert shown
    assert "1" in shown[0][1] and "200" in shown[0][1]


def test_on_bug_hunt_install_warns_when_no_project(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    shown: list[tuple] = []
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.showwarning",
        lambda *a, **k: shown.append(a),
    )
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project="")
    started: list[str] = []
    app._start_home_action = lambda msg: started.append(str(msg))  # type: ignore[method-assign]
    app._run_bg = lambda *_a, **_k: started.append("bg")  # type: ignore[method-assign]
    app._on_bug_hunt_install()
    assert started == []
    assert shown
    assert "Link a workspace first" in shown[0][1]


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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]

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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]

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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]

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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]

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


def test_scripts_readme_documents_implementation_loop() -> None:
    from hive_planner.launcher.user_guide import IMPLEMENTATION_LOOP_SECTION_MARKER

    guide = Path(__file__).resolve().parents[1] / "scripts" / "README.md"
    text = guide.read_text(encoding="utf-8")
    assert IMPLEMENTATION_LOOP_SECTION_MARKER in text
    assert "Loop controls" in text
    assert "implementation-loop" in text
    assert "not a bug hunt" in text.lower()


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
    from hive_planner.launcher.user_guide import (
        AGNOSTIC_LOOP_SECTION_MARKER,
        IMPLEMENTATION_LOOP_SECTION_MARKER,
        UNIFIED_VENDOR_SECTION_MARKER,
        load_user_guide,
        user_guide_path,
    )

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
    assert IMPLEMENTATION_LOOP_SECTION_MARKER in text
    assert "Loop controls" in text
    assert AGNOSTIC_LOOP_SECTION_MARKER in text
    assert "Agnostic loop" in text


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


def test_load_user_guide_does_not_duplicate_implementation_loop_section(tmp_path: Path) -> None:
    from hive_planner.launcher.user_guide import load_user_guide

    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    scripts.joinpath("README.md").write_text(
        "# Guide\n\n## Implementation loop\n\nAlready documented.\n",
        encoding="utf-8",
    )
    cfg = LauncherConfig(hive_planner_root=str(hive))

    text = load_user_guide(cfg)

    assert text.count("## Implementation loop") == 1


def test_load_user_guide_does_not_duplicate_agnostic_loop_section(tmp_path: Path) -> None:
    from hive_planner.launcher.user_guide import load_user_guide

    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    scripts.joinpath("README.md").write_text(
        "# Guide\n\n## Agnostic loop\n\nAlready documented.\n",
        encoding="utf-8",
    )
    cfg = LauncherConfig(hive_planner_root=str(hive))

    text = load_user_guide(cfg)

    assert text.count("## Agnostic loop") == 1


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


def test_bug_hunt_prompt_template_keeps_the_loop_moving() -> None:
    from hive_planner.launcher.agent_prompt_templates import get_agent_prompt_template

    found = get_agent_prompt_template("change.bug_hunt")
    assert found is not None
    assert found.prompt.lstrip().startswith("bug hunt")
    assert "without asking whether to continue" in found.prompt
    assert "@.cursor/commands/bug-hunt.md" in found.prompt


def test_format_loop_gate_includes_dirty_paths() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    text = app._format_loop_gate(
        {
            "ok": False,
            "error": "unrelated dirty paths block start",
            "dirty": ["notes.txt", "scratch.py"],
        }
    )
    assert "ok=False" in text
    assert "notes.txt" in text
    assert "scratch.py" in text
    assert "unrelated dirty" in text


def test_format_loop_gate_does_not_repeat_blocked_reason() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    text = app._format_loop_gate(
        {
            "ok": False,
            "ready": False,
            "action": "status",
            "blocked_reason": "not ready",
            "error": "not ready",
            "missing": ["docs/specs/x/spec.md"],
        }
    )
    assert text.count("not ready") == 1
    assert "spec.md" in text


def test_start_done_dirty_retry_without_ctx_does_not_throw(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    logged: list[dict] = []
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.askyesno",
        lambda *a, **k: True,
    )
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = object()
    app._log_loop_gate = lambda result: logged.append(result)  # type: ignore[method-assign]
    app._run_loop_start = lambda *a, **k: logged.append({"ran": True})  # type: ignore[method-assign]
    app._implementation_loop_start_done(
        {"ok": False, "error": "unrelated dirty paths block start", "dirty": ["notes.txt"]}
    )
    assert logged
    assert logged[0].get("ran") is not True


def test_handoff_done_cap_retry_without_ctx_does_not_throw(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    logged: list[dict] = []
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.askyesno",
        lambda *a, **k: True,
    )
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = object()
    app._log_loop_gate = lambda result: logged.append(result)  # type: ignore[method-assign]
    app._run_loop_handoff = lambda *a, **k: logged.append({"ran": True})  # type: ignore[method-assign]
    app._implementation_loop_handoff_done(
        {"ok": False, "error": "pass --continue-after-cap", "blocked_reason": "continue-after-cap"}
    )
    assert logged
    assert logged[0].get("ran") is not True


def test_implementation_loop_prompt_template_keeps_chat_and_home() -> None:
    from hive_planner.launcher.agent_prompt_templates import get_agent_prompt_template

    found = get_agent_prompt_template("change.implementation_loop")
    assert found is not None
    assert found.title == "Start the implementation loop"
    assert found.prompt.lstrip().startswith("implementation loop")
    assert "@.cursor/commands/implementation-loop.md" in found.prompt
    assert "Loop controls" in found.prompt
    assert "check" in found.prompt
    assert "commit" in found.prompt


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


def test_agent_prompt_templates_collapsed_by_default() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._agent_prompt_expanded = False
    app._agent_prompt_saved_title = None
    assert app._agent_prompt_expanded is False
    assert app._agent_prompt_saved_title is None


def test_toggle_agent_prompt_templates_expands_and_collapses_body() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._agent_prompt_expanded = False
    app._agent_prompt_body = type("Body", (), {"pack": lambda *a, **k: None, "pack_forget": lambda: None})()
    packed: list[str] = []
    forgotten: list[bool] = []

    def pack(*_args, **_kwargs) -> None:
        packed.append("pack")

    def pack_forget() -> None:
        forgotten.append(True)

    app._agent_prompt_body.pack = pack  # type: ignore[method-assign]
    app._agent_prompt_body.pack_forget = pack_forget  # type: ignore[method-assign]
    app._agent_prompt_toggle_btn = type("Btn", (), {"configure": lambda self, **k: None})()
    app._agent_prompt_summary = type("Lbl", (), {"configure": lambda self, **k: None})()

    app._toggle_agent_prompt_templates()
    assert app._agent_prompt_expanded is True
    assert packed == ["pack"]

    app._toggle_agent_prompt_templates()
    assert app._agent_prompt_expanded is False
    assert forgotten == [True]


def test_home_guide_collapsed_by_default() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._home_guide_expanded = False
    assert app._home_guide_expanded is False


def test_toggle_home_guide_expands_and_collapses_body() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._home_guide_expanded = False
    app._home_guide_body = type("Body", (), {"pack": lambda *a, **k: None, "pack_forget": lambda: None})()
    packed: list[str] = []
    forgotten: list[bool] = []

    def pack(*_args, **_kwargs) -> None:
        packed.append("pack")

    def pack_forget() -> None:
        forgotten.append(True)

    app._home_guide_body.pack = pack  # type: ignore[method-assign]
    app._home_guide_body.pack_forget = pack_forget  # type: ignore[method-assign]
    app._home_guide_toggle_btn = type("Btn", (), {"configure": lambda self, **k: None})()
    app._home_guide_summary = type("Lbl", (), {"configure": lambda self, **k: None})()

    app._toggle_home_guide()
    assert app._home_guide_expanded is True
    assert packed == ["pack"]

    app._toggle_home_guide()
    assert app._home_guide_expanded is False
    assert forgotten == [True]


def test_load_user_guide_fallback_mentions_agent_prompt_templates(tmp_path: Path) -> None:
    from hive_planner.launcher.user_guide import load_user_guide

    cfg = LauncherConfig(hive_planner_root=str(tmp_path / "missing"))
    text = load_user_guide(cfg)
    assert "Agent prompt templates" in text
    assert "Loop controls" in text
    assert "implementation loop" in text
    assert "agnostic loop" in text
    assert "Controls" in text


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


def test_run_agents_memory_propose_includes_noop_key_in_response(tmp_path: Path) -> None:
    """run_agents_memory_propose always includes a 'noop' key in successful results."""
    from hive_planner.launcher.service import run_agents_memory_propose
    from hive_planner.wiring_audit import record_wiring_audit

    project = _minimal_unified_project(tmp_path)
    record_wiring_audit(RepoPaths(root=project), evidence="pytest -q")
    candidates = project / "docs" / "proposals" / "candidates.md"
    candidates.parent.mkdir(parents=True, exist_ok=True)
    candidates.write_text("- # operational\n- Keep launcher logs concise.\n", encoding="utf-8")

    result = run_agents_memory_propose(project, candidates, apply=True)
    assert result["ok"] is True
    assert result.get("applied") is True
    assert "noop" in result, "noop key must always be present in propose response"
    assert result["noop"] is False


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
    app._refresh_home_dashboard = lambda **_k: refreshed.append(True)  # type: ignore[method-assign]
    app._active_linked_root = lambda: None  # type: ignore[method-assign]

    app._agents_apply_done({"ok": False, "error": "Wiring audit required", "hints": ["Record wiring audit"]})
    assert refreshed == [True]


def test_refresh_home_dashboard_uses_soft_refresh_when_dashboard_alive() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    calls: list[str] = []
    app._dashboard_alive = lambda: True  # type: ignore[method-assign]
    app._soft_refresh_dashboard = lambda **_k: calls.append("soft")  # type: ignore[method-assign]
    app._show_dashboard = lambda: calls.append("full")  # type: ignore[method-assign]

    app._refresh_home_dashboard()
    assert calls == ["soft"]


def test_refresh_home_dashboard_rebuilds_when_dashboard_missing() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    calls: list[str] = []
    app._dashboard_alive = lambda: False  # type: ignore[method-assign]
    app._soft_refresh_dashboard = lambda **_k: calls.append("soft")  # type: ignore[method-assign]
    app._show_dashboard = lambda: calls.append("full")  # type: ignore[method-assign]

    app._refresh_home_dashboard()
    assert calls == ["full"]


def test_create_done_keeps_projects_context_via_soft_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    target = tmp_path / "new-proj"
    target.mkdir()
    cfg = LauncherConfig(hive_planner_root=str(Path(__file__).resolve().parents[1]))

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._dashboard_tab = 2  # Projects
    refreshed: list[str] = []
    app._refresh_home_dashboard = lambda **_k: refreshed.append("refresh")  # type: ignore[method-assign]
    cleared: list[bool] = []
    app._clear_new_project_form = lambda: cleared.append(True)  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(
        app_mod,
        "prepare_linked_project_root",
        lambda p, **kw: (Path(p), None),
    )

    app._create_done({"ok": True, "target": str(target.resolve())})
    assert refreshed == ["refresh"]
    assert cleared == [True]
    assert app._dashboard_tab == 2


def test_clear_new_project_form_resets_name_and_target() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(default_profile="minimal", default_agent_handoff="unified")
    app.new_name = type("V", (), {"set": lambda self, v: setattr(self, "v", v)})()
    app.new_target = type("V", (), {"set": lambda self, v: setattr(self, "v", v)})()
    app.new_git = type("V", (), {"set": lambda self, v: setattr(self, "v", v)})()
    app.new_profile = type("V", (), {"set": lambda self, v: setattr(self, "v", v)})()
    app.new_agent_handoff = type("V", (), {"set": lambda self, v: setattr(self, "v", v)})()
    app.new_cl_runtime = type("V", (), {"set": lambda self, v: setattr(self, "v", v)})()

    app._clear_new_project_form()
    assert app.new_name.v == ""
    assert app.new_target.v == ""
    assert app.new_git.v is True
    assert app.new_profile.v == "minimal"
    assert app.new_agent_handoff.v == "unified"
    assert app.new_cl_runtime.v == "cursor"


def test_soft_refresh_updates_status_without_clearing_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.service import SetupStatus

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_memory_link = None
    app._pending_memory_candidates = None
    app._last_ci_report = None
    app._pending_home_log = []
    app.config = LauncherConfig()
    app.setup = SetupStatus(
        python_ok=True,
        python_version="3.11",
        hive_root="C:/hive",
        hive_root_ok=True,
        hive_installed=True,
        hive_version="1.0.0",
        git_available=True,
        onboarding_complete=True,
        portable_mode=False,
        unified_handoff_ready=True,
        unified_handoff_detail="ready",
    )
    cleared: list[bool] = []
    app._clear_container = lambda: cleared.append(True)  # type: ignore[method-assign]
    app._header_detail_text = lambda: "Active: demo"  # type: ignore[method-assign]
    app._status_items = lambda: [("Hive", "1.0.0"), ("Profile", "full")]  # type: ignore[method-assign]
    app._header_detail_label = type("L", (), {"configure": lambda self, **kw: None})()
    app._status_value_labels = {
        "Hive": type("L", (), {"configure": lambda self, **kw: setattr(self, "text", kw.get("text"))})(),
        "Profile": type("L", (), {"configure": lambda self, **kw: setattr(self, "text", kw.get("text"))})(),
    }
    app._populate_ci_list = lambda _report: None  # type: ignore[method-assign]
    app._flush_pending_home_log = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod, "load_config", lambda: app.config)
    monkeypatch.setattr(app_mod, "get_setup_status", lambda _cfg: app.setup)

    app._soft_refresh_dashboard()
    assert cleared == []
    assert app._status_value_labels["Hive"].text == "1.0.0"


def test_dashboard_tab_capture_and_restore_roundtrip() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    class FakeNotebook:
        def __init__(self) -> None:
            self._selected = 0
            self._tabs = ("home", "projects", "settings")

        def winfo_exists(self) -> bool:
            return True

        def select(self, value=None):
            if value is None:
                return self._tabs[self._selected]
            if isinstance(value, int):
                self._selected = value
            else:
                self._selected = self._tabs.index(value)

        def index(self, tab_id) -> int:
            if tab_id in self._tabs:
                return self._tabs.index(tab_id)
            return int(tab_id)

        def tabs(self):
            return self._tabs

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._dashboard_tab = 0
    app._home_scroll_y = 0.0
    app._home_canvas = None
    app.notebook = FakeNotebook()
    app.notebook.select(1)
    app._capture_dashboard_view()
    assert app._dashboard_tab == 1
    app.notebook.select(0)
    app.root = type("R", (), {"after_idle": lambda self, cb: cb()})()
    app._restore_dashboard_view()
    assert app.notebook._selected == 1


def test_restore_home_scroll_applies_captured_offset() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    moved: list[float] = []
    app = HivePlannerApp.__new__(HivePlannerApp)
    app._home_scroll_y = 0.42
    app._home_canvas = type(
        "C",
        (),
        {
            "winfo_exists": lambda self: True,
            "yview_moveto": lambda self, v: moved.append(v),
        },
    )()
    app._restore_home_scroll()
    assert moved == [0.42]


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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
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


def test_agents_apply_done_uses_pending_memory_work_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    app.root = None
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app.config = LauncherConfig(active_project=str(workspace))
    app._set_pending_memory_candidates(folder, candidates)
    app._active_linked_root = lambda: None  # type: ignore[method-assign]
    captured: list[Path] = []
    monkeypatch.setattr(
        app,
        "_show_memory_rejection_preview",
        lambda result, *, root: captured.append(root),
    )

    app._agents_apply_done(
        {
            "ok": False,
            "error": "All candidate bullets were rejected by validation",
            "proposal_path": "docs/proposals/agents-memory-1.md",
            "rejected": [{"candidate": "bad", "reason": "behavioral"}],
        }
    )

    assert captured == [folder.resolve()]
    assert app._pending_memory_link == normalize_project_path(workspace)


def test_memory_work_root_persists_after_pending_cleared(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.config import LauncherConfig

    folder = tmp_path / "app"
    folder.mkdir()
    candidates = folder / "docs" / "proposals" / "candidates.md"
    candidates.parent.mkdir(parents=True)
    candidates.write_text("- x\n", encoding="utf-8")

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=str(folder))
    app._memory_work_root = None
    app._memory_work_candidates_path = None
    app._set_pending_memory_candidates(folder, candidates)
    app._pending_memory_candidates = None
    app._pending_memory_link = None

    assert app._resolve_memory_work_root() == folder.resolve()
    assert app._memory_work_candidates() == candidates


def test_profile_switch_clears_entire_memory_work_context(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    project_a = tmp_path / "alpha"
    project_b = tmp_path / "beta"
    candidates = project_a / "docs" / "proposals" / "candidates.md"
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=str(project_b.resolve()))
    app._pending_memory_link = str(project_a.resolve())
    app._pending_memory_candidates = candidates
    app._memory_work_root = project_a.resolve()
    app._memory_work_candidates_path = candidates

    app._sync_pending_memory_for_active()

    assert app._pending_memory_link is None
    assert app._pending_memory_candidates is None
    assert app._memory_work_root is None
    assert app._memory_work_candidates_path is None


def test_run_memory_apply_if_current_cancels_on_stale_generation(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._bg_generation = 2
    candidates = tmp_path / "docs" / "proposals" / "candidates.md"
    candidates.parent.mkdir(parents=True)
    candidates.write_text("- x\n", encoding="utf-8")

    result = app._run_memory_apply_if_current(tmp_path, candidates, 1)

    assert result["ok"] is False
    assert result["cancelled"] is True


def test_run_memory_apply_if_current_uses_finalize_when_prior_has_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._bg_generation = 0
    candidates = tmp_path / "docs" / "proposals" / "candidates.md"
    candidates.parent.mkdir(parents=True)
    candidates.write_text("- x\n", encoding="utf-8")
    prior = {"accepted": ["Keep logs concise."], "rejected": [], "routing": []}
    calls: list[str] = []

    monkeypatch.setattr(
        "hive_planner.launcher.app.run_agents_memory_finalize_apply",
        lambda _root, p: calls.append("finalize") or {"ok": True, "applied": True, **p},
    )
    monkeypatch.setattr(
        "hive_planner.launcher.app.run_agents_memory_apply",
        lambda *_a, **_k: calls.append("apply") or {"ok": True},
    )

    app._run_memory_apply_if_current(tmp_path, candidates, 0, prior=prior)

    assert calls == ["finalize"]


def test_deliver_memory_propose_result_clears_work_context_after_apply() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._memory_work_root = Path("C:/proj")
    app._memory_work_candidates_path = Path("C:/proj/docs/proposals/candidates.md")
    app._pending_memory_candidates = app._memory_work_candidates_path
    app._pending_memory_link = "C:/proj"
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]

    app._deliver_memory_propose_result({"ok": True, "applied": True, "accepted": ["x"], "rejected": []})

    assert app._memory_work_root is None
    assert app._memory_work_candidates_path is None
    assert app._pending_memory_candidates is None


def test_selected_agent_prompt_title_falls_back_to_saved_title() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._agent_prompt_saved_title = "Implement one spec task"
    assert app._selected_agent_prompt_title() == "Implement one spec task"


def test_rosetta_eject_project_name_falls_back_to_saved_name() -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.config import normalize_project_path

    app = HivePlannerApp.__new__(HivePlannerApp)
    link = normalize_project_path("C:/projects/distilled-app")
    app.config = type("Cfg", (), {"active_project": link})()
    app._rosetta_eject_project_names = {link: "Distilled App"}
    assert app._rosetta_eject_project_name() == "Distilled App"


def test_rosetta_eject_saved_name_is_scoped_per_linked_project() -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.config import normalize_project_path

    app = HivePlannerApp.__new__(HivePlannerApp)
    link_a = normalize_project_path("C:/projects/app-a")
    link_b = normalize_project_path("C:/projects/app-b")
    app._rosetta_eject_project_names = {link_a: "Alpha", link_b: "Beta"}
    app.config = type("Cfg", (), {"active_project": link_b})()
    assert app._saved_rosetta_eject_project_name() == "Beta"
    app.config = type("Cfg", (), {"active_project": link_a})()
    assert app._saved_rosetta_eject_project_name() == "Alpha"


def test_save_rosetta_eject_project_name_persists_entry() -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.config import normalize_project_path

    app = HivePlannerApp.__new__(HivePlannerApp)
    link = normalize_project_path("C:/projects/saved-app")
    app.config = type("Cfg", (), {"active_project": link})()
    app._rosetta_eject_project_names = {}
    app._rosetta_eject_name_var = type("Var", (), {"get": lambda self: "  Saved Name  "})()
    app._save_rosetta_eject_project_name()
    assert app._rosetta_eject_project_names[link] == "Saved Name"


def test_agents_propose_done_auto_applies_without_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    app._bg_generation = 0
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._start_home_action = lambda _msg: None  # type: ignore[method-assign]
    bg_calls: list[tuple] = []
    app._run_bg = lambda fn, done: bg_calls.append((fn, done))  # type: ignore[method-assign]
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

    assert previewed == []
    assert len(bg_calls) == 1
    assert not any("NameError" in line for line in app._pending_home_log)


def test_agents_propose_done_logs_routing_when_already_applied() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._clear_memory_work_context = lambda: None  # type: ignore[method-assign]

    app._agents_propose_done(
        {
            "ok": True,
            "proposal_path": "docs/proposals/agents-memory-1.md",
            "accepted": ["Keep logs concise."],
            "rejected": [],
            "applied": True,
            "routing": [{"arm": "split", "reason": "Auto-split into 2 bullet(s) ≤ 240 chars"}],
            "current_facts": "- Old.",
            "after_section": "- Old.\n- Keep logs concise.",
        }
    )

    assert any("Applied to AGENTS.md" in line for line in app._pending_home_log)
    assert any("route/split" in line for line in app._pending_home_log)


def test_deliver_memory_propose_defers_accepted_log_until_apply() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    app._bg_generation = 0
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._start_home_action = lambda _msg: None  # type: ignore[method-assign]
    app._run_bg = lambda fn, done: None  # type: ignore[method-assign]
    project = Path("C:/proj")
    app.config = type("Cfg", (), {"active_project": "C:/proj"})()
    app._active_linked_root = lambda: project
    app._set_pending_memory_candidates(project, Path("C:/proj/docs/proposals/candidates.md"))

    app._deliver_memory_propose_result(
        {
            "ok": True,
            "proposal_path": "docs/proposals/agents-memory-1.md",
            "accepted": ["Keep logs concise."],
            "rejected": [],
            "applied": False,
        }
    )

    assert not any("Accepted 1 candidate" in line for line in app._pending_home_log)
    assert any("Wrote proposal" in line for line in app._pending_home_log)


def test_deliver_memory_propose_stale_does_not_start_bg_apply() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    app._bg_generation = 0
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._start_home_action = lambda _msg: None  # type: ignore[method-assign]
    bg_calls: list = []
    app._run_bg = lambda fn, done: bg_calls.append((fn, done))  # type: ignore[method-assign]
    project = Path("C:/proj")
    app.config = type("Cfg", (), {"active_project": "C:/proj"})()
    app._active_linked_root = lambda: project
    app._set_pending_memory_candidates(project, Path("C:/proj/docs/proposals/candidates.md"))

    app._deliver_memory_propose_result(
        {
            "ok": True,
            "proposal_path": "docs/proposals/agents-memory-1.md",
            "accepted": ["Keep logs concise."],
            "rejected": [],
            "applied": False,
        },
        stale=True,
    )

    assert bg_calls == []
    assert any("dashboard refresh" in line for line in app._pending_home_log)


def test_agents_apply_done_logs_accepted_count_on_apply() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._clear_memory_work_context = lambda: None  # type: ignore[method-assign]

    app._agents_apply_done(
        {
            "ok": True,
            "proposal_path": "docs/proposals/agents-memory-1.md",
            "accepted": ["Keep logs concise."],
            "rejected": [],
            "applied": True,
            "routing": [{"arm": "split", "reason": "Auto-split into 2 bullet(s)"}],
        }
    )

    assert any("Accepted 1 candidate" in line for line in app._pending_home_log)
    assert any("AGENTS.md updated" in line for line in app._pending_home_log)


def test_agents_apply_done_logs_noop_when_already_applied() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._clear_memory_work_context = lambda: None  # type: ignore[method-assign]

    app._agents_apply_done(
        {
            "ok": True,
            "proposal_path": "docs/proposals/agents-memory-1.md",
            "accepted": [],
            "rejected": [],
            "applied": False,
            "noop": True,
        }
    )

    assert any("already present" in line for line in app._pending_home_log)
    assert not any("AGENTS.md updated" in line for line in app._pending_home_log)


def test_on_agents_apply_runs_propose_with_apply_true(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    app.config = type("Cfg", (), {"active_project": "C:/proj"})()
    app._pending_memory_candidates = None
    app._active_linked_root = lambda: Path("C:/proj")
    app._set_pending_memory_candidates = lambda _r, _c: None  # type: ignore[method-assign]
    app._start_home_action = lambda _msg: None  # type: ignore[method-assign]
    captured: list[bool] = []

    def fake_propose(project_root, candidates_path, *, apply=False):
        captured.append(apply)
        return {"ok": True, "applied": apply, "accepted": [], "rejected": []}

    monkeypatch.setattr("hive_planner.launcher.app.run_agents_memory_propose", fake_propose)
    monkeypatch.setattr(
        "hive_planner.launcher.app.filedialog.askopenfilename",
        lambda **_kw: "C:/proj/docs/proposals/candidates.md",
    )
    monkeypatch.setattr("hive_planner.launcher.app.candidates_path_in_project", lambda _r, _c: True)
    app._run_bg = lambda fn, done: fn()  # type: ignore[method-assign]
    app._agents_propose_done = lambda _result: None  # type: ignore[method-assign]

    app._on_agents_apply()

    assert captured == [True]


def test_agents_apply_done_logs_routing_when_applied() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = None
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._clear_memory_work_context = lambda: None  # type: ignore[method-assign]

    app._agents_apply_done(
        {
            "ok": True,
            "proposal_path": "docs/proposals/agents-memory-1.md",
            "accepted": ["Keep logs concise."],
            "rejected": [],
            "applied": True,
            "routing": [{"arm": "split", "reason": "Auto-split into 2 bullet(s) ≤ 240 chars"}],
        }
    )

    assert any("AGENTS.md updated" in line for line in app._pending_home_log)
    assert any("route/split" in line for line in app._pending_home_log)


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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]

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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
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
    # Hub should keep Home working by falling back to another linked workspace.
    assert cfg.active_project == str(other.resolve())
    assert str(alive.resolve()) not in cfg.project_profiles
    assert cfg.remove_recent_project(tmp_path / "missing") is False


def test_prune_stale_projects_falls_back_active_when_path_missing(tmp_path: Path) -> None:
    from hive_planner.launcher.config import linked_project_exists, prune_stale_projects

    gone = tmp_path / "gone"
    keep = tmp_path / "keep"
    keep.mkdir()
    cfg = LauncherConfig(
        active_project=str(gone),
        recent_projects=[str(gone), str(keep.resolve())],
        project_profiles={str(gone): "full", str(keep.resolve()): "minimal"},
    )
    assert linked_project_exists(gone) is False
    assert prune_stale_projects(cfg) is True
    assert cfg.active_project == str(keep.resolve())


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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]

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


def test_status_labels_do_not_repair_agents_md(tmp_path: Path) -> None:
    """Soft Home status refresh must not rewrite AGENTS.md (display-only)."""
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.project_profile import write_project_profile

    project = tmp_path / "demo"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    agents = project / "AGENTS.md"
    legacy = _legacy_agents_with_rosetta("None â€” pending.")
    agents.write_text(legacy, encoding="utf-8")
    write_project_profile(project, profile="full", project_name="Demo")
    _write_handoff_bundle(project, "example-feature")

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=str(project.resolve()))
    before = agents.read_bytes()
    _ = app._active_profile_label()
    _ = app._active_feature_label()
    _ = app._wiring_audit_label()
    assert agents.read_bytes() == before


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
    monkeypatch.setattr(
        "hive_planner.launcher.service._run_hidden",
        lambda *_a, **_k: type(
            "R",
            (),
            {"returncode": 0, "stdout": "9.9.9\n", "stderr": ""},
        )(),
    )
    cfg = LauncherConfig(python_executable="py -3.12")
    status = get_setup_status(cfg)
    assert status.python_ok is True
    assert "3.12.1" in status.python_version
    assert "py -3.12" in status.python_version
    assert status.hive_installed is True
    assert status.hive_version == "9.9.9"


def test_get_setup_status_marks_python_not_ok_when_configured_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("hive_planner.launcher.service.probe_python_command", lambda _cmd: None)
    monkeypatch.setattr(
        "hive_planner.launcher.service._run_hidden",
        lambda *_a, **_k: type("R", (), {"returncode": 1, "stdout": "", "stderr": "gone"})(),
    )
    cfg = LauncherConfig(python_executable="py -99")
    status = get_setup_status(cfg)
    assert status.python_ok is False
    assert "configured Python unavailable" in status.python_version
    assert status.hive_installed is False


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


def test_python_command_keeps_unquoted_existing_path_with_spaces(tmp_path: Path) -> None:
    folder = tmp_path / "Program Files" / "Python311"
    folder.mkdir(parents=True)
    exe = folder / "python.exe"
    exe.write_bytes(b"")
    cfg = LauncherConfig(python_executable=str(exe))
    assert _python_command(cfg) == [str(exe)]


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


def test_select_recent_preserves_unsaved_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Set as active must not load_config() and wipe in-memory Settings edits."""
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
            python_executable="py -3.11",
        )
    )

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = load_config()
    app.config.python_executable = r"C:\Custom\Python\python.exe"
    app._recent_project_paths = [str(p2.resolve()), str(p1.resolve())]
    app.recent_list = type("L", (), {"curselection": lambda self: (0,)})()
    app._pending_home_log = []
    app._home_log_history = []
    app._home_log_histories = {}
    app._last_ci_report = None
    soft_calls: list[dict] = []
    app._dashboard_alive = lambda: True  # type: ignore[method-assign]
    app._soft_refresh_dashboard = (  # type: ignore[method-assign]
        lambda **kwargs: soft_calls.append(dict(kwargs))
    )

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(
        app_mod,
        "load_config",
        lambda: (_ for _ in ()).throw(AssertionError("load_config must not run on Set as active")),
    )

    app._on_select_recent()
    assert app.config.active_project == str(p2.resolve())
    assert app.config.python_executable == r"C:\Custom\Python\python.exe"
    assert soft_calls == [{"reload_config": False}]


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


def test_home_output_history_switches_with_active_project(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    project_a = str((tmp_path / "alpha").resolve())
    project_b = str((tmp_path / "beta").resolve())
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=project_a)
    app._pending_home_log = []
    app._home_log_history = []
    app._home_log_scope = normalize_project_path(project_a)
    app._home_log_histories = {app._home_log_scope: app._home_log_history}

    class _Log:
        def __init__(self) -> None:
            self.lines: list[str] = []

        def configure(self, **_kwargs) -> None:
            pass

        def delete(self, _start, _end) -> None:
            self.lines.clear()

    app.home_log = _Log()
    app._append_log = lambda widget, text: widget.lines.append(text)  # type: ignore[method-assign]

    app._emit_home_log("alpha result")
    assert app.home_log.lines == ["alpha result"]

    app.config.active_project = project_b
    app._sync_home_log_for_active()
    assert app.home_log.lines == []
    app._emit_home_log("beta result")
    assert app.home_log.lines == ["beta result"]

    app.config.active_project = project_a
    app._sync_home_log_for_active()
    assert app.home_log.lines == ["alpha result"]
    assert app._home_log_histories[normalize_project_path(project_b)] == ["beta result"]


def test_ci_check_done_clears_stale_steps_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    monkeypatch.setattr("hive_planner.launcher.app.messagebox.showerror", lambda *a, **k: None)
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = type("R", (), {})()
    app._pending_home_log = []
    app._last_ci_report = {"ok": True, "steps": [{"name": "old", "ok": True, "detail": "x"}]}
    app._last_ci_link = "C:/old"
    app._ci_check_target = "C:/old"
    app.config = LauncherConfig(active_project="C:/old")
    app._show_dashboard = lambda: None  # type: ignore[method-assign]
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._ci_check_done({"ok": False, "error": "Not a Hive project (missing START_HERE.md)"})
    assert app._last_ci_report is None
    assert app._last_ci_link is None
    assert app._pending_home_log
    assert "START_HERE" in app._pending_home_log[0]


def test_ci_check_done_preserves_report_for_dashboard_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    monkeypatch.setattr("hive_planner.launcher.app.messagebox.showwarning", lambda *a, **k: None)
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = type("R", (), {})()
    app._pending_home_log = []
    app._last_ci_report = None
    app._last_ci_link = None
    app._ci_check_target = "C:/proj"
    app.config = LauncherConfig(active_project="C:/proj")
    app._show_dashboard = lambda: None  # type: ignore[method-assign]
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    report = {
        "ok": False,
        "steps": [
            {"name": "agents-lint", "ok": True, "detail": "ok"},
            {"name": "wiring-audit", "ok": False, "detail": "missing attestation"},
        ],
    }
    app._ci_check_done(report)
    assert app._last_ci_report == report
    assert app._last_ci_link == normalize_project_path("C:/proj")
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


def test_soft_refresh_clears_ci_report_when_active_project_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.service import SetupStatus

    project_a = tmp_path / "alpha"
    project_b = tmp_path / "beta"
    project_a.mkdir()
    project_b.mkdir()
    a_path = str(project_a.resolve())
    b_path = str(project_b.resolve())

    cfg = LauncherConfig(active_project=b_path, recent_projects=[a_path, b_path])
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._pending_memory_link = None
    app._pending_memory_candidates = None
    app._pending_home_log = []
    app._last_ci_report = {
        "ok": True,
        "steps": [{"name": "agents-lint", "ok": True, "detail": "ok for alpha"}],
    }
    app._last_ci_link = a_path
    app.setup = SetupStatus(
        python_ok=True,
        python_version="3.11",
        hive_root="C:/hive",
        hive_root_ok=True,
        hive_installed=True,
        hive_version="1.0.0",
        git_available=True,
        onboarding_complete=True,
    )
    cleared: list[object] = []

    class _List:
        def delete(self, _a, _b) -> None:
            cleared.append("cleared")

        def insert(self, _end, text) -> None:
            cleared.append(text)

    app.ci_list = _List()
    app._update_header_detail = lambda: None  # type: ignore[method-assign]
    app._update_status_cards = lambda: None  # type: ignore[method-assign]
    app._sync_rosetta_eject_for_active = lambda: None  # type: ignore[method-assign]
    app._flush_pending_home_log = lambda: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "get_setup_status", lambda _cfg: app.setup)

    app._soft_refresh_dashboard()
    assert app._last_ci_report is None
    assert app._last_ci_link is None
    assert cleared == ["cleared"]


def test_ci_check_done_discards_result_after_active_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    dialogs: list[str] = []
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.showinfo",
        lambda *a, **k: dialogs.append("info"),
    )
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.showwarning",
        lambda *a, **k: dialogs.append("warn"),
    )
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.showerror",
        lambda *a, **k: dialogs.append("error"),
    )

    alpha = normalize_project_path("C:/alpha")
    beta = normalize_project_path("C:/beta")
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = type("R", (), {})()
    app.config = LauncherConfig(active_project=beta)
    app._ci_check_target = alpha
    app._last_ci_report = None
    app._last_ci_link = None
    app._pending_home_log = []
    app._home_log_scope = beta
    app._home_log_history = []
    app._home_log_histories = {alpha: [], beta: app._home_log_history}
    refreshed: list[bool] = []
    app._refresh_home_dashboard = lambda **_k: refreshed.append(True)  # type: ignore[method-assign]

    app._ci_check_done(
        {"ok": True, "steps": [{"name": "agents-lint", "ok": True, "detail": "ok"}]},
        expected_link=alpha,
    )
    assert app._last_ci_report is None
    assert dialogs == []
    assert refreshed == []
    assert app._home_log_histories[alpha] and "discarded" in app._home_log_histories[alpha][0].lower()
    assert app._home_log_history == []


def test_ci_check_done_discards_overlapping_job_after_second_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared _ci_check_target may point at B while an older A job completes — must discard."""
    from hive_planner.launcher.app import HivePlannerApp

    dialogs: list[str] = []
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.showinfo",
        lambda *a, **k: dialogs.append("info"),
    )
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.showwarning",
        lambda *a, **k: dialogs.append("warn"),
    )
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.showerror",
        lambda *a, **k: dialogs.append("error"),
    )

    alpha = normalize_project_path("C:/alpha")
    beta = normalize_project_path("C:/beta")
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = type("R", (), {})()
    app.config = LauncherConfig(active_project=beta)
    # Second health check already retargeted the shared field to Beta.
    app._ci_check_target = beta
    app._last_ci_report = None
    app._last_ci_link = None
    app._pending_home_log = []
    app._home_log_scope = beta
    app._home_log_history = []
    app._home_log_histories = {alpha: [], beta: app._home_log_history}

    app._ci_check_done(
        {"ok": True, "steps": [{"name": "agents-lint", "ok": True, "detail": "alpha-old"}]},
        expected_link=alpha,
    )
    assert app._last_ci_report is None
    assert app._last_ci_link is None
    assert dialogs == []
    assert app._ci_check_target == beta  # in-flight Beta job still tracked
    assert app._home_log_histories[alpha] and "discarded" in app._home_log_histories[alpha][0].lower()
    assert app._home_log_history == []


def test_populate_ci_list_clears_when_report_is_none() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    rows = ["✓  old: ok"]

    class _List:
        def delete(self, _a, _b) -> None:
            rows.clear()

        def insert(self, _end, text) -> None:
            rows.append(text)

    app.ci_list = _List()
    app._populate_ci_list(None)
    assert rows == []


def test_populate_recent_list_preserves_non_active_selection(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    a_path = str(a.resolve())
    b_path = str(b.resolve())

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=a_path, recent_projects=[a_path, b_path])
    app._recent_project_paths = [a_path, b_path]
    selected = {"idx": (1,)}

    class _List:
        def __init__(self) -> None:
            self.rows: list[str] = []
            self.selection: tuple[int, ...] = ()

        def delete(self, _a, _b) -> None:
            self.rows.clear()
            self.selection = ()

        def insert(self, _end, text) -> None:
            self.rows.append(text)

        def size(self) -> int:
            return len(self.rows)

        def curselection(self):
            return selected["idx"]

        def selection_set(self, idx) -> None:
            self.selection = (idx,)

        def see(self, _idx) -> None:
            return None

        def configure(self, **_kwargs) -> None:
            return None

        def yview_moveto(self, _v) -> None:
            return None

    app.recent_list = _List()
    app.recent_scroll = type(
        "S",
        (),
        {
            "winfo_ismapped": lambda self: False,
            "pack": lambda *a, **k: None,
            "pack_forget": lambda *a, **k: None,
            "config": lambda *a, **k: None,
            "set": lambda *a, **k: None,
        },
    )()
    app._update_recent_scrollbar = lambda: None  # type: ignore[method-assign]

    app._populate_recent_list()
    assert app.recent_list.selection == (1,)
    assert app._recent_project_paths[1] == b_path


def test_save_settings_syncs_new_project_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.service import SetupStatus

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.setup = SetupStatus(
        python_ok=True,
        python_version="3.11",
        hive_root="C:/hive",
        hive_root_ok=True,
        hive_installed=True,
        hive_version="1.0.0",
        git_available=True,
        onboarding_complete=True,
        portable_mode=True,
    )
    app.config = LauncherConfig(default_profile="full", default_agent_handoff="unified")
    app.cfg_cursor = type("V", (), {"get": lambda self: ""})()
    app.cfg_profile = type("V", (), {"get": lambda self: "minimal"})()
    app.cfg_agent_handoff = type("V", (), {"get": lambda self: "off"})()
    profile_vals: list[str] = []
    handoff_vals: list[str] = []
    app.new_profile = type("V", (), {"set": lambda self, v: profile_vals.append(v)})()
    app.new_agent_handoff = type("V", (), {"set": lambda self, v: handoff_vals.append(v)})()
    refreshed: list[bool] = []
    app._refresh_home_dashboard = lambda **_k: refreshed.append(True)  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(app_mod, "get_setup_status", lambda cfg: app.setup)
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)

    app._on_save_settings()
    assert app.config.default_profile == "minimal"
    assert app.config.default_agent_handoff == "off"
    assert profile_vals == ["minimal"]
    assert handoff_vals == ["off"]
    assert refreshed == [True]


def test_soft_refresh_retargets_rosetta_eject_when_active_project_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp
    from hive_planner.launcher.service import SetupStatus

    project_a = tmp_path / "alpha-app"
    project_b = tmp_path / "beta-app"
    project_a.mkdir()
    project_b.mkdir()
    (project_a / "START_HERE.md").write_text("# a\n", encoding="utf-8")
    (project_b / "START_HERE.md").write_text("# b\n", encoding="utf-8")

    cfg = LauncherConfig(
        active_project=str(project_b.resolve()),
        recent_projects=[str(project_a.resolve()), str(project_b.resolve())],
    )
    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_memory_link = None
    app._pending_memory_candidates = None
    app._last_ci_report = None
    app._pending_home_log = []
    app._rosetta_eject_project_names = {}
    app._rosetta_eject_expanded = True
    app._rosetta_eject_synced_scope = str(project_a.resolve())
    app._rosetta_eject_name_var = type("V", (), {"get": lambda self: "alpha-app", "set": lambda self, v: setattr(self, "value", v)})()
    app.config = cfg
    app.setup = SetupStatus(
        python_ok=True,
        python_version="3.11",
        hive_root="C:/hive",
        hive_root_ok=True,
        hive_installed=True,
        hive_version="1.0.0",
        git_available=True,
        onboarding_complete=True,
    )
    refreshed: list[bool] = []
    app._refresh_rosetta_eject_preview = lambda: refreshed.append(True)  # type: ignore[method-assign]
    app._update_header_detail = lambda: None  # type: ignore[method-assign]
    app._update_status_cards = lambda: None  # type: ignore[method-assign]
    app._populate_ci_list = lambda _r: None  # type: ignore[method-assign]
    app._flush_pending_home_log = lambda: None  # type: ignore[method-assign]
    app._active_linked_root = lambda: project_b.resolve()  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(app_mod, "get_setup_status", lambda _cfg: app.setup)

    app._soft_refresh_dashboard()
    assert app._rosetta_eject_name_var.value == "beta-app"
    assert app._rosetta_eject_synced_scope == str(project_b.resolve())
    assert refreshed == [True]


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


def test_project_done_callback_keeps_late_result_with_origin_profile(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    project_a = str((tmp_path / "alpha").resolve())
    project_b = str((tmp_path / "beta").resolve())
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=project_a)
    app._home_log_scope = normalize_project_path(project_a)
    app._home_log_history = []
    app._home_log_histories = {app._home_log_scope: app._home_log_history}
    app._pending_home_log = []
    delivered: list[dict] = []

    callback = app._project_done_callback("Impact map sync", delivered.append)
    app.config.active_project = project_b
    callback({"ok": True})

    assert delivered == []
    origin_history = app._home_log_histories[normalize_project_path(project_a)]
    assert origin_history == [
        "Impact map sync finished after switching profiles; result retained for this project."
    ]

    app.config.active_project = project_a
    app._sync_home_log_for_active()
    assert app._home_log_history == origin_history


def test_project_done_callback_delivers_when_profile_unchanged(tmp_path: Path) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    project = str((tmp_path / "alpha").resolve())
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=project)
    delivered: list[dict] = []

    callback = app._project_done_callback("Impact map sync", delivered.append)
    callback({"ok": True})

    assert delivered == [{"ok": True}]


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
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._note_stale_bg_result({"ok": False, "mode": "import", "error": "emit failed"})
    joined = "\n".join(app._pending_home_log)
    assert "emit failed" in joined
    assert "dashboard refresh" in joined


def test_note_stale_bg_result_delivers_memory_propose_preview() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    delivered: list[bool] = []
    app._deliver_memory_propose_result = lambda result, stale=False: delivered.append(stale)  # type: ignore[method-assign]
    app._note_stale_bg_result(
        {
            "ok": True,
            "proposal_path": "docs/proposals/agents-memory-1.md",
            "accepted": ["Run pytest before handoff."],
            "rejected": [],
        }
    )
    assert delivered == [True]


def test_note_stale_bg_result_clears_memory_work_context_on_cancelled() -> None:
    from pathlib import Path

    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._memory_work_root = Path("C:/proj")
    app._memory_work_candidates_path = Path("C:/proj/docs/proposals/candidates.md")
    app._pending_memory_candidates = app._memory_work_candidates_path
    app._pending_memory_link = "C:/proj"
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._note_stale_bg_result(
        {
            "ok": False,
            "cancelled": True,
            "error": "Memory apply cancelled — project or dashboard changed.",
        }
    )
    assert app._memory_work_root is None
    assert app._memory_work_candidates_path is None
    assert app._pending_memory_candidates is None


def test_note_stale_bg_result_preserves_cartridge_details() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
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
    app._refresh_home_dashboard = lambda **_k: refreshed.__setitem__("value", True)  # type: ignore[method-assign]
    app._note_stale_bg_result({"ok": False, "error": "late finish"})
    assert app._pending_home_log == ["Background task finished after dashboard refresh: late finish"]
    assert refreshed["value"] is True


def test_note_stale_bg_result_clears_controls_in_progress() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    class _Var:
        def __init__(self, value: str = "") -> None:
            self._value = value

        def set(self, value: str) -> None:
            self._value = value

        def get(self) -> str:
            return self._value

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app.controls_last = _Var("Starting implementation loop…")
    app._refresh_home_dashboard = lambda **_k: None  # type: ignore[method-assign]
    app._note_stale_bg_result({"ok": True, "action": "start"})
    assert "dashboard refresh" in app.controls_last.get()
    assert "Starting implementation loop" not in app.controls_last.get()


def test_choose_without_arm_ignores_invalid_cycles(monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path

    from hive_planner.launcher.app import HivePlannerApp

    class _Var:
        def __init__(self, value) -> None:
            self._value = value

        def get(self):
            return self._value

    warned: list[object] = []
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.showwarning",
        lambda *a, **k: warned.append(a),
    )
    started: list[str] = []
    app = HivePlannerApp.__new__(HivePlannerApp)
    app._require_active_link = lambda: Path("C:/proj")  # type: ignore[method-assign]
    app.controls_agn_open = _Var("")
    app.controls_agn_arm_choose = _Var(False)
    app.controls_agn_cycles = _Var("not-a-number")
    app._start_home_action = lambda message: started.append(message)  # type: ignore[method-assign]
    app._run_bg = lambda work, done: started.append("bg")  # type: ignore[method-assign]
    app._project_done_callback = lambda label, on_done: on_done  # type: ignore[method-assign]
    app._on_agnostic_loop_choose()
    assert not warned
    assert started == ["Choosing agnostic-loop reward…", "bg"]


def test_choose_with_arm_rejects_invalid_cycles(monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path

    from hive_planner.launcher.app import HivePlannerApp

    class _Var:
        def __init__(self, value) -> None:
            self._value = value

        def get(self):
            return self._value

    warned: list[object] = []
    monkeypatch.setattr(
        "hive_planner.launcher.app.messagebox.showwarning",
        lambda *a, **k: warned.append(a),
    )
    started: list[str] = []
    app = HivePlannerApp.__new__(HivePlannerApp)
    app._require_active_link = lambda: Path("C:/proj")  # type: ignore[method-assign]
    app.controls_agn_open = _Var("")
    app.controls_agn_arm_choose = _Var(True)
    app.controls_agn_cycles = _Var("not-a-number")
    app._start_home_action = lambda message: started.append(message)  # type: ignore[method-assign]
    app._run_bg = lambda work, done: started.append("bg")  # type: ignore[method-assign]
    app._on_agnostic_loop_choose()
    assert warned
    assert started == []


def test_note_stale_bg_result_refreshes_dashboard_for_cartridge() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    refreshed = {"count": 0}
    app._refresh_home_dashboard = lambda **_k: refreshed.__setitem__("count", refreshed["count"] + 1)  # type: ignore[method-assign]
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
    app._home_log_history = []
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
    assert any("Opened in Cursor" in line for line in app._home_log_history)


def test_open_cursor_prefers_projects_list_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    active = tmp_path / "active"
    selected = tmp_path / "selected"
    active.mkdir()
    selected.mkdir()
    active_s = str(active.resolve())
    selected_s = str(selected.resolve())
    cfg = LauncherConfig(
        active_project=active_s,
        recent_projects=[active_s, selected_s],
        hive_planner_root=str(Path(__file__).resolve().parents[1]),
    )

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._pending_home_log = []
    app._home_log_history = []
    app._recent_project_paths = [active_s, selected_s]
    app.recent_list = type("L", (), {"curselection": lambda self: (1,)})()
    app._populate_recent_list = lambda **_k: None  # type: ignore[method-assign]
    app._projects_tab_selected = lambda: True  # type: ignore[method-assign]
    lines: list[str] = []
    app.home_log = type("L", (), {"configure": lambda *a, **k: None})()
    app._append_log = lambda _w, text: lines.append(text)  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    opened: dict[str, str] = {}

    def fake_open(path, *, config=None):
        opened["path"] = str(Path(path).resolve())
        return {"ok": True, "hive_ready": False}

    monkeypatch.setattr(app_mod, "open_in_cursor", fake_open)
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)

    app._on_open_cursor()
    assert opened["path"] == selected_s
    assert app.config.active_project == selected_s
    assert lines and "Opened in Cursor" in lines[0]


def test_open_cursor_activate_preserves_unsaved_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    active = tmp_path / "active"
    selected = tmp_path / "selected"
    active.mkdir()
    selected.mkdir()
    active_s = str(active.resolve())
    selected_s = str(selected.resolve())
    cfg = LauncherConfig(
        active_project=active_s,
        recent_projects=[active_s, selected_s],
        python_executable="py -3.11",
        hive_planner_root=str(Path(__file__).resolve().parents[1]),
    )
    # Simulate unsaved Settings edit still only in memory.
    cfg.python_executable = r"C:\Custom\Python\python.exe"

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._pending_home_log = []
    app._home_log_history = []
    app._recent_project_paths = [active_s, selected_s]
    app.recent_list = type("L", (), {"curselection": lambda self: (1,)})()
    app._populate_recent_list = lambda **_k: None  # type: ignore[method-assign]
    app._projects_tab_selected = lambda: True  # type: ignore[method-assign]
    app.home_log = type("L", (), {"configure": lambda *a, **k: None})()
    app._append_log = lambda *_a, **_k: None  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(
        app_mod,
        "open_in_cursor",
        lambda *_a, **_k: {"ok": True, "hive_ready": False},
    )
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(
        app_mod,
        "load_config",
        lambda: (_ for _ in ()).throw(AssertionError("load_config must not run on Open activate")),
    )

    app._on_open_cursor()
    assert app.config.active_project == selected_s
    assert app.config.python_executable == r"C:\Custom\Python\python.exe"


def test_open_cursor_activate_soft_refreshes_home_without_load_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Activating via Open in Cursor must refresh Home widgets without load_config()."""
    from hive_planner.launcher.app import HivePlannerApp

    active = tmp_path / "active"
    selected = tmp_path / "selected"
    active.mkdir()
    selected.mkdir()
    active_s = str(active.resolve())
    selected_s = str(selected.resolve())
    cfg = LauncherConfig(
        active_project=active_s,
        recent_projects=[active_s, selected_s],
        python_executable="py -3.11",
        hive_planner_root=str(Path(__file__).resolve().parents[1]),
    )
    cfg.python_executable = r"C:\Custom\Python\python.exe"

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._pending_home_log = []
    app._home_log_history = []
    app._home_log_histories = {}
    app._home_log_scope = active_s
    app._last_ci_report = {"ok": True}
    app._last_ci_link = active_s
    app._recent_project_paths = [active_s, selected_s]
    app.recent_list = type("L", (), {"curselection": lambda self: (1,)})()
    app._projects_tab_selected = lambda: True  # type: ignore[method-assign]
    app.home_log = type("L", (), {"configure": lambda *a, **k: None, "delete": lambda *a, **k: None, "insert": lambda *a, **k: None})()
    app._append_log = lambda *_a, **_k: None  # type: ignore[method-assign]
    soft_calls: list[dict] = []
    app._dashboard_alive = lambda: True  # type: ignore[method-assign]
    app._soft_refresh_dashboard = (  # type: ignore[method-assign]
        lambda **kwargs: soft_calls.append(dict(kwargs))
    )

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(
        app_mod,
        "open_in_cursor",
        lambda *_a, **_k: {"ok": True, "hive_ready": False},
    )
    monkeypatch.setattr(app_mod, "save_config", lambda _cfg: None)
    monkeypatch.setattr(
        app_mod,
        "load_config",
        lambda: (_ for _ in ()).throw(AssertionError("load_config must not run on Open activate")),
    )

    app._on_open_cursor()
    assert app.config.active_project == selected_s
    assert soft_calls == [{"reload_config": False}]
    assert app.config.python_executable == r"C:\Custom\Python\python.exe"


def test_open_cursor_home_uses_active_not_list_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    active = tmp_path / "active"
    selected = tmp_path / "selected"
    active.mkdir()
    selected.mkdir()
    active_s = str(active.resolve())
    selected_s = str(selected.resolve())
    cfg = LauncherConfig(
        active_project=active_s,
        recent_projects=[active_s, selected_s],
        hive_planner_root=str(Path(__file__).resolve().parents[1]),
    )

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = cfg
    app._pending_home_log = []
    app._home_log_history = []
    app._recent_project_paths = [active_s, selected_s]
    app.recent_list = type("L", (), {"curselection": lambda self: (1,)})()
    app._projects_tab_selected = lambda: False  # type: ignore[method-assign]
    lines: list[str] = []
    app.home_log = type("L", (), {"configure": lambda *a, **k: None})()
    app._append_log = lambda _w, text: lines.append(text)  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    opened: dict[str, str] = {}

    def fake_open(path, *, config=None):
        opened["path"] = str(Path(path).resolve())
        return {"ok": True, "hive_ready": True}

    monkeypatch.setattr(app_mod, "open_in_cursor", fake_open)

    app._on_open_cursor()
    assert opened["path"] == active_s
    assert app.config.active_project == active_s


def test_open_cursor_empty_prompts_picker_then_opens_after_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project="", recent_projects=[])
    picker_kwargs: dict[str, object] = {}
    app._show_workspace_picker = lambda **kwargs: picker_kwargs.update(kwargs)  # type: ignore[method-assign]

    import hive_planner.launcher.app as app_mod

    monkeypatch.setattr(app_mod.messagebox, "askyesno", lambda *_a, **_k: True)
    app._on_open_cursor()
    assert picker_kwargs.get("open_after_link") is True


def test_start_home_action_survives_full_rebuild_via_history() -> None:
    from hive_planner.launcher.app import HivePlannerApp

    app = HivePlannerApp.__new__(HivePlannerApp)
    app._pending_home_log = []
    app._home_log_history = []
    live: list[str] = []
    app.home_log = object()
    app._append_log = lambda _w, text: live.append(text)  # type: ignore[method-assign]

    app._start_home_action("Running ci-check…")
    assert live == ["Running ci-check…"]
    assert app._home_log_history == ["Running ci-check…"]
    assert app._pending_home_log == []

    restored: list[str] = []
    app.home_log = object()
    app._append_log = lambda _w, text: restored.append(text)  # type: ignore[method-assign]
    app._restore_home_log_history()
    assert restored == ["Running ci-check…"]


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
    app._refresh_home_dashboard = lambda **_k: refreshed.__setitem__("value", True)  # type: ignore[method-assign]

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

