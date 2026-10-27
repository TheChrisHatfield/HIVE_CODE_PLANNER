from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest

from hive_planner.cli import main
from hive_planner.launcher.config import LauncherConfig
from hive_planner.launcher.mcp_servers import (
    HIVE_PLANNER_MCP_NAME,
    hive_planner_mcp_enabled,
    hive_planner_stdio_launch,
    load_mcp_document,
)
from hive_planner.launcher.service import peek_hive_planner_mcp, run_set_hive_planner_mcp
from hive_planner.mcp_server import (
    SERVER_NAME,
    call_tool,
    handle_rpc,
    list_tool_names,
    read_message,
    write_message,
)


def test_hive_planner_stdio_launch_ends_with_mcp_serve() -> None:
    command, args = hive_planner_stdio_launch(LauncherConfig(python_executable="py -3.11"))
    assert command
    assert args[-1] == "mcp-serve"
    assert "-m" in args or "--hive-cli" in [command, *args]


def test_initialize_and_tools_list() -> None:
    init = handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init is not None
    assert init["result"]["serverInfo"]["name"] == SERVER_NAME
    listed = handle_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = [item["name"] for item in listed["result"]["tools"]]
    assert "hive_ping" in names
    assert "hive_implementation_loop_status" in names
    assert names == list_tool_names()


def test_ping_tool_reports_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    reply = handle_rpc(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "hive_ping", "arguments": {}},
        }
    )
    assert reply is not None
    assert reply["result"]["isError"] is False
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["ok"] is True
    assert payload["server"] == SERVER_NAME
    assert Path(payload["root"]) == tmp_path.resolve()


def test_unknown_tool_is_error() -> None:
    reply = handle_rpc(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "not_a_tool", "arguments": {}},
        }
    )
    assert reply["result"]["isError"] is True
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["ok"] is False


def test_blocked_hive_tool_is_not_mcp_is_error(tmp_path: Path) -> None:
    reply = handle_rpc(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "hive_implementation_loop_status",
                "arguments": {"root": str(tmp_path)},
            },
        }
    )
    assert reply["result"]["isError"] is False
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["ok"] is False


def test_unknown_method() -> None:
    reply = handle_rpc({"jsonrpc": "2.0", "id": 5, "method": "nope", "params": {}})
    assert reply["error"]["code"] == -32601


def test_notification_returns_none() -> None:
    assert handle_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_missing_content_length_is_not_eof() -> None:
    with pytest.raises(ValueError, match="Content-Length"):
        read_message(BytesIO(b"X-Foo: 1\r\n\r\n"))


def test_serve_keeps_running_after_a_bad_frame() -> None:
    from hive_planner.mcp_server import serve

    ping_buf = BytesIO()
    write_message(ping_buf, {"jsonrpc": "2.0", "id": 9, "method": "ping", "params": {}})
    stdin = BytesIO(b"X-Foo: 1\r\n\r\n" + ping_buf.getvalue())
    stdout = BytesIO()
    assert serve(stdin, stdout) == 0
    stdout.seek(0)
    first = read_message(stdout)
    second = read_message(stdout)
    assert first["error"]["code"] == -32700
    assert second["id"] == 9
    assert second["result"] == {}


def test_content_length_roundtrip() -> None:
    buf = BytesIO()
    write_message(buf, {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}})
    buf.seek(0)
    message = read_message(buf)
    assert message["method"] == "ping"
    reply = handle_rpc(message)
    assert reply["result"] == {}


def test_enable_writes_hive_planner_and_keeps_other_servers(tmp_path: Path) -> None:
    cursor = tmp_path / ".cursor"
    cursor.mkdir()
    (cursor / "mcp.json").write_text(
        json.dumps({"mcpServers": {"other": {"command": "npx", "args": ["demo"]}}}, indent=2),
        encoding="utf-8",
    )
    config = LauncherConfig(python_executable="py -3.11")
    result = run_set_hive_planner_mcp(tmp_path, config, enabled=True)
    assert result["ok"] is True
    assert result["enabled"] is True
    assert result["name"] == HIVE_PLANNER_MCP_NAME
    doc = load_mcp_document(tmp_path)
    assert doc["mcpServers"]["other"]["command"] == "npx"
    entry = doc["mcpServers"][HIVE_PLANNER_MCP_NAME]
    assert entry["command"]
    assert "mcp-serve" in entry["args"]
    assert hive_planner_mcp_enabled(doc) is True
    disabled = run_set_hive_planner_mcp(tmp_path, config, enabled=False)
    assert disabled["ok"] is True
    assert disabled["enabled"] is False
    again = load_mcp_document(tmp_path)
    assert again["mcpServers"][HIVE_PLANNER_MCP_NAME].get("disabled") is True
    assert hive_planner_mcp_enabled(again) is False


def test_peek_without_config_is_disabled(tmp_path: Path) -> None:
    result = peek_hive_planner_mcp(tmp_path, LauncherConfig(python_executable="py -3.11"))
    assert result["ok"] is True
    assert result["enabled"] is False


def test_cli_mcp_serve_dispatches(monkeypatch) -> None:
    called = {"n": 0}

    def fake_serve() -> int:
        called["n"] += 1
        return 0

    monkeypatch.setattr("hive_planner.mcp_server.serve", fake_serve)
    assert main(["mcp-serve"]) == 0
    assert called["n"] == 1


def test_call_tool_ping_explicit_root(tmp_path: Path) -> None:
    payload = call_tool("hive_ping", {"root": str(tmp_path)})
    assert payload["ok"] is True
    assert Path(payload["root"]) == tmp_path.resolve()
