"""Stdio MCP server so a Cursor agent can call Hive Planner (stdlib JSON-RPC)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "hive-planner"

_ROOT_PROP = {
    "type": "string",
    "description": "Project folder. Defaults to the process working directory (usually the Cursor workspace).",
}


def _schema(properties: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    props = {"root": _ROOT_PROP}
    if properties:
        props.update(properties)
    schema: dict[str, Any] = {"type": "object", "properties": props, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


TOOLS: list[dict[str, Any]] = [
    {
        "name": "hive_ping",
        "description": "Confirm this Hive Planner MCP server is running.",
        "inputSchema": _schema(),
    },
    {
        "name": "hive_health_check",
        "description": "Run Hive Planner ci-check on the project (plans, specs, maps, tests).",
        "inputSchema": _schema(),
    },
    {
        "name": "hive_sync_impact_maps",
        "description": "Merge discovered src/test paths into change-impact maps.",
        "inputSchema": _schema(
            {"dry_run": {"type": "boolean", "description": "Report map changes without writing files."}}
        ),
    },
    {
        "name": "hive_bug_hunt_status",
        "description": "Whether bug-hunt chat files are installed in the project.",
        "inputSchema": _schema(),
    },
    {
        "name": "hive_bug_hunt_enable",
        "description": "Install or refresh the bug-hunt chat command in the project.",
        "inputSchema": _schema({"iterations": {"type": "integer", "minimum": 1, "maximum": 200}}),
    },
    {
        "name": "hive_implementation_loop_enable",
        "description": "Install the implementation-loop coordinator into the project.",
        "inputSchema": _schema(
            {
                "pack": {"type": "string", "enum": ["1-pack", "4-pack"]},
                "force_pack": {"type": "boolean"},
            },
            required=["pack"],
        ),
    },
    {
        "name": "hive_implementation_loop_status",
        "description": "Report whether a spec feature is ready for the implementation loop.",
        "inputSchema": _schema({"feature": {"type": "string"}}),
    },
    {
        "name": "hive_implementation_loop_start",
        "description": "Start implementation-loop coordinator gates for a feature.",
        "inputSchema": _schema(
            {
                "feature": {"type": "string"},
                "allow_dirty": {"type": "boolean"},
                "force_feature": {"type": "boolean"},
            }
        ),
    },
    {
        "name": "hive_implementation_loop_handoff",
        "description": "Write handoff.md and increment round_trips.",
        "inputSchema": _schema(
            {
                "role": {"type": "string"},
                "continue_after_cap": {"type": "boolean"},
            },
            required=["role"],
        ),
    },
    {
        "name": "hive_implementation_loop_check",
        "description": "Run checker infrastructure (build, test:quick, wiring audit).",
        "inputSchema": _schema(),
    },
    {
        "name": "hive_implementation_loop_accept",
        "description": "Accept a result.md entry for a role.",
        "inputSchema": _schema({"role": {"type": "string"}}, required=["role"]),
    },
    {
        "name": "hive_implementation_loop_commit",
        "description": "Commit after checker and reviewer pass. Does not push.",
        "inputSchema": _schema(),
    },
    {
        "name": "hive_agnostic_loop_enable",
        "description": "Install the agnostic pause-cycle loop kit into the project.",
        "inputSchema": _schema(),
    },
    {
        "name": "hive_agnostic_loop_status",
        "description": "Show agnostic-loop cycle state.",
        "inputSchema": _schema(),
    },
    {
        "name": "hive_agnostic_loop_rewards",
        "description": "List agnostic-loop catalog reward ids.",
        "inputSchema": _schema(),
    },
    {
        "name": "hive_agnostic_loop_arm",
        "description": "Point a paused agnostic-loop sequence at a reward.",
        "inputSchema": _schema(
            {"reward": {"type": "string"}, "cycles": {"type": "integer"}},
            required=["reward"],
        ),
    },
    {
        "name": "hive_agnostic_loop_begin",
        "description": "Open one agnostic-loop hook.",
        "inputSchema": _schema(),
    },
    {
        "name": "hive_agnostic_loop_review",
        "description": "Close the open agnostic-loop hook and pause.",
        "inputSchema": _schema({"note": {"type": "string"}}, required=["note"]),
    },
    {
        "name": "hive_agnostic_loop_observe",
        "description": "Record a hit or miss for an agnostic-loop reward.",
        "inputSchema": _schema(
            {"reward": {"type": "string"}, "hit": {"type": "boolean"}},
            required=["reward", "hit"],
        ),
    },
    {
        "name": "hive_agnostic_loop_choose",
        "description": "Pick the next agnostic-loop reward (MCTS + Thompson).",
        "inputSchema": _schema(
            {
                "open": {"type": "string"},
                "arm": {"type": "boolean"},
                "cycles": {"type": "integer"},
            }
        ),
    },
]


def _version() -> str:
    try:
        from importlib.metadata import version

        return version("hive-planner")
    except Exception:
        return "1.3.0"


def _workspace_root(arguments: dict[str, Any] | None) -> Path:
    raw = str((arguments or {}).get("root") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.cwd().resolve()


def _bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _tool_hive_ping(arguments: dict[str, Any]) -> dict[str, Any]:
    root = _workspace_root(arguments)
    return {
        "ok": True,
        "server": SERVER_NAME,
        "version": _version(),
        "root": str(root),
        "cwd": str(Path.cwd().resolve()),
    }


def _tool_hive_health_check(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_ci_check

    return run_project_ci_check(_workspace_root(arguments))


def _tool_hive_sync_impact_maps(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_map_sync

    return run_project_map_sync(_workspace_root(arguments), dry_run=_bool(arguments.get("dry_run")))


def _tool_hive_bug_hunt_status(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import peek_bug_hunt_status

    return peek_bug_hunt_status(_workspace_root(arguments))


def _tool_hive_bug_hunt_enable(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.bug_hunt import validate_iterations
    from hive_planner.launcher.service import run_project_bug_hunt_install

    iterations = arguments.get("iterations", 50)
    try:
        count = validate_iterations(iterations)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return run_project_bug_hunt_install(_workspace_root(arguments), iterations=count)


def _tool_hive_implementation_loop_enable(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_implementation_loop_install

    pack = str(arguments.get("pack") or "").strip()
    if pack not in {"1-pack", "4-pack"}:
        return {"ok": False, "error": "pack must be 1-pack or 4-pack"}
    return run_project_implementation_loop_install(
        _workspace_root(arguments),
        pack,
        force_pack=_bool(arguments.get("force_pack")),
    )


def _tool_hive_implementation_loop_status(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_implementation_loop_status

    return run_project_implementation_loop_status(
        _workspace_root(arguments),
        _optional_str(arguments.get("feature")),
    )


def _tool_hive_implementation_loop_start(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_implementation_loop_start

    return run_project_implementation_loop_start(
        _workspace_root(arguments),
        _optional_str(arguments.get("feature")),
        allow_dirty=_bool(arguments.get("allow_dirty")),
        force_feature=_bool(arguments.get("force_feature")),
    )


def _tool_hive_implementation_loop_handoff(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_implementation_loop_handoff

    role = str(arguments.get("role") or "").strip()
    if not role:
        return {"ok": False, "error": "role is required"}
    return run_project_implementation_loop_handoff(
        _workspace_root(arguments),
        role,
        continue_after_cap=_bool(arguments.get("continue_after_cap")),
    )


def _tool_hive_implementation_loop_check(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_implementation_loop_check

    return run_project_implementation_loop_check(_workspace_root(arguments))


def _tool_hive_implementation_loop_accept(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_implementation_loop_accept

    return run_project_implementation_loop_accept(
        _workspace_root(arguments),
        str(arguments.get("role") or ""),
    )


def _tool_hive_implementation_loop_commit(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_implementation_loop_commit

    return run_project_implementation_loop_commit(_workspace_root(arguments))


def _tool_hive_agnostic_loop_enable(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_agnostic_loop_install

    return run_project_agnostic_loop_install(_workspace_root(arguments))


def _tool_hive_agnostic_loop_status(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_agnostic_loop_status

    return run_project_agnostic_loop_status(_workspace_root(arguments))


def _tool_hive_agnostic_loop_rewards(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_agnostic_loop_rewards

    return run_project_agnostic_loop_rewards(_workspace_root(arguments))


def _tool_hive_agnostic_loop_arm(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_agnostic_loop_arm

    reward = str(arguments.get("reward") or "").strip()
    if not reward:
        return {"ok": False, "error": "reward is required"}
    cycles = arguments.get("cycles", 30)
    try:
        count = int(cycles)
    except (TypeError, ValueError):
        return {"ok": False, "error": "cycles must be an integer"}
    return run_project_agnostic_loop_arm(_workspace_root(arguments), reward, count)


def _tool_hive_agnostic_loop_begin(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_agnostic_loop_begin

    return run_project_agnostic_loop_begin(_workspace_root(arguments))


def _tool_hive_agnostic_loop_review(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_agnostic_loop_review

    note = str(arguments.get("note") or "").strip()
    if not note:
        return {"ok": False, "error": "note is required"}
    return run_project_agnostic_loop_review(_workspace_root(arguments), note)


def _tool_hive_agnostic_loop_observe(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_agnostic_loop_observe

    reward = str(arguments.get("reward") or "").strip()
    if not reward:
        return {"ok": False, "error": "reward is required"}
    if "hit" not in arguments:
        return {"ok": False, "error": "hit is required"}
    return run_project_agnostic_loop_observe(
        _workspace_root(arguments),
        reward,
        _bool(arguments.get("hit")),
    )


def _tool_hive_agnostic_loop_choose(arguments: dict[str, Any]) -> dict[str, Any]:
    from hive_planner.launcher.service import run_project_agnostic_loop_choose

    cycles = arguments.get("cycles", 1)
    try:
        count = int(cycles)
    except (TypeError, ValueError):
        return {"ok": False, "error": "cycles must be an integer"}
    return run_project_agnostic_loop_choose(
        _workspace_root(arguments),
        _optional_str(arguments.get("open")),
        do_arm=_bool(arguments.get("arm")),
        cycles=count,
    )


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "hive_ping": _tool_hive_ping,
    "hive_health_check": _tool_hive_health_check,
    "hive_sync_impact_maps": _tool_hive_sync_impact_maps,
    "hive_bug_hunt_status": _tool_hive_bug_hunt_status,
    "hive_bug_hunt_enable": _tool_hive_bug_hunt_enable,
    "hive_implementation_loop_enable": _tool_hive_implementation_loop_enable,
    "hive_implementation_loop_status": _tool_hive_implementation_loop_status,
    "hive_implementation_loop_start": _tool_hive_implementation_loop_start,
    "hive_implementation_loop_handoff": _tool_hive_implementation_loop_handoff,
    "hive_implementation_loop_check": _tool_hive_implementation_loop_check,
    "hive_implementation_loop_accept": _tool_hive_implementation_loop_accept,
    "hive_implementation_loop_commit": _tool_hive_implementation_loop_commit,
    "hive_agnostic_loop_enable": _tool_hive_agnostic_loop_enable,
    "hive_agnostic_loop_status": _tool_hive_agnostic_loop_status,
    "hive_agnostic_loop_rewards": _tool_hive_agnostic_loop_rewards,
    "hive_agnostic_loop_arm": _tool_hive_agnostic_loop_arm,
    "hive_agnostic_loop_begin": _tool_hive_agnostic_loop_begin,
    "hive_agnostic_loop_review": _tool_hive_agnostic_loop_review,
    "hive_agnostic_loop_observe": _tool_hive_agnostic_loop_observe,
    "hive_agnostic_loop_choose": _tool_hive_agnostic_loop_choose,
}


def list_tool_names() -> list[str]:
    return [str(item["name"]) for item in TOOLS]


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": f"Unknown tool: {name}"}
    return handler(dict(arguments or {}))


def _initialize_result() -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": _version()},
    }


def handle_rpc(message: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one JSON-RPC message. Notifications (no id) return None."""
    method = str(message.get("method") or "")
    msg_id = message.get("id")
    params = message.get("params")
    if not isinstance(params, dict):
        params = {}
    if msg_id is None:
        return None
    try:
        if method == "initialize":
            result: Any = _initialize_result()
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            name = str(params.get("name") or "").strip()
            arguments = params.get("arguments")
            if not isinstance(arguments, dict):
                arguments = {}
            payload = call_tool(name, arguments)
            is_error = bool(payload.get("ok") is False) or name not in _HANDLERS
            result = {
                "content": [{"type": "text", "text": json.dumps(payload, indent=2, default=str)}],
                "isError": is_error,
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32603, "message": str(exc)},
        }
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def read_message(buf) -> dict[str, Any] | None:
    """Return None only on end of input. Malformed frames raise ValueError."""
    headers: dict[str, str] = {}
    saw_line = False
    while True:
        line = buf.readline()
        if not line:
            if not saw_line:
                return None
            raise ValueError("MCP headers truncated")
        saw_line = True
        if line in (b"\r\n", b"\n"):
            break
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        key, _, value = text.partition(":")
        headers[key.strip().lower()] = value.strip()
    raw_len = headers.get("content-length")
    if not raw_len:
        raise ValueError("MCP message missing Content-Length")
    try:
        length = int(raw_len)
    except ValueError as exc:
        raise ValueError("MCP Content-Length is not an integer") from exc
    if length < 0:
        raise ValueError("MCP Content-Length is negative")
    body = buf.read(length)
    if len(body) < length:
        raise ValueError("MCP message body truncated")
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("MCP message must be a JSON object")
    return data


def write_message(buf, message: dict[str, Any]) -> None:
    raw = json.dumps(message, ensure_ascii=False).encode("utf-8")
    buf.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw)
    buf.flush()


def serve(stdin=None, stdout=None) -> int:
    in_buf = stdin if stdin is not None else sys.stdin.buffer
    out_buf = stdout if stdout is not None else sys.stdout.buffer
    while True:
        try:
            message = read_message(in_buf)
        except (json.JSONDecodeError, ValueError) as exc:
            write_message(
                out_buf,
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}},
            )
            continue
        if message is None:
            return 0
        reply = handle_rpc(message)
        if reply is not None:
            write_message(out_buf, reply)


def main(argv: list[str] | None = None) -> int:
    del argv
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
