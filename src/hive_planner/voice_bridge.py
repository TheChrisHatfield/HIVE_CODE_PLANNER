"""Local bridge: exposes the pending approval and accepts replies over loopback HTTP (T017).

The extension client calls this listener instead of a stub modal. Every request must carry
the per-session token written under `.hive/voice-bot/bridge-token`. A request without a valid
token is refused before any runner call, so it creates no session, no state change, and no reply.

Every request is checked against a declared schema (R18, R23) before dispatch: required
fields, types, id format, length limits, enumerated modes, no unknown keys, and the bound
workspace. A failed check returns `{"error": <code>}` with status 400 and reaches no runner logic.

Endpoints (127.0.0.1 only). Query parameters for GET, JSON body for POST:

- `GET  /v1/approval?workspace=` -> `{"pending": bool, "request_id", "task_id", "kind", "action"}`
- `POST /v1/reply`    `{"workspace", "task_id", "request_id", "text", "editor_snapshot"?}` -> the
  `reply_approval` result. `editor_snapshot` is the live T007 object at approval time (R22).
  409 when there is no pending approval, the request_id is stale, or the task_id does not match.
- `POST /v1/submit`   `{"workspace", "instruction", "client_request_id", "mode"?, "file_path"?,
  "selection_text"?, "file_content"?, "editor_snapshot"?}` -> the `submit` result (`task_id` and
  `context_snapshot_id`, or a queued entry). `editor_snapshot` is the T007 object (R2). 400 with
  `error` = the refusal code (e.g. `path_outside_workspace`), 429 when the queue is full.
- `POST /v1/reply/spoken` `{"workspace", "task_id", "request_id", "wav_path", "editor_snapshot"?}` -> the
  `reply_spoken` result: the WAV is transcribed (same STT gates as submit), then the text goes to the
  pending approval only (never a follow-up). Same 409 rule as `/v1/reply`.
- `POST /v1/submit/spoken` `{"workspace", "client_request_id", "wav_path", "mode"?, "file_path"?}` -> the
  `submit_spoken` result (T042 slice 3). `wav_path` is a workspace-relative WAV, transcribed by the pinned
  STT adapter; the transcript becomes the task instruction. 400 `stt_not_configured` while `stt_provider` is null.
- `GET  /v1/submission?workspace=&client_request_id=` -> where a submit ended up (task or queue entry).
- `GET  /v1/task?workspace=&task_id=&context_snapshot_id=` -> status, `spoken`, `written`.
  404 `unknown_task`; 409 `context_mismatch` when the snapshot id is not the task's.
- `GET  /v1/editor?workspace=` -> pending `navigate` / `show_diff` for the extension to execute.
- `POST /v1/editor` `{"workspace", "action_id"}` -> marks that editor action opened.
- `POST /v1/editor/show_diff` `{"workspace", "task_id"}` -> queues a `show_diff` editor action (T043).
- `POST /v1/editor/navigate` `{"workspace", "file_path", "context_snapshot_id"}` -> queues a `navigate` editor
  action (R18 `navigate_to`; the R23 path check and snapshot bind apply).
- `POST /v1/playback/interrupt` `{"workspace"}` -> `VoiceTaskRunner.interrupt_playback()` result
  (session `interrupted`; task state unchanged, T031/R7).
- `POST /v1/call/end` `{"workspace"}` -> `VoiceTaskRunner.end_call()` result (session `ended`; active
  task keeps running; queued/held follow-ups discarded, T031/R5/R25).
- `POST /v1/cancel`   `{"workspace", "task_id"}` -> `VoiceTaskRunner.cancel()` result (T036, Patch B).
  404 `unknown_task`; 409 `task_already_terminal` or `session_not_active`.
- `POST /v1/queue`    `{"workspace", "task_id", "text"}` -> `VoiceTaskRunner.queue_follow_up()` result
  (T036, Patch B). 409 `no_active_task` / `task_mismatch` / `session_not_active`; 429 when the queue is full.
- `GET  /v1/diff?workspace=&task_id=` -> `VoiceTaskRunner.task_diff()` result (T036, Patch B).
  404 `unknown_task`; `source` is `no_diff_evidence` unless the R33 latch is on and a write was recorded.
- `POST /v1/reconnect` `{"workspace", "task_id"}` -> `VoiceTaskRunner.reconnect_task()` result (T036, Patch B,
  R26). 409 `not_unknown` / `no_provider_evidence` / `task_slot_occupied`; 404 `unknown_task`.
- `POST /v1/live`   `{"workspace", "file_path", "document_version", "dirty"}` -> 200 `{"status": "recorded"}`.
  T029 producer feed: the extension poll posts the active editor's workspace-relative file, version,
  and dirty flag. The bridge stores it for the R22 live lookup (`record_live_buffer`). Paths must be
  workspace-relative (no absolute path, drive letter, or `..`).

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
from hive_planner.voice_bot import TERMINAL_TASK_STATES, VOICE_BOT_DIR, VoiceBotError, same_workspace
from hive_planner.voice_task import DelegationError, VoiceTaskRunner

TOKEN_FILE = "bridge-token"
ENDPOINT_FILE = "bridge.json"
HOST = "127.0.0.1"
MAX_BODY_BYTES = 16 * 1024
TOKEN_BYTES = 32
# file_content, selection.text, and diagnostics are each capped at snapshot_max_bytes (R21).
EDITOR_SNAPSHOT_FIELDS = 3
ENVELOPE_OVERHEAD_BYTES = 4096  # JSON keys, file name, diagnostic metadata

ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
MODES: tuple[str, ...] = ("ask", "plan", "agent")  # `agent` passes the schema and is refused by the runner (R6)
PATH_MAX = 1024
WORKSPACE_MAX = 4096

# Declared schema per tool: field -> (required, kind).
# Kinds: workspace, id, text, mode, relpath, snapshot, editor, version (int), flag (bool), livepath.
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
        "editor_snapshot": (False, "editor"),
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
    # Spoken approval reply: a workspace WAV is transcribed, then routed to the pending approval only.
    "reply_spoken": {
        "workspace": (True, "workspace"),
        "task_id": (True, "id"),
        "request_id": (True, "id"),
        "wav_path": (True, "relpath"),
        "editor_snapshot": (False, "editor"),
    },
    # T042 slice 3: spoken turn from a workspace WAV file. Same workspace/auth/schema as `submit`.
    "submit_spoken": {
        "workspace": (True, "workspace"),
        "client_request_id": (True, "id"),
        "wav_path": (True, "relpath"),
        "mode": (False, "mode"),
        "file_path": (False, "relpath"),
        "editor_snapshot": (False, "editor"),
    },
    "editor": {"workspace": (True, "workspace")},
    "editor_ack": {"workspace": (True, "workspace"), "action_id": (True, "id")},
    "live": {
        "workspace": (True, "workspace"),
        "file_path": (True, "livepath"),
        "document_version": (True, "version"),
        "dirty": (True, "flag"),
    },
    "playback_interrupt": {"workspace": (True, "workspace")},
    "call_end": {"workspace": (True, "workspace")},
    "cancel": {"workspace": (True, "workspace"), "task_id": (True, "id")},
    "queue": {
        "workspace": (True, "workspace"),
        "task_id": (True, "id"),
        "text": (True, "text"),
    },
    "diff": {"workspace": (True, "workspace"), "task_id": (True, "id")},
    "show_diff": {"workspace": (True, "workspace"), "task_id": (True, "id")},
    "navigate": {
        "workspace": (True, "workspace"),
        "file_path": (True, "relpath"),
        "context_snapshot_id": (True, "id"),
    },
    "reconnect": {"workspace": (True, "workspace"), "task_id": (True, "id")},
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
    """HTTP body must fit the instruction plus an editor snapshot at its limit (R2, R21).

    The editor snapshot carries three R21-capped fields (file content, selection, diagnostics),
    so the body allows that plus JSON overhead.
    """
    return max(
        MAX_BODY_BYTES,
        int(snapshot_max_bytes) * EDITOR_SNAPSHOT_FIELDS + int(instruction_max_chars) * 4 + 4096,
    )


def token_matches(presented: str | None, expected: str) -> bool:
    if not presented or not expected:
        return False
    left = presented.encode("utf-8")
    right = expected.encode("utf-8")
    # compare_digest raises when lengths differ; a wrong-length token is still unauthorized.
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def _same_workspace(value: str, root: Path) -> bool:
    return same_workspace(value, root)


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
            encoded = json.dumps(raw, ensure_ascii=False).encode("utf-8")
            if len(encoded) > snapshot_max_bytes * EDITOR_SNAPSHOT_FIELDS + ENVELOPE_OVERHEAD_BYTES:
                raise ToolArgError("editor_snapshot_too_long", "exceeds the configured snapshot limit")
            out[name] = raw
            continue
        if kind == "version":
            if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 2**31 - 1:
                raise ToolArgError(f"bad_{name}", "must be a non-negative integer")
            out[name] = raw
            continue
        if kind == "flag":
            if not isinstance(raw, bool):
                raise ToolArgError(f"bad_{name}", "must be true or false")
            out[name] = raw
            continue
        if kind == "livepath":
            if not isinstance(raw, str) or len(raw) > PATH_MAX or "\x00" in raw:
                raise ToolArgError(f"bad_{name}", "must be a workspace-relative path")
            normalized = raw.replace("\\", "/")
            if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
                raise ToolArgError(f"bad_{name}", "must be a workspace-relative path")
            out[name] = normalized
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
        # R22 live buffer: file path (relative to the workspace) -> (document_version, dirty).
        self._live: dict[str, tuple[int, bool]] = {}
        self._live_lock = threading.Lock()

    def record_live_buffer(self, file_path: str, document_version: int, dirty: bool) -> None:
        """Record the editor's current buffer state for one file (fed by the extension poll)."""
        with self._live_lock:
            self._live[file_path] = (int(document_version), bool(dirty))

    def live_buffer_for(self, file_path: str) -> tuple[int, bool] | None:
        """Runner lookup for the R22 check. None means no reading, so the runner skips the check."""
        with self._live_lock:
            return self._live.get(file_path)

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
        # Install the R22 live lookup at startup so submit and reply can enforce it.
        self.runner.set_live_buffer(self.live_buffer_for)
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
        if self.runner.live_buffer_lookup() == self.live_buffer_for:  # bound methods: compare with ==
            self.runner.set_live_buffer(None)
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
    "/v1/diff": "diff",
}
_POST_ROUTES = {
    "/v1/reply": "reply",
    "/v1/reply/spoken": "reply_spoken",
    "/v1/submit": "submit",
    "/v1/submit/spoken": "submit_spoken",
    "/v1/editor": "editor_ack",
    "/v1/editor/show_diff": "show_diff",
    "/v1/editor/navigate": "navigate",
    "/v1/live": "live",
    "/v1/playback/interrupt": "playback_interrupt",
    "/v1/call/end": "call_end",
    "/v1/cancel": "cancel",
    "/v1/queue": "queue",
    "/v1/reconnect": "reconnect",
}

# Runner refusals that are state conflicts (409); unknown ids are 404; anything else is 400.
_CONFLICT_CODES = frozenset({
    "task_already_terminal", "not_unknown", "no_provider_evidence", "task_slot_occupied",
    "task_mismatch", "no_active_task", "session_not_active",
})


def _reply_status(result: dict[str, Any]) -> int:
    """Shared HTTP status for approval replies: a stale or missing approval is 409 (nothing executed)."""
    return 409 if result.get("status") in (
        "no_pending_approval", "stale_approval", "task_mismatch",
    ) else 200


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
            if length <= 0:
                self._send(400, {"error": "bad_length"})
                return None
            if length > max_body:
                self._drain_body(length)
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

        def _runner_refusal(self, exc: DelegationError) -> None:
            status = 404 if exc.code == "unknown_task" else (409 if exc.code in _CONFLICT_CODES else 400)
            payload: dict[str, Any] = {"error": exc.code, "message": str(exc)}
            if exc.spoken:
                payload["spoken"] = exc.spoken
            self._send(status, payload)

        def do_GET(self) -> None:  # noqa: N802 - stdlib name
            route, _, query = self.path.partition("?")
            if len(route) > 1:
                route = route.rstrip("/")
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
            elif tool == "diff":
                try:
                    self._send(200, bridge.runner.task_diff(args["task_id"]))
                except DelegationError as exc:
                    self._runner_refusal(exc)
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

        def _drain_body(self, length: int | None = None) -> None:
            """Read and discard any request body before replying early.

            Replying to a POST without reading its body can make the OS reset the socket
            while the client is still sending, which surfaces as ConnectionAbortedError.
            """
            if length is None:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self.close_connection = True
                    return
            if length <= 0:
                return
            cap = 1_000_000
            try:
                self.rfile.read(min(length, cap))
            except OSError:
                pass
            if length > cap:
                self.close_connection = True

        def do_POST(self) -> None:  # noqa: N802 - stdlib name
            route, _, _ = self.path.partition("?")
            if len(route) > 1:
                route = route.rstrip("/")
            tool = _POST_ROUTES.get(route)
            if tool is None:
                self._drain_body()
                self._send(404, {"error": "not_found"})
                return
            if not self._authorized():
                self._drain_body()
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
            elif tool == "reply_spoken":
                self._reply_spoken(args)
            elif tool == "editor_ack":
                result = bridge.runner.ack_editor_action(args["action_id"])
                status = 404 if result.get("status") == "unknown_action" else 200
                self._send(status, result)
            elif tool == "live":
                bridge.record_live_buffer(args["file_path"], args["document_version"], args["dirty"])
                self._send(200, {"status": "recorded"})
            elif tool == "playback_interrupt":
                self._send(200, bridge.runner.interrupt_playback())
            elif tool == "call_end":
                self._send(200, bridge.runner.end_call())
            elif tool in ("cancel", "queue", "reconnect", "show_diff", "navigate"):
                self._runner_control(tool, args)
            elif tool == "submit_spoken":
                self._spoken(args)
            else:
                self._submit(args)

        def _runner_control(self, tool: str, args: dict[str, Any]) -> None:
            """Patch B routes: cancel, queue_follow_up, reconnect_task, show_diff. Runner refusals keep their code."""
            try:
                if tool == "cancel":
                    result = bridge.runner.cancel(args["task_id"])
                elif tool == "show_diff":
                    result = bridge.runner.show_diff(args["task_id"])
                elif tool == "navigate":
                    result = bridge.runner.navigate_to(
                        args["file_path"], context_snapshot_id=args["context_snapshot_id"],
                    )
                elif tool == "queue":
                    result = bridge.runner.queue_follow_up(args["text"], task_id=args["task_id"])
                else:
                    result = bridge.runner.reconnect_task(args["task_id"])
            except DelegationError as exc:
                self._runner_refusal(exc)
                return
            self._send(200, result)

        def _reply(self, args: dict[str, Any]) -> None:
            result = bridge.runner.reply_approval(
                args["text"],
                request_id=args["request_id"],
                task_id=args["task_id"],
                editor_snapshot=args.get("editor_snapshot") or None,
            )
            self._send(_reply_status(result), result)

        def _reply_spoken(self, args: dict[str, Any]) -> None:
            """`POST /v1/reply/spoken`: transcribe a workspace WAV, then reply to the pending approval."""
            try:
                result = bridge.runner.reply_spoken(
                    request_id=args["request_id"],
                    task_id=args["task_id"],
                    wav_path=args["wav_path"],
                    editor_snapshot=args.get("editor_snapshot") or None,
                )
            except DelegationError as exc:
                self._runner_refusal(exc)
                return
            self._send(_reply_status(result), result)

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
                payload: dict[str, Any] = {"error": exc.code, "message": str(exc)}
                if exc.spoken:
                    payload["spoken"] = exc.spoken
                self._send(status, payload)
                return
            self._send(200, result)

        def _spoken(self, args: dict[str, Any]) -> None:
            """`POST /v1/submit/spoken` (T042 slice 3): transcribe a workspace WAV, then submit the text."""
            try:
                result = bridge.runner.submit_spoken(
                    wav_path=args["wav_path"],
                    client_request_id=args["client_request_id"],
                    mode=args.get("mode", "ask"),
                    file_path=args.get("file_path", ""),
                    editor_snapshot=args.get("editor_snapshot") or None,
                )
            except DelegationError as exc:
                status = 429 if exc.code == "queue_full" else 400
                payload: dict[str, Any] = {"error": exc.code, "message": str(exc)}
                if exc.spoken:
                    payload["spoken"] = exc.spoken
                self._send(status, payload)
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
        msg = f"{submitted.get('error', 'submit_failed')}: {submitted.get('message', '')}".rstrip(": ")
        spoken = str(submitted.get("spoken") or "").strip()
        if spoken:
            msg = f"{msg} ({spoken})"
        raise VoiceBotError(msg)

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
