from __future__ import annotations

from pathlib import Path

from hive_planner.launcher.config import LauncherConfig
from hive_planner.launcher.mcp_servers import HIVE_PLANNER_MCP_NAME, load_mcp_document
from hive_planner.launcher.service import peek_hive_planner_mcp, run_set_hive_planner_mcp


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
