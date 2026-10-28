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
