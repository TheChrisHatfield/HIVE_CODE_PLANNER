"""Read and write Cursor project MCP config (`.cursor/mcp.json`)."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

MCP_REL = Path(".cursor") / "mcp.json"
HIVE_PLANNER_MCP_NAME = "hive-planner"
_SERVER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class McpConfigError(ValueError):
    """User-facing MCP config problem."""


def mcp_config_path(root: Path) -> Path:
    return Path(root).resolve() / MCP_REL


def validate_mcp_name(name: str) -> str:
    value = str(name or "").strip()
    if not _SERVER_NAME.fullmatch(value):
        raise McpConfigError(
            "Server name must start with a letter or digit and use only letters, digits, dot, underscore, or hyphen."
        )
    return value


def parse_mcp_args(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise McpConfigError("Args JSON is not valid.") from exc
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise McpConfigError("Args JSON must be an array of strings.")
        return [str(item) for item in data]
    try:
        return shlex.split(text, posix=False)
    except ValueError as exc:
        raise McpConfigError(str(exc) or "Could not parse args.") from exc


def format_mcp_token(text: str) -> str:
    if not text or any(ch.isspace() for ch in text) or any(ch in text for ch in "\"'"):
        return '"' + text.replace('"', '\\"') + '"'
    return text


def format_mcp_args(args: list[str]) -> str:
    return " ".join(format_mcp_token(str(item)) for item in args)


def format_mcp_invocation(command: str, args: list[str] | None = None) -> str:
    """One shell line. A path with spaces stays a single token."""
    parts: list[str] = []
    command = str(command or "").strip()
    if command:
        parts.append(format_mcp_token(command))
    if args:
        formatted = format_mcp_args([str(item) for item in args])
        if formatted:
            parts.append(formatted)
    return " ".join(parts)


def load_mcp_document(root: Path) -> dict[str, Any]:
    path = mcp_config_path(root)
    if not path.is_file():
        return {"mcpServers": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise McpConfigError(".cursor/mcp.json is not valid JSON") from exc
    except UnicodeDecodeError as exc:
        raise McpConfigError(".cursor/mcp.json is not UTF-8 (save it without UTF-16 encoding)") from exc
    except OSError as exc:
        raise McpConfigError(str(exc)) from exc
    if not isinstance(data, dict):
        raise McpConfigError(".cursor/mcp.json must be a JSON object")
    servers = data.get("mcpServers")
    if servers is None:
        data["mcpServers"] = {}
    elif not isinstance(servers, dict):
        raise McpConfigError("mcpServers must be an object")
    return data


def save_mcp_document(root: Path, data: dict[str, Any]) -> Path:
    path = mcp_config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return path


def list_mcp_servers(doc: dict[str, Any]) -> list[dict[str, Any]]:
    servers = doc.get("mcpServers") if isinstance(doc, dict) else None
    if not isinstance(servers, dict):
        return []
    rows: list[dict[str, Any]] = []
    for name, raw in servers.items():
        if not isinstance(name, str) or not isinstance(raw, dict):
            continue
        disabled = bool(raw.get("disabled"))
        if raw.get("enabled") is False:
            disabled = True
        args_raw = raw.get("args") or []
        args = [str(item) for item in args_raw] if isinstance(args_raw, list) else []
        rows.append(
            {
                "name": name,
                "command": str(raw.get("command") or ""),
                "args": args,
                "url": str(raw.get("url") or ""),
                "enabled": not disabled,
            }
        )
    rows.sort(key=lambda row: row["name"].lower())
    return rows


def upsert_mcp_server(
    doc: dict[str, Any],
    name: str,
    *,
    command: str = "",
    args: list[str] | None = None,
    url: str = "",
    enabled: bool = True,
) -> dict[str, Any]:
    key = validate_mcp_name(name)
    command = str(command or "").strip()
    url = str(url or "").strip()
    if bool(command) == bool(url):
        raise McpConfigError("Enter a command or a URL, not both.")
    servers = doc.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
        doc["mcpServers"] = servers
    existing = servers.get(key)
    entry = dict(existing) if isinstance(existing, dict) else {}
    if url:
        entry["url"] = url
        entry.pop("command", None)
        entry.pop("args", None)
    else:
        entry["command"] = command
        if args:
            entry["args"] = list(args)
        else:
            entry.pop("args", None)
        entry.pop("url", None)
    if enabled:
        entry.pop("disabled", None)
        if "enabled" in entry:
            entry.pop("enabled", None)
    else:
        entry["disabled"] = True
        entry["enabled"] = False
    servers[key] = entry
    return doc


def hive_planner_stdio_launch(config: Any) -> tuple[str, list[str]]:
    """Command + args Cursor uses to start this Hive Planner as an MCP server."""
    from hive_planner.runtime_paths import hive_cli_argv

    argv = hive_cli_argv(config, "mcp-serve")
    if not argv:
        raise McpConfigError("Could not build the Hive Planner MCP launch command.")
    return str(argv[0]), [str(part) for part in argv[1:]]


def hive_planner_mcp_enabled(doc: dict[str, Any]) -> bool:
    servers = doc.get("mcpServers") if isinstance(doc, dict) else None
    if not isinstance(servers, dict):
        return False
    entry = servers.get(HIVE_PLANNER_MCP_NAME)
    if not isinstance(entry, dict):
        return False
    if entry.get("disabled") or entry.get("enabled") is False:
        return False
    return bool(str(entry.get("command") or "").strip() or str(entry.get("url") or "").strip())


def set_hive_planner_mcp(
    doc: dict[str, Any],
    *,
    enabled: bool,
    command: str,
    args: list[str] | None = None,
) -> dict[str, Any]:
    if not enabled:
        servers = doc.setdefault("mcpServers", {})
        if not isinstance(servers, dict):
            servers = {}
            doc["mcpServers"] = servers
        existing = servers.get(HIVE_PLANNER_MCP_NAME)
        if isinstance(existing, dict) and (
            str(existing.get("command") or "").strip() or str(existing.get("url") or "").strip()
        ):
            existing["disabled"] = True
            existing["enabled"] = False
            return doc
    return upsert_mcp_server(
        doc,
        HIVE_PLANNER_MCP_NAME,
        command=command,
        args=list(args or []),
        enabled=enabled,
    )


def remove_mcp_server(doc: dict[str, Any], name: str) -> dict[str, Any]:
    key = str(name or "").strip()
    servers = doc.get("mcpServers")
    if not isinstance(servers, dict) or key not in servers:
        raise McpConfigError(f"No MCP server named {key or '(blank)'}.")
    del servers[key]
    return doc
