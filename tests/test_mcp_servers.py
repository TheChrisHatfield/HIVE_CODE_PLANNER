from __future__ import annotations

import json
from pathlib import Path

from hive_planner.launcher.config import LauncherConfig
from hive_planner.launcher.mcp_servers import (
    HIVE_PLANNER_MCP_NAME,
    hive_planner_mcp_enabled,
    load_mcp_document,
    set_hive_planner_mcp,
)
from hive_planner.launcher.service import peek_hive_planner_mcp, run_set_hive_planner_mcp


def test_load_mcp_document_utf16_is_a_user_error(tmp_path: Path) -> None:
    import pytest

    from hive_planner.launcher.mcp_servers import McpConfigError

    cursor = tmp_path / ".cursor"
    cursor.mkdir()
    (cursor / "mcp.json").write_text(
        json.dumps({"mcpServers": {}}), encoding="utf-16"
    )
    with pytest.raises(McpConfigError):
        load_mcp_document(tmp_path)


def test_load_mcp_document_accepts_utf8_bom(tmp_path: Path) -> None:
    cursor = tmp_path / ".cursor"
    cursor.mkdir()
    payload = json.dumps({"mcpServers": {"other": {"command": "npx"}}})
    (cursor / "mcp.json").write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))
    doc = load_mcp_document(tmp_path)
    assert doc["mcpServers"]["other"]["command"] == "npx"
    raw = (cursor / "mcp.json").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert json.loads(raw.decode("utf-8"))["mcpServers"]["other"]["command"] == "npx"


def test_load_mcp_document_readonly_bom_is_a_user_error(tmp_path: Path) -> None:
    import stat

    import pytest

    from hive_planner.launcher.mcp_servers import McpConfigError

    cursor = tmp_path / ".cursor"
    cursor.mkdir()
    path = cursor / "mcp.json"
    raw = b"\xef\xbb\xbf" + json.dumps({"mcpServers": {}}).encode("utf-8")
    path.write_bytes(raw)
    path.chmod(stat.S_IREAD)
    try:
        with pytest.raises(McpConfigError, match="BOM"):
            load_mcp_document(tmp_path)
        assert path.read_bytes() == raw
    finally:
        path.chmod(stat.S_IWRITE | stat.S_IREAD)


def test_disable_clears_leftover_enabled_true() -> None:
    doc = {
        "mcpServers": {
            HIVE_PLANNER_MCP_NAME: {
                "command": "py",
                "args": ["-m", "hive_planner", "mcp-serve"],
                "enabled": True,
            }
        }
    }
    set_hive_planner_mcp(
        doc,
        enabled=False,
        command="py",
        args=["-m", "hive_planner", "mcp-serve"],
    )
    entry = doc["mcpServers"][HIVE_PLANNER_MCP_NAME]
    assert entry.get("disabled") is True
    assert entry.get("enabled") is False
    assert hive_planner_mcp_enabled(doc) is False


def test_peek_launch_snippet_matches_mcp_json_after_python_settings_change(tmp_path) -> None:
    first = LauncherConfig(python_executable="py -3.11")
    enabled = run_set_hive_planner_mcp(tmp_path, first, enabled=True)
    assert enabled["ok"] is True
    written = load_mcp_document(tmp_path)["mcpServers"][HIVE_PLANNER_MCP_NAME]
    assert written["args"][-1] == "mcp-serve"

    later = LauncherConfig(python_executable="py -3.12")
    peeked = peek_hive_planner_mcp(tmp_path, later)
    assert peeked["ok"] is True
    assert peeked["enabled"] is True
    assert peeked["launch_snippet"].startswith(str(written["command"]))
    assert "mcp-serve" in peeked["launch_snippet"]
    assert "-3.11" in peeked["launch_snippet"]
    assert "-3.12" not in peeked["launch_snippet"]


def test_peek_launch_snippet_uses_a_url_entry(tmp_path: Path) -> None:
    cursor = tmp_path / ".cursor"
    cursor.mkdir()
    (cursor / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    HIVE_PLANNER_MCP_NAME: {"url": "http://127.0.0.1:9/mcp"}
                }
            }
        ),
        encoding="utf-8",
    )
    peeked = peek_hive_planner_mcp(tmp_path, LauncherConfig(python_executable="py -3.11"))
    assert peeked["ok"] is True
    assert peeked["enabled"] is True
    assert peeked["launch_snippet"] == "http://127.0.0.1:9/mcp"
    assert "mcp-serve" not in peeked["launch_snippet"]


def test_format_mcp_invocation_quotes_a_path_with_spaces() -> None:
    from hive_planner.launcher.mcp_servers import format_mcp_invocation

    text = format_mcp_invocation(
        r"C:\Program Files\Python311\python.exe",
        ["-m", "hive_planner", "mcp-serve"],
    )
    assert text == '"C:\\Program Files\\Python311\\python.exe" -m hive_planner mcp-serve'


def test_format_mcp_invocation_quotes_a_shell_operator() -> None:
    from hive_planner.launcher.mcp_servers import format_mcp_invocation

    text = format_mcp_invocation(r"C:\tools\python&py.exe", ["-m", "hive_planner"])
    assert text == '"C:\\tools\\python&py.exe" -m hive_planner'


def test_format_mcp_invocation_quotes_parentheses_without_spaces() -> None:
    from hive_planner.launcher.mcp_servers import format_mcp_invocation

    text = format_mcp_invocation(r"C:\Python(x86)\python.exe", ["-m", "hive_planner"])
    assert text == '"C:\\Python(x86)\\python.exe" -m hive_planner'


def test_format_mcp_invocation_keeps_percent_signs_literal() -> None:
    import subprocess

    from hive_planner.launcher.mcp_servers import format_mcp_invocation

    text = format_mcp_invocation(r"C:\Users\%USERNAME%\python.exe", ["-m", "hive_planner"])
    assert text == r"C:\Users\^%USERNAME^%\python.exe -m hive_planner"
    proc = subprocess.run(
        ["cmd", "/d", "/s", "/c", "echo " + text],
        capture_output=True,
        text=True,
        check=False,
    )
    echoed = proc.stdout.strip()
    assert echoed == r"C:\Users\%USERNAME%\python.exe -m hive_planner"


def test_format_mcp_invocation_keeps_a_spaced_percent_path_literal(tmp_path: Path) -> None:
    import subprocess

    from hive_planner.launcher.mcp_servers import format_mcp_token

    path = r"C:\Program Files\%USERNAME%\python.exe"
    script = tmp_path / "show.py"
    script.write_text("import sys\nprint(sys.argv[1])\n", encoding="utf-8")
    # A string command line is required. A list would be re-quoted and hide the bug.
    proc = subprocess.run(
        "cmd /d /c py -3.11 " + format_mcp_token(str(script)) + " " + format_mcp_token(path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.stdout.strip() == path


def test_settings_enable_mcp_writes_the_active_project(tmp_path: Path, monkeypatch) -> None:
    from hive_planner.launcher.app import HivePlannerApp

    called: list[tuple[Path, bool]] = []
    monkeypatch.setattr("hive_planner.launcher.app.messagebox.showinfo", lambda *_a, **_k: None)
    monkeypatch.setattr("hive_planner.launcher.app.messagebox.showerror", lambda *_a, **_k: None)
    monkeypatch.setattr("hive_planner.launcher.app.messagebox.showwarning", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "hive_planner.launcher.app.run_set_hive_planner_mcp",
        lambda path, _config, enabled: called.append((Path(path), bool(enabled)))
        or {"ok": True, "enabled": True},
    )
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.config = LauncherConfig(active_project=str(tmp_path), python_executable="py -3.11")
    app._on_enable_hive_mcp()
    assert called == [(Path(tmp_path), True)]


def test_run_project_ci_check_uses_code_workspace_folder(tmp_path: Path, monkeypatch) -> None:
    from hive_planner.launcher.service import run_project_ci_check

    folder = tmp_path / "repo"
    folder.mkdir()
    (folder / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "repo"}]}), encoding="utf-8")
    seen: list[Path] = []

    def fake_ci_check(paths, **_kwargs):
        seen.append(Path(paths.root))
        from hive_planner.ci_handoff import CiCheckReport, CiStepResult

        return CiCheckReport(steps=[CiStepResult("agents-lint", True, "ok")])

    monkeypatch.setattr("hive_planner.launcher.service.run_ci_check", fake_ci_check)
    result = run_project_ci_check(workspace)
    assert seen == [folder.resolve()]
    assert result.get("error") != "Directory not found"
