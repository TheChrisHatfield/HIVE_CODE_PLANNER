"""ACP JSON-RPC adapter over stdio (Voice_Bot T003; hook: cursor.acp).

Owns one persistent ``agent acp`` child process. Responsibilities:

- newline-delimited JSON-RPC 2.0 framing on stdin/stdout,
- response routing by request id (requests may be concurrent),
- server-initiated requests (e.g. ``session/request_permission``) routed to a
  handler and answered on the wire without blocking the reader,
- notifications (e.g. ``session/update``) queued for the caller,
- disconnect detection: stdout EOF or process exit fails every pending request
  with :class:`AcpDisconnected` and marks the client disconnected (R20 ``unknown``
  basis; no automatic re-submit).

This module does not decide task state. HIVE maps disconnects to R20 transitions.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

JSONRPC = "2.0"
METHOD_NOT_FOUND = -32601

ServerRequestHandler = Callable[[str, Any], Any]

# A server-request handler returns DEFER to answer later with reply()/reply_error().
# The reader thread must not block on approvals (T008, R27 protocol reader stays active).
DEFER = object()


class AcpError(Exception):
    """Base error for the ACP adapter."""


class AcpDisconnected(AcpError):
    """The provider process exited or its stdout closed."""


class AcpTimeout(AcpError):
    """A request got no response within its timeout."""


class AcpRemoteError(AcpError):
    """The provider answered a request with a JSON-RPC error object."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"ACP error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


@dataclass
class _Pending:
    event: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: AcpError | None = None


class AcpClient:
    """Persistent JSON-RPC client bound to one child process."""

    def __init__(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None = None,
        server_request_handler: ServerRequestHandler | None = None,
    ) -> None:
        self._argv = list(argv)
        self._handler = server_request_handler
        self._proc = subprocess.Popen(
            self._argv,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._pending: dict[str, _Pending] = {}
        self._next_id = 0
        self._disconnect_reason: str | None = None
        self.current_server_request_id: Any = None
        self.notifications: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._reader = threading.Thread(target=self._read_loop, name="acp-reader", daemon=True)
        self._reader.start()

    # -- public API -------------------------------------------------------

    @property
    def pid(self) -> int:
        return self._proc.pid

    def is_connected(self) -> bool:
        with self._state_lock:
            if self._disconnect_reason is not None:
                return False
        return self._proc.poll() is None

    def disconnect_reason(self) -> str | None:
        with self._state_lock:
            return self._disconnect_reason

    def request(self, method: str, params: Any = None, *, timeout: float = 30.0) -> Any:
        """Send a request and block until its response routes back by id."""
        pending = _Pending()
        with self._state_lock:
            if self._disconnect_reason is not None:
                raise AcpDisconnected(self._disconnect_reason)
            self._next_id += 1
            req_id = str(self._next_id)
            self._pending[req_id] = pending
        try:
            self._send({"jsonrpc": JSONRPC, "id": req_id, "method": method, "params": params})
        except AcpDisconnected:
            with self._state_lock:
                self._pending.pop(req_id, None)
            raise
        if not pending.event.wait(timeout):
            with self._state_lock:
                self._pending.pop(req_id, None)
            raise AcpTimeout(f"no response to {method} within {timeout}s")
        if pending.error is not None:
            raise pending.error
        return pending.result

    def notify(self, method: str, params: Any = None) -> None:
        self._send({"jsonrpc": JSONRPC, "method": method, "params": params})

    def close(self) -> None:
        """Close stdin, then terminate the child if it does not exit."""
        try:
            if self._proc.stdin and not self._proc.stdin.closed:
                self._proc.stdin.close()
        except OSError:
            pass
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=5)
        self._reader.join(timeout=5)

    # -- internals --------------------------------------------------------

    def _send(self, message: dict[str, Any]) -> None:
        line = json.dumps(message, separators=(",", ":"))
        with self._write_lock:
            if not self.is_connected():
                raise AcpDisconnected(self.disconnect_reason() or "provider_exited")
            try:
                assert self._proc.stdin is not None
                self._proc.stdin.write(line + "\n")
                self._proc.stdin.flush()
            except (OSError, ValueError) as exc:
                self._mark_disconnected(f"provider_write_failed: {exc}")
                raise AcpDisconnected(self._disconnect_reason or "provider_write_failed") from exc

    def _read_loop(self) -> None:
        assert self._proc.stdout is not None
        try:
            for raw in self._proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue  # non-protocol noise on stdout is ignored, not fatal
                if isinstance(message, dict):
                    self._dispatch(message)
        except (OSError, ValueError):
            pass
        returncode = self._proc.wait()
        self._mark_disconnected(f"provider_disconnected (exit {returncode})")

    def _dispatch(self, message: dict[str, Any]) -> None:
        has_method = "method" in message
        has_id = "id" in message and message["id"] is not None
        if has_method and has_id:
            self._handle_server_request(message)
        elif has_method:
            self.notifications.put(message)
        elif has_id:
            self._route_response(message)

    def _route_response(self, message: dict[str, Any]) -> None:
        req_id = str(message["id"])
        with self._state_lock:
            pending = self._pending.pop(req_id, None)
        if pending is None:
            return  # late reply after timeout; nothing waits on it
        if "error" in message and message["error"] is not None:
            err = message["error"] if isinstance(message["error"], dict) else {}
            pending.error = AcpRemoteError(
                int(err.get("code", 0)), str(err.get("message", "")), err.get("data")
            )
        else:
            pending.result = message.get("result")
        pending.event.set()

    def _handle_server_request(self, message: dict[str, Any]) -> None:
        method = str(message["method"])
        req_id = message["id"]
        if self._handler is None:
            self._reply_error(req_id, METHOD_NOT_FOUND, f"no handler for {method}")
            return
        self.current_server_request_id = req_id  # set on the reader thread only
        try:
            result = self._handler(method, message.get("params"))
        except Exception as exc:  # handler failure must not kill the reader
            self._reply_error(req_id, -32603, f"handler failed: {exc}")
            return
        if result is DEFER:
            return  # answered later via reply()/reply_error()
        self._send_quiet({"jsonrpc": JSONRPC, "id": req_id, "result": result})

    def reply(self, req_id: Any, result: Any) -> None:
        """Answer a server request that the handler deferred."""
        self._send_quiet({"jsonrpc": JSONRPC, "id": req_id, "result": result})

    def reply_error(self, req_id: Any, code: int, message: str) -> None:
        self._reply_error(req_id, code, message)

    def _reply_error(self, req_id: Any, code: int, message: str) -> None:
        self._send_quiet(
            {"jsonrpc": JSONRPC, "id": req_id, "error": {"code": code, "message": message}}
        )

    def _send_quiet(self, message: dict[str, Any]) -> None:
        try:
            self._send(message)
        except AcpDisconnected:
            pass

    def _mark_disconnected(self, reason: str) -> None:
        with self._state_lock:
            if self._disconnect_reason is None:
                self._disconnect_reason = reason
            pending = list(self._pending.values())
            self._pending.clear()
        for item in pending:
            item.error = AcpDisconnected(reason)
            item.event.set()
        self.notifications.put(None)  # sentinel: stream ended


def open_agent_acp(agent_path: str, *, cwd: str | None = None,
                   server_request_handler: ServerRequestHandler | None = None) -> AcpClient:
    """Start ``<agent_path> acp`` as one persistent ACP session transport."""
    return AcpClient([agent_path, "acp"], cwd=cwd, server_request_handler=server_request_handler)
