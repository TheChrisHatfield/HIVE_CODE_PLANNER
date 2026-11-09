"""Voice_Bot task runner: delegation, state machine, approvals, queue, results (T004-T011).

Hooks: agent.sessions, agent.events, agent.permissions, voice.interruption, voice.results.

Design rules this module enforces:

- One persistent ACP session per runner. One active coding turn at a time (R5).
  Submits and follow-ups that arrive while a turn is active are queued (FIFO, R5).
- Blocking ACP calls never run while the runner lock is held. The protocol reader
  thread must stay free to deliver `session/request_permission` (R27, T008).
- Every task state change goes through `_transition`, which enforces the R20 table
  and appends a record (SC-011).
- Speech is produced only from recorded evidence (R14). Test claims come from the
  R8 mapping over the task's evidence record file (SC-013).
- Interrupting playback changes no task state (R7, SC-003). Ending the call discards
  queued follow-ups but leaves the task running (R1, R5, R25).

Provisional mappings (to be confirmed against a logged-in `agent acp` run, G2):
the ACP method names, the mode ids `ask`/`plan`, permission option kinds
`allow*`/`reject*`, and the `execute` tool-call shape used for test evidence.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hive_planner.config import RepoPaths, validate_feature_id
from hive_planner.voice_acp import (
    DEFER,
    AcpClient,
    AcpDisconnected,
    AcpError,
    AcpRemoteError,
    AcpTimeout,
    open_agent_acp,
)
from hive_planner.voice_bot import (
    CODING_TASK_STATES,
    TERMINAL_TASK_STATES,
    VOICE_BOT_DIR,
    CodingTask,
    ContextSnapshot,
    TestsStatus,
    VoiceBotConfig,
    VoiceBotError,
    VoiceBotState,
    VoiceSession,
    create_context_snapshot,
    load_state,
    load_voice_bot_config,
    resolve_cartridge_trace,
    save_state,
)

ALLOWED_MODES: tuple[str, ...] = ("ask", "plan")  # `agent` is refused until G6 closes (R6)
APPROVAL_KINDS: tuple[str, ...] = ("write_or_command", "plan", "question")

# R20 transition table. Terminal states have no outgoing edges.
TRANSITIONS: dict[str, frozenset[str]] = {
    "submitted": frozenset({"running", "failed", "cancel_requested", "unknown"}),
    "running": frozenset({"awaiting_approval", "completed", "failed", "cancel_requested", "unknown"}),
    "awaiting_approval": frozenset({"running", "completed", "failed", "cancel_requested", "unknown"}),
    "cancel_requested": frozenset({"cancelled", "failed", "unknown"}),
    "unknown": frozenset({"submitted", "running", "awaiting_approval", "cancel_requested", "failed"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}

TEST_COMMAND_RE = re.compile(
    r"\b(pytest|py\.test|unittest|npm (?:run )?test|yarn test|pnpm test|jest|vitest"
    r"|go test|cargo test|dotnet test)\b",
    re.IGNORECASE,
)

TEST_SPEECH: dict[str, str] = {
    "passed": "Tests passed.",
    "failed": "Tests failed.",
    "not_run": "Tests were not run.",
    "unknown": "Test status is unknown.",
}

RAW_EVENT_CAP = 500


class DelegationError(VoiceBotError):
    """A bounded delegation call was refused. `code` is the stable reason string."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _shorten(text: str, max_chars: int) -> str:
    """Shorten speech to the R14/R21 cap. Full text stays in written_result."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def cap_text(text: str, max_bytes: int) -> tuple[str, bool]:
    """Return (text, truncated) with an explicit flag (R21). Never silent."""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text, False
    return raw[:max_bytes].decode("utf-8", errors="ignore"), True


# ---------------------------------------------------------------------------
# R8 test-state mapping (T011)
# ---------------------------------------------------------------------------


def evidence_record_path(paths: RepoPaths, task_id: str) -> Path:
    return paths.root / VOICE_BOT_DIR / "evidence" / f"{task_id}.json"


def tests_status_from_record(record: Any) -> TestsStatus:
    """Map a parsed evidence record to the R8 test state.

    - missing / unparsable record (not a dict, or no `test_commands` list) -> unknown
    - present record with no test commands                               -> not_run
    - any test command without an integer exit code                      -> unknown
    - any test command with non-zero exit                                -> failed
    - all test commands exit 0                                           -> passed
    """
    if not isinstance(record, dict):
        return "unknown"
    commands = record.get("test_commands")
    if not isinstance(commands, list):
        return "unknown"
    if not commands:
        return "not_run"
    codes: list[int] = []
    for entry in commands:
        code = entry.get("exit_code") if isinstance(entry, dict) else None
        if not isinstance(code, int) or isinstance(code, bool):
            return "unknown"
        codes.append(code)
    return "failed" if any(code != 0 for code in codes) else "passed"


def tests_status_for_task(paths: RepoPaths, task_id: str) -> TestsStatus:
    """Read the task's evidence record file and map it (missing or unreadable -> unknown)."""
    path = evidence_record_path(paths, task_id)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown"
    return tests_status_from_record(record)


def build_spoken_summary(state: str, reason: str, tests: TestsStatus, max_chars: int) -> str:
    """Spoken summary from recorded evidence only. Test status comes first so truncation keeps it."""
    if state == "completed":
        head = "Task completed."
    else:
        head = f"Task failed: {reason}."
    return _shorten(f"{TEST_SPEECH[tests]} {head}", max_chars)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


ClientFactory = Callable[[Callable[[str, Any], Any]], AcpClient]


class VoiceTaskRunner:
    """One voice session, one persistent ACP session, one active coding turn."""

    def __init__(
        self,
        paths: RepoPaths,
        feature: str,
        *,
        agent_path: str = "agent",
        client_factory: ClientFactory | None = None,
        request_timeout: float = 600.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.paths = paths
        self.feature = validate_feature_id(feature)
        self.config: VoiceBotConfig = load_voice_bot_config(paths)
        self.agent_path = agent_path
        self._client_factory: ClientFactory = client_factory or self._default_client_factory
        self._request_timeout = request_timeout
        self._clock = clock
        self._lock = threading.RLock()

        self.state: VoiceBotState = load_state(paths)
        if self.state.voice_session is None or self.state.voice_session.state == "ended":
            # Start a new voice session but keep existing tasks and their records (R4, R26).
            self.state.voice_session = VoiceSession(
                session_id=_new_id("vs"),
                state="active",
                feature_id=self.feature,
                cartridge_trace=resolve_cartridge_trace(paths, self.feature),
                started_at=_now(),
            )
            self._save()

        self._client: AcpClient | None = None
        self._acp_session_id = ""
        self._mode_set = ""
        self._active_task_id: str | None = None
        self._pending_approval: dict[str, Any] | None = None
        self._pending_cmd: dict[str, str] = {}
        self._test_records: dict[str, list[dict[str, Any]]] = {}
        self._progress_last: dict[str, float] = {}
        self._provider_lost_timers: dict[str, threading.Timer] = {}
        self._call_ended = False

    # -- helpers ----------------------------------------------------------

    @property
    def session(self) -> VoiceSession:
        assert self.state.voice_session is not None
        return self.state.voice_session

    @property
    def active_task_id(self) -> str | None:
        with self._lock:
            return self._active_task_id

    def _save(self) -> None:
        save_state(self.paths, self.state)

    def _get_task(self, task_id: str) -> CodingTask:
        task = self.state.coding_tasks.get(task_id)
        if task is None:
            raise DelegationError("unknown_task", f"no task {task_id}")
        return task

    def _active_task(self) -> CodingTask | None:
        if self._active_task_id is None:
            return None
        return self.state.coding_tasks.get(self._active_task_id)

    def _event(self, task: CodingTask, name: str, payload: dict[str, Any] | None = None) -> None:
        task.events.append({"name": name, "at": _now(), "payload": payload or {}})

    def _transition(self, task: CodingTask, to: str, reason: str) -> None:
        if to not in CODING_TASK_STATES or to not in TRANSITIONS.get(task.state, frozenset()):
            raise DelegationError("illegal_transition", f"{task.state} -> {to} ({reason})")
        task.transitions.append({"from": task.state, "to": to, "reason": reason, "at": _now()})
        task.state = to
        task.reason = reason
        task.updated_at = _now()
        self._event(task, "task.cancelled" if to == "cancelled" else f"task.{to}", {"reason": reason})

    def _say(self, task: CodingTask, text: str) -> bool:
        """Record a spoken update. Returns False (and records nothing) after the call ends (R25)."""
        if self._call_ended:
            return False
        spoken = _shorten(text, self.config.spoken_update_max_chars)
        task.evidence.spoken_update = spoken
        self._event(task, "speech.spoken", {"text": spoken})
        return True

    def _resolve_file(self, file_path: str) -> str:
        """R23 path validation: the file must resolve inside the bound workspace."""
        if not file_path:
            return ""
        root = self.paths.root.resolve()
        target = (root / file_path).resolve()
        try:
            rel = target.relative_to(root)
        except ValueError as exc:
            raise DelegationError("path_outside_workspace", f"{file_path} is outside the workspace") from exc
        if not target.is_file():
            raise DelegationError("file_not_found", f"{rel.as_posix()} does not exist")
        return rel.as_posix()

    def _validate_instruction(self, text: str) -> str:
        stripped = (text or "").strip()
        if not stripped:
            raise DelegationError("instruction_required", "instruction is empty")
        if len(text) > self.config.instruction_max_chars:
            raise DelegationError("instruction_too_long", "instruction exceeds the configured limit")
        return stripped

    def _prompt_text(self, task: CodingTask) -> str:
        parts = [f"Mode: {task.mode}. Read-only request; do not modify files."]
        if task.file_path:
            parts.append(f"Active file: {task.file_path}.")
        parts.append(task.instruction)
        return " ".join(parts)

    def _default_client_factory(self, handler: Callable[[str, Any], Any]) -> AcpClient:
        return open_agent_acp(self.agent_path, cwd=str(self.paths.root), server_request_handler=handler)

    # -- ACP session (blocking; never called under the lock) ---------------

    def _ensure_session(self, mode: str) -> None:
        with self._lock:
            client = self._client if (self._client is not None and self._client.is_connected()) else None
        if client is None:
            client = self._client_factory(self._handle_server_request)
            try:
                client.request(
                    "initialize", {"protocolVersion": 1, "clientCapabilities": {}},
                    timeout=self._request_timeout,
                )
                result = client.request(
                    "session/new", {"cwd": str(self.paths.root), "mcpServers": []},
                    timeout=self._request_timeout,
                )
            except AcpError:
                client.close()
                raise
            session_id = result.get("sessionId") if isinstance(result, dict) else None
            if not session_id:
                client.close()
                raise VoiceBotError("session/new returned no sessionId")
            threading.Thread(target=self._pump, args=(client,), name="voice-pump", daemon=True).start()
            with self._lock:
                self._client = client
                self._acp_session_id = str(session_id)
                self._mode_set = ""
        if self._mode_set != mode:
            # Fail closed: if the provider will not confirm the mode, no prompt is sent.
            client.request(
                "session/set_mode", {"sessionId": self._acp_session_id, "modeId": mode},
                timeout=self._request_timeout,
            )
            with self._lock:
                self._mode_set = mode

    def _pump(self, client: AcpClient) -> None:
        """Route session/update notifications into the active task, in arrival order."""
        while True:
            item = client.notifications.get()
            if item is None:
                break
            marker = item.get("_marker")
            if marker is not None:
                marker.set()
                continue
            if item.get("method") == "session/update":
                with self._lock:
                    self._on_update(item.get("params") or {})

    def _drain(self, client: AcpClient) -> None:
        """Wait until the pump has processed every notification received so far."""
        if not client.is_connected():
            return
        marker = threading.Event()
        client.notifications.put({"_marker": marker})  # type: ignore[arg-type]
        marker.wait(timeout=5)

    # -- server requests from the agent (reader thread) --------------------

    def _handle_server_request(self, method: str, params: Any) -> Any:
        if method == "session/request_permission":
            return self._on_permission(params if isinstance(params, dict) else {})
        raise VoiceBotError(f"unsupported client method {method}")

    def _on_update(self, params: dict[str, Any]) -> None:
        if str(params.get("sessionId") or "") != self._acp_session_id:
            return
        task = self._active_task()
        if task is None:
            return
        task.raw_events.append(params)
        del task.raw_events[:-RAW_EVENT_CAP]
        update = params.get("update") or {}
        if not isinstance(update, dict):
            return
        kind = update.get("sessionUpdate")
        if kind == "agent_message_chunk":
            content = update.get("content") or {}
            text = str(content.get("text", "")) if isinstance(content, dict) else ""
            task.evidence.written_result += text
            self._event(task, "task.progress", {"chunk_chars": len(text)})
            self._maybe_progress_speech(task)
        elif kind == "tool_call":
            call_id = str(update.get("toolCallId") or "")
            raw_input = update.get("rawInput") or {}
            command = raw_input.get("command") if isinstance(raw_input, dict) else None
            if command and call_id:
                self._pending_cmd[call_id] = str(command)
            self._event(task, "task.progress", {"tool": str(update.get("title") or "")})
        elif kind == "tool_call_update":
            call_id = str(update.get("toolCallId") or "")
            command = self._pending_cmd.get(call_id)
            status = update.get("status")
            if command and status in ("completed", "failed"):
                self._pending_cmd.pop(call_id, None)
                if TEST_COMMAND_RE.search(command):
                    raw_output = update.get("rawOutput") or {}
                    code = raw_output.get("exitCode") if isinstance(raw_output, dict) else None
                    self._test_records.setdefault(task.task_id, []).append(
                        {"command": command, "exit_code": code if isinstance(code, int) else None}
                    )

    def _maybe_progress_speech(self, task: CodingTask) -> None:
        now = self._clock()
        last = self._progress_last.get(task.task_id)
        if last is None or now - last >= self.config.progress_interval_s:
            if self._say(task, "Still working."):
                self._progress_last[task.task_id] = now

    @staticmethod
    def _approval_kind(params: dict[str, Any]) -> str:
        raw = str(params.get("kind") or "").lower()
        if raw in APPROVAL_KINDS:
            return raw
        tool = params.get("toolCall") or {}
        tool_kind = str(tool.get("kind") or "").lower() if isinstance(tool, dict) else ""
        if tool_kind == "switch_mode":
            return "plan"
        return "write_or_command"

    def _on_permission(self, params: dict[str, Any]) -> Any:
        """R6/R27: create a pending approval and defer the reply. Returns DEFER or a refusal."""
        refuse = {"outcome": {"outcome": "cancelled"}}
        with self._lock:
            task = self._active_task()
            client = self._client
            if task is None or client is None:
                return refuse  # no active task: nothing may execute
            if self._pending_approval is not None:
                self._event(task, "approval.refused", {"reason": "approval_already_pending"})
                return refuse
            tool = params.get("toolCall") or {}
            action = str(tool.get("title") or "perform the requested action") if isinstance(tool, dict) else "perform the requested action"
            kind = self._approval_kind(params)
            options = params.get("options") or []
            request_id = _new_id("apr")
            timer = threading.Timer(self.config.approval_timeout_s, self._on_approval_timeout, args=(request_id,))
            timer.daemon = True
            self._pending_approval = {
                "request_id": request_id,
                "task_id": task.task_id,
                "server_request_id": client.current_server_request_id,
                "client": client,
                "kind": kind,
                "action": action,
                "options": options if isinstance(options, list) else [],
                "timer": timer,
            }
            task.approval = {"request_id": request_id, "kind": kind, "action": action, "status": "pending"}
            self._transition(task, "awaiting_approval", "approval_requested")
            self._refresh_queue_holds()
            self._event(task, "task.awaiting_approval", {"request_id": request_id, "kind": kind})
            if kind == "question":
                self._say(task, f"Question: {action}")
            else:
                self._say(task, f"Approval needed to {action}. Say approve or deny {action}.")
            self._save()
            timer.start()
            return DEFER

    def _resolve_approval(self, pend: dict[str, Any], status: str, reply: dict[str, Any], detail: str) -> None:
        """Close the pending approval with a recorded status. Caller holds the lock."""
        pend["timer"].cancel()
        self._pending_approval = None
        task = self.state.coding_tasks[pend["task_id"]]
        record = {
            "request_id": pend["request_id"],
            "kind": pend["kind"],
            "action": pend["action"],
            "status": status,
            "detail": detail,
            "at": _now(),
        }
        task.approvals.append(record)
        task.approval = record
        self._event(task, "approval.resolved", {"status": status, "kind": pend["kind"]})
        try:
            pend["client"].reply(pend["server_request_id"], reply)
        except AcpDisconnected:
            pass  # provider already gone; nothing can execute either way
        if task.state == "awaiting_approval":
            self._transition(task, "running", f"approval_{status}")
        self._refresh_queue_holds()
        self._save()

    def _on_approval_timeout(self, request_id: str) -> None:
        with self._lock:
            pend = self._pending_approval
            if pend is None or pend["request_id"] != request_id:
                return
            self._resolve_approval(pend, "timed_out", {"outcome": {"outcome": "cancelled"}}, "timeout")

    def reply_approval(self, text: str) -> dict[str, Any]:
        """Route a spoken reply to the pending approval only (R6). Never queues a follow-up."""
        with self._lock:
            pend = self._pending_approval
            if pend is None:
                return {"status": "no_pending_approval", "spoken": ""}
            clean = (text or "").strip()
            action = pend["action"]
            if pend["kind"] == "question":
                if not any(ch.isalnum() for ch in clean):
                    return {"status": "reprompt", "spoken": f"Please answer: {action}"}
                # Provider delivery of a free-text answer is G2-unverified; the protocol
                # request is refused so the provider never sees a fake approval.
                self._resolve_approval(
                    pend, "answered", {"outcome": {"outcome": "cancelled"}}, clean,
                )
                return {"status": "answered", "spoken": "Answer recorded."}

            lowered = clean.lower()
            if action.lower() not in lowered:
                return {"status": "reprompt", "spoken": f"Say approve or deny {action}."}
            says_yes = re.search(r"\bapprove\b", lowered) is not None
            says_no = re.search(r"\bdeny\b", lowered) is not None
            if says_yes == says_no:
                return {"status": "reprompt", "spoken": f"Say approve or deny {action}."}
            if says_no:
                self._resolve_approval(pend, "denied", {"outcome": {"outcome": "cancelled"}}, "user_denied")
                return {"status": "denied", "spoken": "Denied. Nothing was executed."}
            allow = next(
                (o for o in pend["options"] if isinstance(o, dict) and str(o.get("kind", "")).startswith("allow")),
                None,
            )
            if allow is None:
                self._resolve_approval(pend, "denied", {"outcome": {"outcome": "cancelled"}}, "no_allow_option")
                return {"status": "denied", "spoken": "The provider offered no allow option. Nothing was executed."}
            self._resolve_approval(
                pend, "approved",
                {"outcome": {"outcome": "selected", "optionId": allow.get("optionId")}},
                "user_approved",
            )
            return {"status": "approved", "spoken": "Approved."}

    # -- task lifecycle ----------------------------------------------------

    def _settle(self, task: CodingTask) -> None:
        """Write the evidence record and speak the outcome once a task is terminal. Caller holds lock."""
        if task.state == "unknown":
            timer = threading.Timer(
                self.config.reconnect_window_s, self._provider_lost, args=(task.task_id,)
            )
            timer.daemon = True
            self._provider_lost_timers[task.task_id] = timer
            timer.start()
            return
        if task.state not in TERMINAL_TASK_STATES:
            return
        record = {"task_id": task.task_id, "test_commands": self._test_records.get(task.task_id, [])}
        path = evidence_record_path(self.paths, task.task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        tests = tests_status_for_task(self.paths, task.task_id)
        task.evidence.tests_status = tests
        task.evidence.provider_turn_finished = True
        task.evidence.written_result = task.evidence.written_result.strip()
        if task.state == "completed":
            self._event(task, "task.completed", {"tests_status": tests})
            self._say(task, build_spoken_summary("completed", task.reason, tests, self.config.spoken_update_max_chars))
        elif task.state == "failed":
            self._event(task, "task.failed", {"reason": task.reason, "tests_status": tests})
            self._say(task, build_spoken_summary("failed", task.reason, tests, self.config.spoken_update_max_chars))
        # cancelled: written result only (R14 allows no cancellation speech)
        if self._active_task_id == task.task_id:
            self._active_task_id = None
            self._progress_last.pop(task.task_id, None)

    def _provider_lost(self, task_id: str) -> None:
        with self._lock:
            task = self.state.coding_tasks.get(task_id)
            if task is None or task.state != "unknown":
                return
            self._transition(task, "failed", "provider_lost")
            self._settle(task)
            self._save()
        self._dispatch_next()

    def _launch(self, task_id: str) -> None:
        """Open the provider session for a task, then start its prompt. Never holds the lock while blocking."""
        with self._lock:
            task = self.state.coding_tasks[task_id]
            mode = task.mode
        try:
            self._ensure_session(mode)
        except (AcpError, VoiceBotError, OSError) as exc:
            # OSError: the agent binary cannot be started (R19 coding_unavailable path).
            with self._lock:
                reason = "coding_unavailable" if isinstance(exc, OSError) else "submit_error"
                self._transition(task, "failed", f"{reason}: {exc}")
                self._settle(task)
                self._save()
            self._dispatch_next()
            return
        with self._lock:
            if task.state == "cancel_requested":
                self._transition(task, "cancelled", "cancelled_before_dispatch")
                self._settle(task)
                self._save()
                cancelled = True
            else:
                self._transition(task, "running", "provider_accepted")
                task.provider_session_id = self._acp_session_id
                task.provider_kind = "cursor_acp_session"
                self._event(task, "task.started", {"provider_session_id": self._acp_session_id})
                self._say(task, "Task accepted, running.")
                self._save()
                cancelled = False
        if cancelled:
            self._dispatch_next()
            return
        prompt = self._prompt_text(task)
        threading.Thread(
            target=self._run_prompt, args=(task_id, prompt), name="voice-turn", daemon=True
        ).start()

    def _run_prompt(self, task_id: str, prompt: str) -> None:
        with self._lock:
            client = self._client
            session_id = self._acp_session_id
        outcome: tuple[str, str]
        try:
            assert client is not None
            result = client.request(
                "session/prompt",
                {"sessionId": session_id, "prompt": [{"type": "text", "text": prompt}]},
                timeout=self._request_timeout,
            )
            self._drain(client)
            stop = result.get("stopReason") if isinstance(result, dict) else None
            outcome = ("finished", str(stop or ""))
        except AcpDisconnected as exc:
            outcome = ("disconnected", str(exc))
        except AcpTimeout:
            outcome = ("timeout", "")
        except AcpRemoteError as exc:
            outcome = ("remote_error", str(exc))
        except (AcpError, AssertionError) as exc:
            outcome = ("remote_error", str(exc))
        self._finish(task_id, outcome)
        self._dispatch_next()

    def _finish(self, task_id: str, outcome: tuple[str, str]) -> None:
        kind, detail = outcome
        with self._lock:
            task = self.state.coding_tasks[task_id]
            pend = self._pending_approval
            if pend is not None and pend["task_id"] == task_id:
                status = "timed_out"
                self._resolve_approval(pend, status, {"outcome": {"outcome": "cancelled"}}, kind)
            cancel_requested = task.state == "cancel_requested"
            if kind == "finished":
                task.evidence.stop_reason = detail
                if detail == "end_turn":
                    if cancel_requested:
                        self._transition(task, "failed", "cancel_not_acknowledged")
                    else:
                        self._transition(task, "completed", "end_turn")
                elif detail == "cancelled" and cancel_requested:
                    self._transition(task, "cancelled", "cancel_acknowledged")
                elif cancel_requested:
                    self._transition(task, "failed", "cancel_not_acknowledged")
                elif detail == "cancelled":
                    self._transition(task, "failed", "provider_cancelled")
                else:
                    self._transition(task, "failed", f"stop_reason:{detail or 'missing'}")
            elif kind == "disconnected":
                self._transition(task, "unknown", "provider_disconnected")
            elif kind == "timeout":
                if cancel_requested:
                    self._transition(task, "failed", "cancel_not_acknowledged")
                else:
                    self._transition(task, "failed", "provider_timeout")
            else:
                self._transition(task, "failed", "provider_error")
            self._settle(task)
            self._refresh_queue_holds()
            self._save()

    def _refresh_queue_holds(self) -> None:
        held = self._pending_approval is not None
        for entry in self.state.queue:
            if entry.get("state") == "queued" and held:
                entry["state"] = "held"
            elif entry.get("state") == "held" and not held:
                entry["state"] = "queued"

    def _dispatch_next(self) -> None:
        """Start the next FIFO queue entry once the active slot is free (R5)."""
        with self._lock:
            if self._active_task_id is not None or self._call_ended:
                return
            entry = next((q for q in self.state.queue if q.get("state") == "queued"), None)
            if entry is None:
                return
            task = self._new_task(
                text=str(entry["text"]),
                file_path=str(entry.get("file_path") or ""),
                mode=str(entry.get("mode") or "ask"),
                client_request_id=str(entry.get("client_request_id") or ""),
                queue_id=str(entry["queue_id"]),
            )
            entry["state"] = "dispatched"
            entry["task_id"] = task.task_id
            self._save()
        self._launch(task.task_id)

    def _new_task(self, *, text: str, file_path: str, mode: str, client_request_id: str, queue_id: str | None) -> CodingTask:
        """Create a task and make it the active one. Caller holds the lock."""
        snapshot = create_context_snapshot(
            self.paths,
            self.state,
            ContextSnapshot(
                workspace_root=str(self.paths.root),
                file_path=file_path,
                selection_text="",
                document_version=0,
                dirty=False,
                instruction=text,
            ),
        )
        now = _now()
        task = CodingTask(
            task_id=_new_id("task"),
            voice_session_id=self.session.session_id,
            context_snapshot_id=snapshot.snapshot_id,
            state="submitted",
            created_at=now,
            updated_at=now,
            client_request_id=client_request_id,
            mode=mode,
            instruction=text,
            file_path=file_path,
        )
        self.state.coding_tasks[task.task_id] = task
        self._active_task_id = task.task_id
        self._event(task, "context.snapshot", {"snapshot_id": snapshot.snapshot_id, "file_path": file_path})
        if client_request_id:
            self._event(task, "transcript.final", {"client_request_id": client_request_id})
        if queue_id is not None:
            self._event(task, "queue.dispatched", {"queue_id": queue_id})
        key = self._dedupe_key(client_request_id)
        if client_request_id:
            self.state.dedupe[key] = {"task_id": task.task_id, "queue_id": queue_id}
        return task

    def _dedupe_key(self, client_request_id: str) -> str:
        return f"{self.session.session_id}|{client_request_id}"

    def _enqueue(self, *, text: str, file_path: str, mode: str, client_request_id: str) -> dict[str, Any]:
        """Append a FIFO entry (R5). Caller holds the lock. Raises when the queue is full."""
        depth = sum(1 for q in self.state.queue if q.get("state") in ("queued", "held"))
        if depth >= self.config.queue_depth:
            raise DelegationError("queue_full", "the follow-up queue is full")
        entry = {
            "queue_id": _new_id("q"),
            "session_id": self.session.session_id,
            "task_id": None,
            "text": text,
            "state": "held" if self._pending_approval is not None else "queued",
            "file_path": file_path,
            "mode": mode,
            "client_request_id": client_request_id,
        }
        self.state.queue.append(entry)
        return entry

    def _require_active_session(self) -> None:
        if self.session.state != "active" or self._call_ended:
            raise DelegationError("session_not_active", "the voice session has ended")

    # -- bounded delegation surface (T006, R18) ----------------------------

    def submit(
        self,
        instruction: str,
        *,
        mode: str = "ask",
        file_path: str = "",
        client_request_id: str = "",
    ) -> dict[str, Any]:
        """`submit_coding_task`. The only call that issues a task_id (R18)."""
        with self._lock:
            self._require_active_session()
            if not str(client_request_id or "").strip():
                raise DelegationError("missing_client_request_id", "submit requires client_request_id")
            if mode == "agent":
                raise DelegationError("agent_mode_disabled", "agent mode is disabled until G6 closes")
            if mode not in ALLOWED_MODES:
                raise DelegationError("invalid_mode", f"mode must be one of {', '.join(ALLOWED_MODES)}")
            key = self._dedupe_key(client_request_id)
            if key in self.state.dedupe:
                return self._dedupe_result(key)
            text = self._validate_instruction(instruction)
            rel = self._resolve_file(file_path)
            if self._active_task_id is not None:
                entry = self._enqueue(
                    text=text, file_path=rel, mode=mode, client_request_id=client_request_id,
                )
                self.state.dedupe[key] = {"task_id": None, "queue_id": entry["queue_id"]}
                self._refresh_queue_holds()
                self._save()
                return {
                    "status": "queued", "task_id": None, "queue_id": entry["queue_id"],
                    "state": entry["state"], "spoken": "Queued behind the active task.",
                }
            task = self._new_task(
                text=text, file_path=rel, mode=mode, client_request_id=client_request_id, queue_id=None,
            )
            self._save()
            task_id = task.task_id
        self._launch(task_id)
        with self._lock:
            task = self.state.coding_tasks[task_id]
            return {
                "status": task.state, "task_id": task_id, "state": task.state,
                "spoken": task.evidence.spoken_update,
            }

    def _dedupe_result(self, key: str) -> dict[str, Any]:
        ref = self.state.dedupe[key]
        if ref.get("task_id"):
            task = self.state.coding_tasks[str(ref["task_id"])]
            return {"status": "duplicate", "task_id": task.task_id, "state": task.state, "spoken": ""}
        queue_id = ref.get("queue_id")
        entry = next((q for q in self.state.queue if q.get("queue_id") == queue_id), None)
        return {
            "status": "duplicate", "task_id": None, "queue_id": queue_id,
            "state": entry.get("state") if entry else None, "spoken": "",
        }

    def task_status(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            task = self._get_task(task_id)
            payload: dict[str, Any] = {
                "task_id": task.task_id,
                "state": task.state,
                "reason": task.reason,
                "transitions": list(task.transitions),
                "approval": task.approval,
            }
            if task.state in TERMINAL_TASK_STATES:
                payload["tests_status"] = task.evidence.tests_status
            return payload

    def task_diff(self, task_id: str) -> dict[str, Any]:
        """Read-only tasks record no diff evidence. Diffs arrive with G6 (edits)."""
        with self._lock:
            self._get_task(task_id)
            text, truncated = cap_text("", self.config.diff_max_bytes)
            return {"task_id": task_id, "diff": text, "truncated": truncated, "source": "no_diff_evidence"}

    def written_result(self, task_id: str) -> str:
        with self._lock:
            return self._get_task(task_id).evidence.written_result

    def queue_follow_up(self, text: str, *, task_id: str) -> dict[str, Any]:
        """`queue_follow_up`: binds the active task (R18) and queues FIFO (R5)."""
        with self._lock:
            self._require_active_session()
            if self._active_task_id is None:
                raise DelegationError("no_active_task", "no active task to follow up on")
            if task_id != self._active_task_id:
                raise DelegationError("task_mismatch", "follow-up is bound to a different task")
            active = self._get_task(task_id)
            clean = self._validate_instruction(text)
            entry = self._enqueue(
                text=clean, file_path=active.file_path, mode=active.mode, client_request_id="",
            )
            self._refresh_queue_holds()
            self._save()
            return {"status": "queued", "queue_id": entry["queue_id"], "task_id": None, "state": entry["state"]}

    def cancel(self, task_id: str) -> dict[str, Any]:
        """`cancel_coding_task`. Requested and acknowledged are separate records (R7, SC-011)."""
        with self._lock:
            task = self._get_task(task_id)
            if task.state in TERMINAL_TASK_STATES:
                raise DelegationError("task_already_terminal", f"task is {task.state}")
            if task.state == "cancel_requested":
                return {"task_id": task_id, "state": "cancel_requested", "spoken": "", "rollback": "not_performed"}
            pend = self._pending_approval
            if pend is not None and pend["task_id"] == task_id:
                self._resolve_approval(pend, "timed_out", {"outcome": {"outcome": "cancelled"}}, "task_cancelled")
            was_running = task.state in ("running", "awaiting_approval")
            client = self._client
            connected = client is not None and client.is_connected()
            if task.state == "unknown" or (not connected and task.state != "submitted"):
                # No live provider can acknowledge the cancel, so it is recorded as not acknowledged.
                self._transition(task, "cancel_requested", "user_cancel")
                self._transition(task, "failed", "cancel_not_acknowledged")
                self._settle(task)
                self._save()
                return {"task_id": task_id, "state": "failed", "spoken": "", "rollback": "not_performed"}
            self._transition(task, "cancel_requested", "user_cancel")
            if was_running and client is not None:
                try:
                    client.notify("session/cancel", {"sessionId": self._acp_session_id})
                except AcpDisconnected:
                    pass
            self._save()
            return {"task_id": task_id, "state": "cancel_requested", "spoken": "", "rollback": "not_performed"}

    # -- playback, call end (T010) -----------------------------------------

    def interrupt_playback(self) -> dict[str, Any]:
        """Stop talking. Records an event; changes no task state (R7, SC-003)."""
        with self._lock:
            task = self._active_task()
            before = task.state if task else None
            if task is not None:
                self._event(task, "speech.interrupted", {})
                self._save()
            after = task.state if task else None
            return {
                "event": "speech.interrupted",
                "task_state_before": before,
                "task_state_after": after,
                "state_changed": before != after,
            }

    def end_call(self) -> dict[str, Any]:
        """End the voice session. Tasks continue (R1, R25); queued follow-ups are discarded (R5, R26)."""
        with self._lock:
            discarded = 0
            for entry in self.state.queue:
                if entry.get("state") in ("queued", "held"):
                    entry["state"] = "discarded"
                    discarded += 1
            self._call_ended = True
            self.session.state = "ended"
            self.session.ended_at = _now()
            task = self._active_task()
            self._save()
            return {
                "session_ended": True,
                "discarded": discarded,
                "active_task_id": task.task_id if task else None,
                "active_task_state": task.state if task else None,
                "pending_approval": self._pending_approval["request_id"] if self._pending_approval else None,
                "rollback": "not_performed",
            }

    def close(self) -> None:
        """Close the provider session and stop provider-lost timers."""
        with self._lock:
            for timer in self._provider_lost_timers.values():
                timer.cancel()
            client = self._client
            self._client = None
        if client is not None:
            client.close()

    # -- synchronous convenience for CLI and tests -------------------------

    def wait_idle(self, timeout: float = 60.0) -> bool:
        """Block until no task is active (or timeout). Used by the CLI and tests."""
        deadline = self._clock() + timeout
        while self._clock() < deadline:
            with self._lock:
                if self._active_task_id is None:
                    return True
            time.sleep(0.02)
        return False
