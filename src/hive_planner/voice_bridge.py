"""Local bridge: exposes the pending approval and accepts replies over loopback HTTP (T017).

The extension client calls this listener instead of a stub modal. Every request must carry
the per-session token written under `.hive/voice-bot/bridge-token`. A request without a valid
token is refused before any runner call, so it creates no session, no state change, and no reply.

Every request is checked against a declared schema (R18, R23) before dispatch: required
fields, types, id format, length limits, enumerated modes, no unknown keys, and the bound
workspace. A failed check returns `{"error": <code>}` with status 400 and reaches no runner logic.

Endpoints (127.0.0.1 only). Query parameters for GET, JSON body for POST:

- `GET  /v1/approval?workspace=` -> `{"pending": bool, "request_id", "task_id", "kind", "action"}`
- `POST /v1/reply`    `{"workspace", "task_id", "request_id", "text"}` -> the `reply_approval` result.
  409 when there is no pending approval, the request_id is stale, or the task_id does not match.
- `POST /v1/submit`   `{"workspace", "instruction", "client_request_id", "mode"?, "file_path"?,
  "selection_text"?, "file_content"?, "editor_snapshot"?}` -> the `submit` result (`task_id` and
  `context_snapshot_id`, or a queued entry). `editor_snapshot` is the T007 object (R2). 400 with
  `error` = the refusal code (e.g. `path_outside_workspace`), 429 when the queue is full.
- `GET  /v1/submission?workspace=&client_request_id=` -> where a submit ended up (task or queue entry).
- `GET  /v1/task?workspace=&task_id=&context_snapshot_id=` -> status, `spoken`, `written`.
  404 `unknown_task`; 409 `context_mismatch` when the snapshot id is not the task's.
- `GET  /v1/editor?workspace=` -> pending `navigate` / `show_diff` for the extension to execute.
- `POST /v1/editor` `{"workspace", "action_id"}` -> marks that editor action opened.

The bridge owns the only runner while it is live (the runner lock in `voice_lock.py` is held for
its whole life, so a second process cannot start a runner or write state). `voice-bot turn`
delegates here (`run_turn_via_bridge`) instead of writing `state.json` from a second process.

Files written under `.hive/voice-bot/` while the bridge runs (removed on close):

- `bridge-token`  the per-session token (raw text, owner-only permissions where the OS honours them)
- `bridge.json`   `{"host", "port", "started_at"}` so the extension can find the listener
"""

from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import TERMINAL_TASK_STATES, VOICE_BOT_DIR, VoiceBotError
from hive_planner.voice_task import DelegationError, VoiceTaskRunner

TOKEN_FILE = "bridge-token"
ENDPOINT_FILE = "bridge.json"
HOST = "127.0.0.1"
MAX_BODY_BYTES = 16 * 1024
TOKEN_BYTES = 32

ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
MODES: tuple[str, ...] = ("ask", "plan", "agent")  # `agent` passes the schema and is refused by the runner (R6)
PATH_MAX = 1024
WORKSPACE_MAX = 4096

# Declared schema per tool: field -> (required, kind).
# Kinds: workspace, id, text, mode, relpath, snapshot, editor.
TOOL_SCHEMAS: dict[str, dict[str, tuple[bool, str]]] = {
    "approval": {"workspace": (True, "workspace")},
    "submission": {"workspace": (True, "workspace"), "client_request_id": (True, "id")},
    "task": {
        "workspace": (True, "workspace"),
        "task_id": (True, "id"),
        "context_snapshot_id": (True, "id"),
    },
    "reply": {
        "workspace": (True, "workspace"),
        "task_id": (True, "id"),
        "request_id": (True, "id"),
        "text": (True, "text"),
    },
    "submit": {
        "workspace": (True, "workspace"),
        "instruction": (True, "text"),
        "client_request_id": (True, "id"),
        "mode": (False, "mode"),
        "file_path": (False, "relpath"),
        "selection_text": (False, "snapshot"),
        "file_content": (False, "snapshot"),
        "editor_snapshot": (False, "editor"),
    },
    "editor": {"workspace": (True, "workspace")},
    "editor_ack": {"workspace": (True, "workspace"), "action_id": (True, "id")},
}


class ToolArgError(Exception):
    """A request failed its tool schema. `code` is the stable refusal reason (returned as `error`)."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bridge_token_path(paths: RepoPaths) -> Path:
    return paths.root / VOICE_BOT_DIR / TOKEN_FILE


def bridge_endpoint_path(paths: RepoPaths) -> Path:
    return paths.root / VOICE_BOT_DIR / ENDPOINT_FILE


def issue_token(paths: RepoPaths) -> str:
    """Generate a fresh per-session token and write it owner-only. Never logged."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    path = bridge_token_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token)
    return token


def max_submit_body_bytes(instruction_max_chars: int, snapshot_max_bytes: int) -> int:
    """HTTP body must fit the instruction plus two R21 snapshot fields (R2, R21)."""
    return max(
        MAX_BODY_BYTES,
        int(snapshot_max_bytes) * 2 + int(instruction_max_chars) * 4 + 4096,
    )


def token_matches(presented: str | None, expected: str) -> bool:
    if not presented or not expected:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def _same_workspace(value: str, root: Path) -> bool:
    return os.path.normcase(os.path.realpath(value)) == os.path.normcase(os.path.realpath(root))


def validate_tool_args(
    tool: str,
    data: dict[str, Any],
    *,
    root: Path,
    instruction_max_chars: int,
    snapshot_max_bytes: int = 64 * 1024,
) -> dict[str, Any]:
    """Check `data` against `TOOL_SCHEMAS[tool]` and return the normalized arguments.

    Checks, in order: unknown keys, required fields, types, id format, lengths, the mode enum,
    and the workspace binding (R23). Raises `ToolArgError` with a stable code on the first failure.
    """
    schema = TOOL_SCHEMAS[tool]
    unknown = sorted(set(data) - set(schema))
    if unknown:
        raise ToolArgError("unknown_argument", ", ".join(unknown))
    out: dict[str, Any] = {}
    defaults: dict[str, Any] = {"mode": "ask", "file_path": "", "editor_snapshot": None}
    for name, (required, kind) in schema.items():
        raw = data.get(name)
        # An empty text is a value, not a missing field: an empty spoken reply must reach the
        # runner, which re-prompts (R6). Empty ids, workspaces, and optional fields are missing.
        if raw is None or (raw == "" and kind != "text"):
            if required:
                raise ToolArgError(f"missing_{name}")
            out[name] = defaults.get(name, "")
            continue
        if kind == "editor":
            if not isinstance(raw, dict):
                raise ToolArgError("bad_editor_snapshot", "must be a JSON object")
            encoded = json.dumps(raw).encode("utf-8")
            if len(encoded) > snapshot_max_bytes * 2:
                raise ToolArgError("editor_snapshot_too_long", "exceeds the configured snapshot limit")
            out[name] = raw
            continue
        if not isinstance(raw, str):
            raise ToolArgError(f"bad_{name}", "must be a string")
        if "\x00" in raw:
            raise ToolArgError(f"bad_{name}", "contains a NUL byte")
        if kind == "workspace":
            if len(raw) > WORKSPACE_MAX or not _same_workspace(raw, root):
                raise ToolArgError("workspace_mismatch", "workspace is not the one bound to this bridge")
        elif kind == "id":
            if not ID_PATTERN.fullmatch(raw):
                raise ToolArgError(f"bad_{name}", "must be 1-128 of letters, digits, '_', '.', ':', '-'")
        elif kind == "text":
            if len(raw) > instruction_max_chars:
                raise ToolArgError(f"{name}_too_long", "exceeds the configured limit")
        elif kind == "snapshot":
            if len(raw.encode("utf-8")) > snapshot_max_bytes:
                raise ToolArgError(f"{name}_too_long", "exceeds the configured snapshot limit")
        elif kind == "mode":
            if raw not in MODES:
                raise ToolArgError("invalid_mode", f"mode must be one of {', '.join(MODES)}")
        elif kind == "relpath":
            if len(raw) > PATH_MAX:
                raise ToolArgError(f"{name}_too_long", "exceeds the path length limit")
        out[name] = raw
    return out


class VoiceBridge:
    """Loopback listener bound to one runner. Start once per voice session; close when done."""

    def __init__(self, runner: VoiceTaskRunner) -> None:
        self.runner = runner
        self.paths = runner.paths
        self._token = ""
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        assert self._server is not None, "bridge not started"
        return int(self._server.server_address[1])

    @property
    def token(self) -> str:
        return self._token

    def validate(self, tool: str, data: dict[str, Any]) -> dict[str, Any]:
        return validate_tool_args(
            tool,
            data,
            root=self.paths.root,
            instruction_max_chars=self.runner.config.instruction_max_chars,
            snapshot_max_bytes=self.runner.config.snapshot_max_bytes,
        )

    def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("bridge already started")
        self._token = issue_token(self.paths)
        handler = _make_handler(self)
        self._server = ThreadingHTTPServer((HOST, 0), handler)
        self._server.daemon_threads = True
        endpoint = bridge_endpoint_path(self.paths)
        endpoint.write_text(
            json.dumps({"host": HOST, "port": self.port, "started_at": _utc_now()}, indent=2),
            encoding="utf-8",
        )
        self._thread = threading.Thread(target=self._server.serve_forever, name="voice-bridge", daemon=True)
        self._thread.start()

    def close(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            server.shutdown()
            server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        for path in (bridge_token_path(self.paths), bridge_endpoint_path(self.paths)):
            path.unlink(missing_ok=True)
        self._token = ""


class BridgeAlreadyRunning(RuntimeError):
    """A live listener already owns `.hive/voice-bot/bridge.json` for this repo."""


class BridgeUnavailable(VoiceBotError):
    """`bridge.json` names a listener that could not be reached during a delegated call."""


def bridge_is_live(paths: RepoPaths) -> bool:
    """True only when `bridge.json` names a listener that still accepts connections.

    A missing, unreadable, or dead endpoint is stale and does not block a new start.
    """
    endpoint = bridge_endpoint_path(paths)
    if not endpoint.exists():
        return False
    try:
        data = json.loads(endpoint.read_text(encoding="utf-8"))
        host, port = str(data["host"]), int(data["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def start_bridge(runner: VoiceTaskRunner) -> VoiceBridge:
    """Start the bridge for `runner`, refusing when another live bridge owns this repo.

    The runner already holds the cross-process runner lock (see `voice_lock.py`), so no other
    process can be writing state while this bridge serves requests.
    """
    if bridge_is_live(runner.paths):
        raise BridgeAlreadyRunning(
            "a voice bridge is already running for this repo (see .hive/voice-bot/bridge.json)"
        )
    bridge = VoiceBridge(runner)
    bridge.start()
    return bridge


_GET_ROUTES = {
    "/v1/approval": "approval",
    "/v1/submission": "submission",
    "/v1/task": "task",
    "/v1/editor": "editor",
}
_POST_ROUTES = {"/v1/reply": "reply", "/v1/submit": "submit", "/v1/editor": "editor_ack"}


def _make_handler(bridge: VoiceBridge) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "HiveVoiceBridge/1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
            return  # keep the token and request bodies out of logs

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization", "")
            prefix = "Bearer "
            presented = header[len(prefix):] if header.startswith(prefix) else None
            return token_matches(presented, bridge.token)

        def _read_json_body(self) -> dict[str, Any] | None:
            """Parse the request body as a JSON object, or send the 400 and return None."""
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send(400, {"error": "bad_length"})
                return None
            cfg = bridge.runner.config
            max_body = max_submit_body_bytes(cfg.instruction_max_chars, cfg.snapshot_max_bytes)
            if length <= 0 or length > max_body:
                self._send(400, {"error": "bad_length"})
                return None
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send(400, {"error": "bad_json"})
                return None
            if not isinstance(data, dict):
                self._send(400, {"error": "bad_body"})
                return None
            return data

        def _refuse(self, exc: ToolArgError) -> None:
            self._send(400, {"error": exc.code, "message": str(exc)})

        def do_GET(self) -> None:  # noqa: N802 - stdlib name
            route, _, query = self.path.partition("?")
            tool = _GET_ROUTES.get(route)
            if tool is None:
                self._send(404, {"error": "not_found"})
                return
            if not self._authorized():
                self._send(401, {"error": "unauthorized"})
                return
            params = {key: values[0] for key, values in parse_qs(query, keep_blank_values=True).items()}
            try:
                args = bridge.validate(tool, params)
            except ToolArgError as exc:
                self._refuse(exc)
                return
            if tool == "approval":
                self._send(200, bridge.runner.pending_approval_view())
            elif tool == "submission":
                try:
                    self._send(200, bridge.runner.submission_view(args["client_request_id"]))
                except DelegationError:
                    self._send(404, {"error": "unknown_submission"})
            elif tool == "editor":
                self._send(200, bridge.runner.pending_editor_action())
            else:
                self._task(args)

        def _task(self, args: dict[str, Any]) -> None:
            try:
                view = bridge.runner.task_result(args["task_id"])
            except DelegationError:
                self._send(404, {"error": "unknown_task"})
                return
            if view.get("context_snapshot_id") != args["context_snapshot_id"]:
                self._send(409, {"error": "context_mismatch"})
                return
            self._send(200, view)

        def do_POST(self) -> None:  # noqa: N802 - stdlib name
            tool = _POST_ROUTES.get(self.path)
            if tool is None:
                self._send(404, {"error": "not_found"})
                return
            if not self._authorized():
                self._send(401, {"error": "unauthorized"})
                return
            data = self._read_json_body()
            if data is None:
                return
            try:
                args = bridge.validate(tool, data)
            except ToolArgError as exc:
                self._refuse(exc)
                return
            if tool == "reply":
                self._reply(args)
            elif tool == "editor_ack":
                result = bridge.runner.ack_editor_action(args["action_id"])
                status = 404 if result.get("status") == "unknown_action" else 200
                self._send(status, result)
            else:
                self._submit(args)

        def _reply(self, args: dict[str, Any]) -> None:
            result = bridge.runner.reply_approval(
                args["text"], request_id=args["request_id"], task_id=args["task_id"],
            )
            status = 409 if result.get("status") in (
                "no_pending_approval", "stale_approval", "task_mismatch",
            ) else 200
            self._send(status, result)

        def _submit(self, args: dict[str, Any]) -> None:
            """`POST /v1/submit`: the same runner.submit the CLI uses; the bridge is the only writer."""
            try:
                result = bridge.runner.submit(
                    args["instruction"],
                    mode=args.get("mode", "ask"),
                    file_path=args.get("file_path", ""),
                    client_request_id=args["client_request_id"],
                    selection_text=args.get("selection_text", ""),
                    file_content=args.get("file_content", ""),
                    editor_snapshot=args.get("editor_snapshot") or None,
                )
            except DelegationError as exc:
                status = 429 if exc.code == "queue_full" else 400
                self._send(status, {"error": exc.code, "message": str(exc)})
                return
            self._send(200, result)

    return Handler


def run_turn_via_bridge(
    paths: RepoPaths,
    *,
    instruction: str,
    mode: str,
    file_path: str,
    client_request_id: str,
    timeout: float,
) -> dict[str, Any]:
    """Submit through the live bridge and wait for the turn to settle. Returns the CLI turn payload.

    A submit that lands behind an active task is queued (R5). This waits for the queue to
    dispatch it, then for the task to reach a terminal state, so the caller never reports a
    queued turn as finished. Raises `BridgeUnavailable` when the listener cannot be reached; the
    caller must not fall back to a second runner in that case.
    """
    endpoint = json.loads(bridge_endpoint_path(paths).read_text(encoding="utf-8"))
    token = bridge_token_path(paths).read_text(encoding="utf-8")
    base = f"http://{endpoint['host']}:{endpoint['port']}"
    workspace = str(paths.root)

    def call(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(base + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=max(timeout, 5.0)) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except OSError as exc:
            raise BridgeUnavailable(f"bridge not reachable: {exc}") from exc

    status, submitted = call("POST", "/v1/submit", {
        "workspace": workspace, "instruction": instruction, "mode": mode, "file_path": file_path,
        "client_request_id": client_request_id,
    })
    if status != 200:
        raise VoiceBotError(f"{submitted.get('error', 'submit_failed')}: {submitted.get('message', '')}".rstrip(": "))

    deadline = time.monotonic() + timeout + 30
    task_id: str | None = submitted.get("task_id")
    context_id: str = str(submitted.get("context_snapshot_id") or "")
    sub_state = str(submitted.get("state") or "")
    while not task_id and sub_state != "discarded":
        if time.monotonic() > deadline:
            break
        query = urlencode({"workspace": workspace, "client_request_id": client_request_id})
        status, sub = call("GET", f"/v1/submission?{query}")
        if status != 200:
            raise VoiceBotError(f"{sub.get('error', 'submission_failed')}")
        sub_state = str(sub.get("state") or "")
        task_id = sub.get("task_id")
        context_id = str(sub.get("context_snapshot_id") or "")
        if not task_id and sub_state != "discarded":
            time.sleep(0.1)

    view: dict[str, Any] = {}
    if task_id:
        while True:
            query = urlencode({"workspace": workspace, "task_id": task_id, "context_snapshot_id": context_id})
            status, view = call("GET", f"/v1/task?{query}")
            if status != 200:
                raise VoiceBotError(f"{view.get('error', 'task_failed')}")
            if view.get("state") in TERMINAL_TASK_STATES or time.monotonic() > deadline:
                break
            time.sleep(0.1)
    state = view.get("state") if task_id else sub_state
    settled = state in TERMINAL_TASK_STATES
    return {
        "submit": submitted,
        "task_id": task_id,
        "state": state,
        "reason": view.get("reason", "") if task_id else "",
        "tests_status": view.get("tests_status") if settled else None,
        "spoken": view.get("spoken", "") if task_id else submitted.get("spoken", ""),
        "written": view.get("written", "") if task_id else "",
    }
