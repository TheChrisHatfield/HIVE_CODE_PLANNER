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

import difflib
import json
import os
import queue
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
from hive_planner.voice_lock import RunnerLock
from hive_planner.voice_stt import FasterWhisperAdapter, SttError, resolve_pinned_model_dir
from hive_planner.voice_bot import (
    CODING_TASK_STATES,
    TERMINAL_TASK_STATES,
    VOICE_BOT_DIR,
    VOICE_CONTROLLER_TOOLS,
    CodingTask,
    ContextSnapshot,
    TestsStatus,
    VoiceBotConfig,
    VoiceBotError,
    VoiceBotState,
    VoiceSession,
    _FS_READ_METHODS,
    _FS_WRITE_METHODS,
    _read_workspace_text,
    buffers_match,
    create_context_snapshot,
    edits_enabled,
    event_delta_ms,
    is_planning_question,
    rss_meets_target,
    latency_meets_target,
    load_state,
    load_voice_bot_config,
    map_editor_snapshot,
    resolve_cartridge_trace,
    save_state,
    same_workspace,
    answer_planning_question,
    TypedInstructionAdapter,
    speech_adapter,
)
from hive_planner.voice_moshi import MOSHI_SPOKEN, moshi_listen_gate

ALLOWED_MODES: tuple[str, ...] = ("ask", "plan", "agent")  # `agent` needs the R33 latch (R6)
APPROVAL_KINDS: tuple[str, ...] = ("write_or_command", "plan", "question")
# U6: ACP tool kinds that change files. Each completed or started call counts as one write.
WRITE_TOOL_KINDS: frozenset[str] = frozenset({"edit", "delete", "move", "write"})
# U10: an `execute` call is a write only when its command text changes files. Test and lint runs
# stay reads, so this matches on the command, not on the tool kind alone.
WRITE_COMMAND_RE = re.compile(
    r"(?<!&)>{1,2}(?!&)|\btee\b|\bsed\s+-i\b"
    r"|\b(mv|cp|rm|mkdir|del|move|copy|ren|touch|truncate|chmod|chown|ln|dd)\b"
    r"|\b(Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|New-Item"
    r"|Rename-Item|Clear-Content|Set-Item|Expand-Archive)\b"
    # H1: interpreter one-liners that write files (python/node/etc.), not only shell redirects.
    # U12: modes `r+`/`rb+` (read-write) and `w+` (truncate-write) also write.
    r"|\bopen\s*\([^)]*['\"](?:[wax][bt]*\+?[bt]*|r[bt]*\+[bt]*)['\"]"
    r"|\.write_(?:text|bytes)\s*\(|\bwriteFile(?:Sync)?\s*\("
    r"|\bWriteAll(?:Text|Bytes|Lines)\b|\bAppendAll(?:Text|Lines)\b"
    r"|\bshutil\.(?:copy\w*|move|rmtree)\b|\bos\.(?:remove|unlink|rename|replace|makedirs|mkdir|rmdir)\b"
    r"|\bfs\.(?:writeFile|appendFile|rm|unlink|rename|mkdir)\w*\s*\("
    r"|\bgit\s+(checkout|restore|apply|reset|clean|rm|mv|stash)\b|\bpatch\s"
    # R22 review 2026-11-13: copy/download tools and in-place editors also write files.
    r"|\b(robocopy|xcopy|setx)\b|\bperl\s+-i\b|\bawk\s+-i\s+inplace\b"
    r"|\bcurl\b[^|;&]*\s-[oO]\b|\bwget\b[^|;&]*\s-O\b"
    r"|\bInvoke-(?:WebRequest|RestMethod)\b[^|;&]*-OutFile\b",
    re.IGNORECASE,
)

# Tool kinds that cannot write files. Any other kind (edit, execute, other, or a missing kind)
# is checked by command text, so an unlabelled shell call cannot skip the write count (fail closed).
READ_ONLY_TOOL_KINDS: frozenset[str] = frozenset({"read", "search", "fetch", "think", "switch_mode"})

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

# F3: tool-call evidence. Secrets are masked before truncation, so a cut cannot leave half a secret.
TOOL_COMMAND_MAX_CHARS = 200
_BEARER_RE = re.compile(r"(?i)\bbearer\s+\S+")
_SECRET_ARG_RE = re.compile(
    r"(?i)\b(token|password|passwd|secret|api[_-]?key|authorization|auth)(\s*[=:]\s*|\s+)(\"[^\"]*\"|'[^']*'|\S+)"
)
_SHORT_P_ARG_RE = re.compile(r"(?<![\w-])(-p)(\s+)(\"[^\"]*\"|'[^']*'|\S+)")
_SK_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}")


def _mask_secrets(text: str) -> str:
    text = _BEARER_RE.sub("Bearer <redacted>", text)
    text = _SECRET_ARG_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", text)
    # Short credential flag `-p <value>` (space form only). Lookbehind keeps `--p` and `foo-p` intact.
    text = _SHORT_P_ARG_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", text)
    return _SK_KEY_RE.sub("<redacted>", text)


def redact_raw_payload(value: Any) -> Any:
    """Mask credential-looking text in a raw provider payload before it is retained (R17).
    Keeps structure and length limits untouched so diagnosis still works."""
    if isinstance(value, str):
        return _mask_secrets(value)
    if isinstance(value, dict):
        return {k: redact_raw_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_raw_payload(v) for v in value]
    return value


def redact_command(command: str, limit: int = TOOL_COMMAND_MAX_CHARS) -> str:
    """F3: mask credential-looking arguments, then truncate. Never returns the raw secret."""
    text = _mask_secrets(str(command))
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text

# Words that turn an approve/deny reply into something other than a plain decision (R6).
NEGATION_RE = re.compile(r"\b(not|no|never|cancel|wait|stop|don't|dont|do not)\b")


class DelegationError(VoiceBotError):
    """A bounded delegation call was refused. `code` is the stable reason string."""

    def __init__(self, code: str, message: str = "", *, spoken: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.spoken = spoken


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _shorten(text: str, max_chars: int) -> str:
    """Shorten speech to the R14/R21 cap. Full text stays in written_result."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


APPROVAL_ACTION_MAX_CHARS = 120
DEFAULT_APPROVAL_ACTION = "perform the requested action"


def _safe_action_label(raw: Any) -> str:
    """Sanitize a provider tool title before it is spoken or stored as an approval action.

    Markdown emphasis and code marks are removed, control characters become spaces, runs of
    whitespace collapse, and the result is capped. The raw title stays in `task.events` and
    `raw_events` for diagnosis. Exact-match approval replies still use this label.
    """
    text = str(raw or "")
    for mark in ("`", "*", "<", ">"):
        text = text.replace(mark, "")
    text = "".join(ch if ch.isprintable() else " " for ch in text)
    text = " ".join(text.split())
    if not text:
        return DEFAULT_APPROVAL_ACTION
    return _shorten(text, APPROVAL_ACTION_MAX_CHARS)


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
RssReader = Callable[[], dict[str, float | None]]


def default_rss_mb() -> dict[str, float | None]:
    """Measured RSS in MB for the voice service (this process) and its descendants (agent children).

    A scope is ``None`` when it cannot be measured (psutil missing or the process is gone). R24:
    an unmeasured scope is not checked, so it is never reported as within budget.
    """
    unknown: dict[str, float | None] = {"voice_service": None, "agent_children": None}
    try:
        import psutil
    except ImportError:
        return unknown
    try:
        me = psutil.Process(os.getpid())
        service = me.memory_info().rss
        children = 0
        for child in me.children(recursive=True):
            try:
                children += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except psutil.Error:
        return unknown
    mb = 1048576
    return {"voice_service": service / mb, "agent_children": children / mb}


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
        rss_reader: RssReader | None = None,
    ) -> None:
        self.paths = paths
        self.feature = validate_feature_id(feature)
        # Cross-process lock, held until close(): no second process may load or write state
        # for this repo while this runner lives (bridge start race). Raises RunnerLockHeld.
        self._repo_lock = RunnerLock(paths)
        self._repo_lock.acquire()
        try:
            self._init_state(paths, agent_path, client_factory, request_timeout, clock, rss_reader)
        except BaseException:
            self._repo_lock.release()
            raise

    def _init_state(
        self,
        paths: RepoPaths,
        agent_path: str,
        client_factory: ClientFactory | None,
        request_timeout: float,
        clock: Callable[[], float],
        rss_reader: RssReader | None = None,
    ) -> None:
        self.config: VoiceBotConfig = load_voice_bot_config(paths)
        self.agent_path = agent_path
        self._client_factory: ClientFactory = client_factory or self._default_client_factory
        # R24 RSS reader: injectable so tests run without a live agent child.
        self._rss_reader: RssReader = rss_reader or default_rss_mb
        self._request_timeout = request_timeout
        self._clock = clock
        self._lock = threading.RLock()
        self._closed = False

        # Read only after the lock is held, so this is the state no other process can change.
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
        self._client_write_cap = False  # U11b: did the live child get clientCapabilities.fs.writeTextFile
        self._acp_session_id = ""
        self._mode_set = ""
        self._active_task_id: str | None = None
        self._pending_approval: dict[str, Any] | None = None
        self._pending_cmd: dict[str, str] = {}
        self._pending_kind: dict[str, str] = {}
        self._test_records: dict[str, list[dict[str, Any]]] = {}
        self._progress_last: dict[str, float] = {}
        self._provider_lost_timers: dict[str, threading.Timer] = {}
        self._call_ended = False
        self._live_buffer: Callable[[str], tuple[int, bool] | None] | None = None
        self._recover_after_hive_restart()

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
        if self._closed:
            return
        save_state(self.paths, self.state)

    def set_live_buffer(self, lookup: Callable[[str], tuple[int, bool] | None] | None) -> None:
        """Editor live version/dirty lookup for the R22 stale check (T014, T029).

        A lookup that returns None has no reading for that file, so the check is skipped for it.
        """
        self._live_buffer = lookup

    def live_buffer_lookup(self) -> Callable[[str], tuple[int, bool] | None] | None:
        return self._live_buffer

    def _live_buffer_at_reply(
        self,
        snap: ContextSnapshot,
        editor_snapshot: dict[str, Any] | None,
    ) -> tuple[int, bool]:
        """Live version/dirty at write-approval time (R22). Prefer the host snapshot."""
        if editor_snapshot is not None:
            return (
                int(editor_snapshot.get("document_version") or 0),
                bool(editor_snapshot.get("dirty")),
            )
        if self._live_buffer is not None:
            live = self._live_buffer(snap.file_path)
            if live is not None:
                return live
        return snap.document_version, snap.dirty

    @staticmethod
    def _live_file_mismatch(snap: ContextSnapshot, editor_snapshot: dict[str, Any] | None) -> bool:
        """True when the host named a different file than the bound snapshot (R22).

        Snapshots that omit `file` keep the version/dirty-only check (typed tests).
        A present `file` (including null) must match the snapshot path.
        """
        if editor_snapshot is None or "file" not in editor_snapshot:
            return False
        live = str(editor_snapshot.get("file") or "").replace("\\", "/").casefold()
        bound = str(snap.file_path or "").replace("\\", "/").casefold()
        return live != bound

    def _recover_after_hive_restart(self) -> None:
        """R26: in-flight tasks become unknown; pending approvals time out; queued entries discard."""
        changed = False
        for task in self.state.coding_tasks.values():
            if task.state == "unknown":
                # Left unknown by an earlier process: re-arm its provider_lost window (R26).
                if task.task_id not in self._provider_lost_timers:
                    self._settle(task)
                continue
            if task.state not in ("submitted", "running", "awaiting_approval", "cancel_requested"):
                continue
            task.prior_state = task.state
            if task.approval:
                timed = dict(task.approval)
                timed["status"] = "timed_out"
                task.approval = timed
                task.approvals.append(timed)
            self._transition(task, "unknown", "hive_restarted")
            self._settle(task)
            changed = True
        for entry in self.state.queue:
            if entry.get("state") in ("queued", "held"):
                entry["state"] = "discarded"
                changed = True
        self._active_task_id = None
        self._pending_approval = None
        if changed:
            self._save()

    def reconnect_task(self, task_id: str) -> dict[str, Any]:
        """R26: matching provider evidence restores the last non-unknown state. Approvals stay timed out.

        Evidence is a live ACP connection whose session id matches the task. A restart or a
        dead child is not evidence: restoring `running` with no prompt would occupy the
        active slot and block the queue until someone cancelled.
        """
        with self._lock:
            task = self._get_task(task_id)
            if task.state != "unknown":
                raise DelegationError("not_unknown", f"task is {task.state}")
            client = self._client
            live = client is not None and client.is_connected()
            session_ok = bool(self._acp_session_id) and (
                not task.provider_session_id or task.provider_session_id == self._acp_session_id
            )
            if not live or not session_ok:
                raise DelegationError(
                    "no_provider_evidence",
                    "reconnect requires a live provider session that matches this task",
                )
            prior = task.prior_state or "running"
            if prior == "awaiting_approval":
                prior = "running"
            if prior not in TERMINAL_TASK_STATES and self._active_task_id not in (None, task.task_id):
                raise DelegationError(
                    "task_slot_occupied",
                    "reconnect refused because another task is already active",
                )
            timer = self._provider_lost_timers.pop(task_id, None)
            if timer is not None:
                timer.cancel()
            self._transition(task, prior, "provider_reconnect")
            if prior not in TERMINAL_TASK_STATES:
                self._active_task_id = task.task_id
            self._save()
            return {"task_id": task_id, "state": task.state, "approval": task.approval}

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
        if name in ("task.started", "speech.spoken"):
            self._check_r24_budget(task, name)
        if name == "task.started":
            self._check_r24_rss(task)

    def _check_r24_rss(self, task: CodingTask) -> None:
        """R24/AC20 runtime check: measured RSS against the config targets, at task start.

        Logs ``r24.over_budget`` with ``kind=rss`` and a ``scope`` (``agent_children`` or
        ``voice_service``). Each scope is logged at most once per task. A missing target or an
        unmeasured scope is not checked.
        """
        targets = {
            "agent_children": self.config.agent_children_rss_target_mb,
            "voice_service": self.config.voice_service_rss_target_mb,
        }
        if all(target is None for target in targets.values()):
            return
        measured = self._rss_reader()
        for scope, target in targets.items():
            mb = measured.get(scope)
            if target is None or mb is None or rss_meets_target(mb, target):
                continue
            if any(
                e.get("name") == "r24.over_budget"
                and e.get("payload", {}).get("kind") == "rss"
                and e.get("payload", {}).get("scope") == scope
                for e in task.events
            ):
                continue
            task.events.append({
                "name": "r24.over_budget",
                "at": _now(),
                "payload": {"kind": "rss", "scope": scope, "measured_mb": round(mb, 1), "target_mb": target},
            })

    def _check_r24_budget(self, task: CodingTask, name: str) -> None:
        """R24 runtime check: compare a measured latency with the config target and log a miss.

        Latency is only known after the event happens, so an over-budget result is recorded as
        ``r24.over_budget`` (never silently ignored). A missing target is not checked (R24).
        Each budget kind is logged at most once per task.
        """
        if name == "task.started":
            kind, target = "task_started", self.config.latency_target_ms
            elapsed = event_delta_ms(task.events, "transcript.final", "task.started")
        else:
            # Only the first spoken update of a task counts toward the first-speech budget.
            if sum(1 for e in task.events if e.get("name") == "speech.spoken") != 1:
                return
            kind, target = "first_speech", self.config.first_spoken_update_target_ms
            elapsed = event_delta_ms(task.events, "transcript.final", "speech.spoken")
        if elapsed is None or latency_meets_target(elapsed, target):
            return
        if any(e.get("name") == "r24.over_budget" and e.get("payload", {}).get("kind") == kind for e in task.events):
            return
        task.events.append({
            "name": "r24.over_budget",
            "at": _now(),
            "payload": {"kind": kind, "elapsed_ms": elapsed, "target_ms": target},
        })

    @staticmethod
    def _correlation_ids(task: CodingTask) -> dict[str, str]:
        """R9: ids that let a disconnect/timeout event be joined to its task and provider session."""
        return {
            "task_id": task.task_id,
            "voice_session_id": task.voice_session_id,
            "provider_session_id": task.provider_session_id,
        }

    def _transition(self, task: CodingTask, to: str, reason: str, extra: dict[str, Any] | None = None) -> None:
        if to not in CODING_TASK_STATES or to not in TRANSITIONS.get(task.state, frozenset()):
            raise DelegationError("illegal_transition", f"{task.state} -> {to} ({reason})")
        if to == "unknown" and task.state != "unknown":
            # R26: remember the last non-unknown state on every path into unknown
            # (provider disconnect as well as HIVE restart), so reconnect restores it.
            task.prior_state = task.state
        task.transitions.append({"from": task.state, "to": to, "reason": reason, "at": _now()})
        task.state = to
        task.reason = reason
        task.updated_at = _now()
        self._event(task, "task.cancelled" if to == "cancelled" else f"task.{to}", {"reason": reason, **(extra or {})})

    def _say(self, task: CodingTask, text: str, record: bool = True) -> bool:
        """Speak an update and log it. Returns False (and records nothing) after the call ends (R25).

        ``record=False`` is for progress speech: it is spoken and logged as ``speech.spoken`` but
        does not overwrite ``evidence.spoken_update``, so the acceptance ack and outcome stay as
        the recorded spoken result (spec §Speech, SC-010).
        """
        if self._call_ended:
            return False
        spoken = _shorten(text, self.config.spoken_update_max_chars)
        if record:
            task.evidence.spoken_update = spoken
        # T042 slice 4: config audio_enabled picks the adapter. Any adapter failure falls back to
        # the typed no-audio path so the update is still recorded.
        try:
            playback = speech_adapter(self.config).speak(spoken)
        except VoiceBotError:
            playback = TypedInstructionAdapter().speak(spoken)
        self._event(
            task,
            "speech.spoken",
            {"text": spoken, "audio": bool(playback.get("audio")), "path": playback.get("path", "typed")},
        )
        return True

    def _resolve_wav_input(self, wav_path: str) -> str:
        """Workspace-relative WAV for a spoken input. Only the launcher's recordings folder is allowed.

        `.hive/` stays refused by `_resolve_file` (it holds the bridge token). The one exception is a
        `.wav` directly inside `.hive/voice-bot/recordings/`, which the mic route writes and which
        holds audio only. Traversal and other `.hive` paths are still refused.
        """
        text = str(wav_path or "").replace("\\", "/")
        if text.lower().endswith(".wav") and not Path(text).is_absolute():
            recordings = self.paths.root / ".hive" / "voice-bot" / "recordings"
            if "\x00" not in text and Path(text).parent.as_posix().casefold() == ".hive/voice-bot/recordings":
                target = (self.paths.root / text).resolve()
                try:
                    inside = target.parent == recordings.resolve()
                except OSError:
                    inside = False
                if inside and target.is_file():
                    return target.relative_to(self.paths.root.resolve()).as_posix()
        return self._resolve_file(wav_path)

    def _resolve_file(self, file_path: str) -> str:
        """R23 path validation: the file must resolve inside the bound workspace."""
        if not file_path:
            return ""
        # NUL is never part of a path. On Windows resolve() truncates at the NUL, so
        # "src/app.py\x00.txt" would silently validate and bind as "src/app.py". Refuse it first.
        if "\x00" in file_path:
            raise DelegationError("bad_path", "path contains a NUL byte")
        root = self.paths.root.resolve()
        try:
            target = (root / file_path).resolve()
        except (OSError, ValueError) as exc:
            raise DelegationError("bad_path", f"{file_path!r} is not a usable path") from exc
        try:
            rel = target.relative_to(root)
        except ValueError as exc:
            raise DelegationError("path_outside_workspace", f"{file_path} is outside the workspace") from exc
        # Same R23 fence as ACP fs/read and fs/write: `.hive/` holds the bridge token and latch.
        if not rel.parts or rel.parts[0].casefold() == ".hive":
            raise DelegationError(
                "path_protected",
                f"{rel.as_posix()} is a HIVE internal path",
                spoken="That file is reserved. Nothing was submitted.",
            )
        if not target.is_file():
            raise DelegationError("file_not_found", f"{rel.as_posix()} does not exist")
        return rel.as_posix()

    def _validate_instruction(self, text: str) -> str:
        stripped = (text or "").strip()
        if not stripped:
            raise DelegationError("instruction_required", "instruction is empty")
        if len(text) > self.config.instruction_max_chars:
            raise DelegationError(
                "instruction_too_long",
                "instruction exceeds the configured limit",
                spoken="That instruction is too long. Nothing was submitted.",
            )
        return stripped

    def _prompt_text(self, task: CodingTask) -> str:
        if task.mode == "agent":
            # R33: agent mode is only reachable when the edits latch is on, so the
            # prompt must not contradict it with a blanket read-only line.
            parts = [f"Mode: {task.mode}. Edits are permitted as the instruction below directs."]
        else:
            parts = [f"Mode: {task.mode}. Read-only request; do not modify files."]
        if task.file_path:
            parts.append(f"Active file: {task.file_path}.")
        snap = self.state.context_snapshots.get(task.context_snapshot_id)
        if snap is not None and not snap.excluded:
            if snap.selection_text:
                parts.append("Selected code:\n" + snap.selection_text)
            if snap.file_content:
                parts.append("File content:\n" + snap.file_content)
        if snap is not None and snap.cartridge_trace is not None:
            trace = snap.cartridge_trace
            if trace.cartridge_id:
                parts.append(f"Cartridge id: {trace.cartridge_id}.")
            if trace.source_excerpt_ids:
                parts.append("Source excerpts: " + ", ".join(trace.source_excerpt_ids) + ".")
        parts.append(task.instruction)
        return "\n".join(parts)

    def _default_client_factory(self, handler: Callable[[str, Any], Any]) -> AcpClient:
        return open_agent_acp(self.agent_path, cwd=str(self.paths.root), server_request_handler=handler)

    # -- ACP session (blocking; never called under the lock) ---------------

    def _ensure_session(self, mode: str) -> None:
        # U11b: only agent mode with the R33 latch advertises writes; the broker gates each one.
        want_write = mode == "agent" and edits_enabled(self.paths)
        replaced: AcpClient | None = None
        with self._lock:
            if self._closed:
                raise VoiceBotError("session_not_active")
            client = self._client if (self._client is not None and self._client.is_connected()) else None
            if client is not None and want_write and not self._client_write_cap:
                # A live child initialized without writeTextFile would self-write in agent mode.
                replaced, client = client, None
                self._client = None
                self._acp_session_id = ""
                self._mode_set = ""
                self._client_write_cap = False
        if replaced is not None:
            try:
                replaced.terminate()
                replaced.close()
            except (AcpError, OSError):
                pass
        if client is None:
            client = self._client_factory(self._handle_server_request)
            try:
                client.request(
                    "initialize",
                    {
                        "protocolVersion": 1,
                        "clientCapabilities": {
                            "fs": {"readTextFile": True, "writeTextFile": want_write},
                        },
                    },
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
            # close() during handshake sees _client is None and cannot kill this child (R9).
            with self._lock:
                keep = not self._closed
                if keep:
                    self._client = client
                    self._client_write_cap = want_write
                    self._acp_session_id = str(session_id)
                    self._mode_set = ""
            if not keep:
                try:
                    client.terminate()
                    client.close()
                except (AcpError, OSError):
                    pass
                raise VoiceBotError("session_not_active")
            threading.Thread(target=self._pump, args=(client,), name="voice-pump", daemon=True).start()
        if self._mode_set != mode:
            # Fail closed: if the provider will not confirm the mode, no prompt is sent.
            client.request(
                "session/set_mode", {"sessionId": self._acp_session_id, "modeId": mode},
                timeout=self._request_timeout,
            )
            with self._lock:
                if self._closed:
                    raise VoiceBotError("session_not_active")
                self._mode_set = mode

    def _pump(self, client: AcpClient) -> None:
        """Route session/update notifications into the active task, in arrival order."""
        while True:
            item = client.notifications.get()
            if item is None:
                break
            self._apply_notification(item)

    def _apply_notification(self, item: dict[str, Any]) -> None:
        marker = item.get("_marker")
        if marker is not None:
            marker.set()
            return
        if item.get("method") != "session/update":
            return
        params = item.get("params")
        if not isinstance(params, dict):
            return
        with self._lock:
            if self._closed:
                return
            try:
                self._on_update(params)
            except Exception as exc:
                # Fail closed: an update that could not be recorded may have hidden a write (R22).
                self._note_update_error(exc)

    def _note_update_error(self, exc: Exception) -> None:
        """Record that an ACP update was dropped, so `_finish` cannot report success on it."""
        task = self._active_task()
        if task is not None:
            self._event(task, "update.error", {"error": type(exc).__name__})

    @staticmethod
    def _has_update_error(task: CodingTask) -> bool:
        return any(e.get("name") == "update.error" for e in task.events)

    def _drain(self, client: AcpClient) -> None:
        """Wait until the pump has processed every notification received so far.

        After a disconnect the pump exits on the EOF sentinel and never sees a later
        marker, so leftovers (including writes queued just before the crash) are applied
        here. R22 needs those writes before `_finish` runs.
        """
        marker = threading.Event()
        client.notifications.put({"_marker": marker})  # type: ignore[arg-type]
        wait_s = 2.0 if client.is_connected() else 0.5
        if marker.wait(timeout=wait_s):
            return
        leftover: list[dict[str, Any] | None] = []
        while True:
            try:
                leftover.append(client.notifications.get_nowait())
            except queue.Empty:
                break
        for item in leftover:
            if item is None:
                continue
            self._apply_notification(item)

    # -- server requests from the agent (reader thread) --------------------

    def _handle_server_request(self, method: str, params: Any) -> Any:
        if method == "session/request_permission":
            return self._on_permission(params if isinstance(params, dict) else {})
        # ACP client fs/read (G2 live_prompt). Not an R18 voice-layer tool. Writes stay errors (T027).
        if method in _FS_READ_METHODS:
            return _read_workspace_text(self.paths.root, params, self.config.snapshot_max_bytes)
        if method in _FS_WRITE_METHODS:
            return self._on_fs_write(params)
        raise VoiceBotError(f"unsupported client method {method}")

    def _resolve_write_target(self, params: Any) -> tuple[str, Path]:
        """R23: a write target must resolve inside the workspace and outside `.hive/`.

        `.hive/` holds the bridge token and the config latch, so no provider write may reach it.
        Nothing touches disk here; the same check runs again right before the bytes are written.
        """
        if not isinstance(params, dict):
            raise VoiceBotError("fs_write_invalid")
        raw = str(params.get("path") or "")
        if not raw:
            raise VoiceBotError("fs_write_missing_path")
        if "\x00" in raw:
            # resolve() truncates at NUL on Windows; refuse before the path is interpreted.
            raise VoiceBotError("fs_write_outside_workspace")
        if not isinstance(params.get("content"), str):
            raise VoiceBotError("fs_write_missing_content")
        root = self.paths.root.resolve()
        path = Path(raw)
        try:
            resolved = (path if path.is_absolute() else root / path).resolve()
            rel = resolved.relative_to(root)
        except (OSError, ValueError):
            raise VoiceBotError("fs_write_outside_workspace") from None
        if not rel.parts or rel.parts[0].casefold() == ".hive":
            raise VoiceBotError("fs_write_protected")
        if resolved.is_dir():
            raise VoiceBotError("fs_write_is_directory")
        return rel.as_posix(), resolved

    def _on_fs_write(self, params: Any) -> Any:
        """U11b: a provider `fs/write_text_file` goes through the same approval broker as a
        permission request. The bytes are written only after an allow (see `_apply_fs_write`)."""
        rel, _target = self._resolve_write_target(params)
        label = re.sub(r"[-_.]+", " ", Path(rel).stem).strip() or "file"
        call_id = _new_id("fsw")
        fs_write = {"rel": rel, "content": params["content"], "call_id": call_id}
        opened = self._open_approval(
            {
                "kind": "write_or_command",
                "toolCall": {"toolCallId": call_id, "title": f"edit {label}", "kind": "edit"},
                "options": [
                    {"optionId": "allow-once", "name": "Allow", "kind": "allow_once"},
                    {"optionId": "reject-once", "name": "Reject", "kind": "reject_once"},
                ],
            },
            fs_write=fs_write,
        )
        if not opened:
            raise VoiceBotError("fs_write_refused")
        return DEFER

    def _apply_fs_write(self, task: CodingTask, fs_write: dict[str, Any]) -> None:
        """Write the approved bytes. Re-runs the R23 check because the approval wait is open."""
        rel, target = self._resolve_write_target({"path": fs_write["rel"], "content": fs_write["content"]})
        try:
            old_text = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
            payload = fs_write["content"].encode("utf-8")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        except (OSError, TypeError, UnicodeError) as exc:
            raise VoiceBotError("fs_write_failed") from exc
        self._record_write_event(task, fs_write.get("call_id") or _new_id("fsw"))
        task.evidence.write_diffs.append({"path": rel, "old_text": old_text, "new_text": fs_write["content"]})

    def _on_update(self, params: dict[str, Any]) -> None:
        if str(params.get("sessionId") or "") != self._acp_session_id:
            return
        task = self._active_task()
        if task is None:
            return
        task.raw_events.append(redact_raw_payload(params))
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
            tool_kind, command = self._remember_tool_fields(call_id, update)
            if self._is_write_call(tool_kind, command):
                self._record_write_event(task, call_id)
            self._record_tool_call(task, call_id, tool_kind, command)
            self._event(task, "task.progress", {"tool": str(update.get("title") or "")})
        elif kind == "tool_call_update":
            call_id = str(update.get("toolCallId") or "")
            self._set_tool_call_status(task, call_id, update.get("status"))
            tool_kind, pending = self._remember_tool_fields(call_id, update)
            self._record_tool_call(task, call_id, tool_kind, pending)
            if self._is_write_call(tool_kind, pending) or self._has_diff_content(update.get("content")):
                self._record_write_event(task, call_id)
            if update.get("status") == "completed":
                self._record_write_diffs(task, update.get("content"))
            status = update.get("status")
            if status in ("completed", "failed"):
                command = self._pending_cmd.pop(call_id, None)
                self._pending_kind.pop(call_id, None)
                if command and TEST_COMMAND_RE.search(command):
                    raw_output = update.get("rawOutput") or {}
                    code = raw_output.get("exitCode") if isinstance(raw_output, dict) else None
                    self._test_records.setdefault(task.task_id, []).append(
                        {"command": command, "exit_code": code if isinstance(code, int) else None}
                    )

    def _remember_tool_fields(self, call_id: str, update: dict[str, Any]) -> tuple[Any, Any]:
        """Merge kind/command from this update with fields already seen for the call id.

        An empty toolCallId still uses this update's kind/command so a write is not dropped.
        """
        raw_input = update.get("rawInput") or {}
        command = raw_input.get("command") if isinstance(raw_input, dict) else None
        kind = update.get("kind")
        merged_kind = self._pending_kind.get(call_id) if call_id else None
        merged_cmd = self._pending_cmd.get(call_id) if call_id else None
        if kind:
            merged_kind = str(kind)
            if call_id:
                self._pending_kind[call_id] = merged_kind
        if command:
            merged_cmd = str(command)
            if call_id:
                self._pending_cmd[call_id] = merged_cmd
        return merged_kind, merged_cmd

    @staticmethod
    def _record_tool_call(task: CodingTask, call_id: str, kind: Any, command: Any) -> None:
        """F3: one evidence row per tool call id. The command is redacted and truncated here."""
        if not call_id:
            return
        for row in task.evidence.tool_calls:
            if row.get("tool_call_id") != call_id:
                continue
            if kind and not row.get("kind"):
                row["kind"] = str(kind).lower()
            if command and not row.get("command"):
                row["command"] = redact_command(str(command))
            return
        task.evidence.tool_calls.append({
            "tool_call_id": call_id,
            "kind": str(kind or "").lower(),
            "command": redact_command(str(command)) if command else "",
            "status": "pending",
        })

    @staticmethod
    def _set_tool_call_status(task: CodingTask, call_id: str, status: Any) -> None:
        if not call_id or status not in ("completed", "failed"):
            return
        for row in task.evidence.tool_calls:
            if row.get("tool_call_id") == call_id:
                row["status"] = str(status)

    @staticmethod
    def _is_write_call(kind: Any, command: Any) -> bool:
        """U6/U10: a file-changing tool kind, or an `execute` call whose command writes files."""
        tool_kind = str(kind or "").lower()
        if tool_kind in WRITE_TOOL_KINDS:
            return True
        if tool_kind in READ_ONLY_TOOL_KINDS:
            return False
        return bool(command) and WRITE_COMMAND_RE.search(str(command)) is not None

    @staticmethod
    def _record_write_event(task: CodingTask, call_id: str) -> None:
        """U6: count one write per tool call id. Writes with no diff content still count.

        A write with no tool call id cannot be deduplicated, so each one counts separately
        (fail closed): two anonymous writes need two approvals (R22).
        """
        key = call_id or _new_id("anon")
        if call_id and key in task.evidence.write_events:
            return
        task.evidence.write_events.append(key)

    @staticmethod
    def _has_diff_content(content: Any) -> bool:
        return isinstance(content, list) and any(
            isinstance(item, dict) and item.get("type") == "diff" for item in content
        )

    @staticmethod
    def _has_unguarded_write(task: CodingTask) -> bool:
        """R22: True when the task has more writes than approved write permissions.

        Every write must pass through `session/request_permission`, which lands in
        `task.approvals` as a `write_or_command` record. Each approved record covers one write
        only: a turn with two writes and one approval is unguarded. Denied, timed-out, or stale
        approvals cover nothing. Writes are counted from `write_events` (tool calls), so a write
        with no diff content still counts.
        """
        # Matching is by tool call id (ACP `toolCall.toolCallId` on the permission request). An
        # approval covers only the write event with the same id, so an approved edit for one
        # tool call does not guard a different write. An approved `execute` (for example
        # `npm test`) guards only its own call id. Anonymous writes never match (fail closed).
        approved_ids = {
            a.get("tool_call_id")
            for a in task.approvals
            if a.get("kind") == "write_or_command"
            and a.get("status") == "approved"
            and a.get("tool_call_id")
        }
        return any(write not in approved_ids for write in task.evidence.write_events)

    @staticmethod
    def _record_write_diffs(task: CodingTask, content: Any) -> None:
        """T032: keep ACP `diff` content items as write evidence for `task_diff`."""
        if not isinstance(content, list):
            return
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "diff":
                continue
            task.evidence.write_diffs.append({
                "path": str(item.get("path") or ""),
                "old_text": str(item.get("oldText") or ""),
                "new_text": str(item.get("newText") or ""),
            })

    def _maybe_progress_speech(self, task: CodingTask) -> None:
        now = self._clock()
        last = self._progress_last.get(task.task_id)
        if last is None or now - last >= self.config.progress_interval_s:
            if self._say(task, "Still working.", record=False):
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
        if self._open_approval(params):
            return DEFER
        return {"outcome": {"outcome": "cancelled"}}

    def _open_approval(self, params: dict[str, Any], fs_write: dict[str, Any] | None = None) -> bool:
        """Open one pending approval. False means refused: nothing may execute.

        `fs_write` marks a provider file write (U11b): its bytes wait in the pending approval
        and are written by `_resolve_approval` only on an allow.
        """
        with self._lock:
            task = self._active_task()
            client = self._client
            if task is None or client is None:
                return False  # no active task: nothing may execute
            if self._pending_approval is not None:
                self._event(task, "approval.refused", {"reason": "approval_already_pending"})
                return False
            if task.state != "running":
                # Only a running task may open an approval. A cancelling or unstarted task
                # cannot take the R20 awaiting_approval edge, so refuse before any pending
                # state exists; otherwise the approval would strand with no timer (R6, R7).
                self._event(task, "approval.refused", {"reason": f"task_{task.state}"})
                return False
            tool = params.get("toolCall") or {}
            action = _safe_action_label(tool.get("title") if isinstance(tool, dict) else None)
            tool_kind = str(tool.get("kind") or "").lower() if isinstance(tool, dict) else ""
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
                "tool_kind": tool_kind,
                "tool_call_id": str(tool.get("toolCallId") or "") if isinstance(tool, dict) else "",
                "action": action,
                "options": options if isinstance(options, list) else [],
                "timer": timer,
                "fs_write": fs_write,
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
            return True

    def _resolve_approval(self, pend: dict[str, Any], status: str, reply: dict[str, Any], detail: str) -> str:
        """Close the pending approval with a recorded status. Caller holds the lock.

        Returns the final status. A file write that fails after an allow is recorded as denied,
        so a failed write is never reported as approved.
        """
        pend["timer"].cancel()
        self._pending_approval = None
        task = self.state.coding_tasks[pend["task_id"]]
        fs_write = pend.get("fs_write")
        if fs_write is not None and status == "approved":
            try:
                self._apply_fs_write(task, fs_write)
            except (VoiceBotError, OSError, TypeError, UnicodeError) as exc:
                status, detail = "denied", str(exc)
        record = {
            "request_id": pend["request_id"],
            "kind": pend["kind"],
            "tool_kind": pend.get("tool_kind", ""),
            "tool_call_id": pend.get("tool_call_id", ""),
            "action": pend["action"],
            "status": status,
            "detail": detail,
            "at": _now(),
        }
        task.approvals.append(record)
        task.approval = record
        self._event(task, "approval.resolved", {"status": status, "kind": pend["kind"]})
        try:
            if fs_write is None:
                pend["client"].reply(pend["server_request_id"], reply)
            elif status == "approved":
                pend["client"].reply(pend["server_request_id"], {})
            else:
                pend["client"].reply_error(pend["server_request_id"], -32000, f"write not applied: {detail}")
        except AcpDisconnected:
            pass  # provider already gone; nothing can execute either way
        if task.state == "awaiting_approval":
            self._transition(task, "running", f"approval_{status}")
        self._refresh_queue_holds()
        self._save()
        return status

    def _on_approval_timeout(self, request_id: str) -> None:
        with self._lock:
            if self._closed:
                return
            pend = self._pending_approval
            if pend is None or pend["request_id"] != request_id:
                return
            self._resolve_approval(pend, "timed_out", {"outcome": {"outcome": "cancelled"}}, "timeout")

    def pending_approval_view(self) -> dict[str, Any]:
        """Read-only view of the pending approval for the local bridge (no client or timer handles)."""
        with self._lock:
            pend = self._pending_approval
            if pend is None:
                return {"pending": False}
            task = self.state.coding_tasks.get(pend["task_id"])
            return {
                "pending": True,
                "request_id": pend["request_id"],
                "task_id": pend["task_id"],
                "kind": pend["kind"],
                "action": pend["action"],
                "file_path": task.file_path if task is not None else "",
            }

    def reply_approval(
        self,
        text: str,
        *,
        request_id: str | None = None,
        task_id: str | None = None,
        editor_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Route a spoken reply to the pending approval only (R6). Never queues a follow-up.

        When `request_id` is given, the reply applies only if it names the pending approval;
        otherwise it is refused as stale and nothing is resolved. `task_id` (R18 binding) must
        match the pending approval's task when given; a mismatch resolves nothing.
        """
        with self._lock:
            if self._closed:
                return {
                    "status": "no_pending_approval",
                    "spoken": "The voice session has ended. Nothing was executed.",
                }
            pend = self._pending_approval
            if pend is None:
                return {"status": "no_pending_approval", "spoken": ""}
            if request_id is not None and request_id != pend["request_id"]:
                return {"status": "stale_approval", "spoken": ""}
            if task_id is not None and task_id != pend["task_id"]:
                return {"status": "task_mismatch", "spoken": ""}
            clean = (text or "").strip()
            action = pend["action"]
            if pend["kind"] == "question":
                if not any(ch.isalnum() for ch in clean):
                    return {"status": "reprompt", "spoken": f"Please answer: {action}"}
                # R6: a question answer is not an approval. Select the continue option so the
                # turn stays running, and put the text on the result so the provider sees it.
                allow = next(
                    (o for o in pend["options"] if isinstance(o, dict) and str(o.get("kind", "")).startswith("allow")),
                    None,
                )
                if allow is None:
                    # The provider offered no option that carries an answer, so the reply is
                    # cancelled on the wire. Say so: "answered" here would be a false success.
                    self._resolve_approval(
                        pend, "denied", {"outcome": {"outcome": "cancelled"}, "answer": clean},
                        "no_answer_option",
                    )
                    return {
                        "status": "not_delivered",
                        "spoken": "The provider offered no way to take that answer. Nothing was answered.",
                    }
                else:
                    self._resolve_approval(
                        pend,
                        "answered",
                        {
                            "outcome": {"outcome": "selected", "optionId": allow.get("optionId")},
                            "answer": clean,
                        },
                        clean,
                    )
                return {"status": "answered", "spoken": "Answer recorded."}

            lowered = clean.lower()
            action_lower = action.lower()
            if action_lower not in lowered:
                return {"status": "reprompt", "spoken": f"Say approve or deny {action}."}
            # The action label is matched once and then removed, so words inside it (for example
            # "deny" in a file name) cannot decide the reply. Any negation fails safe to reprompt.
            decision_text = lowered.replace(action_lower, " ", 1)
            says_yes = re.search(r"\bapprove\b", decision_text) is not None
            says_no = re.search(r"\bdeny\b", decision_text) is not None
            negated = NEGATION_RE.search(decision_text) is not None
            if negated or says_yes == says_no:
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
            task = self._get_task(str(pend["task_id"]))
            snap = self.state.context_snapshots.get(task.context_snapshot_id)
            if snap is not None and pend["kind"] == "write_or_command":
                live_version, live_dirty = self._live_buffer_at_reply(snap, editor_snapshot)
                file_mismatch = self._live_file_mismatch(snap, editor_snapshot)
                if file_mismatch or not buffers_match(snap, live_version, live_dirty):
                    self._event(task, "context.stale", {"file_path": snap.file_path})
                    self._resolve_approval(pend, "denied", {"outcome": {"outcome": "cancelled"}}, "stale")
                    return {"status": "stale", "spoken": "The editor buffer changed. Re-snapshot and resubmit."}
            final = self._resolve_approval(
                pend, "approved",
                {"outcome": {"outcome": "selected", "optionId": allow.get("optionId")}},
                "user_approved",
            )
            if final != "approved":
                return {"status": "denied", "spoken": "The file could not be written. Nothing was changed."}
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
            if task.provider_kind == "hive_spec":
                spoken = _shorten(
                    f"{TEST_SPEECH[tests]} Cited {task.reason}. See written result.",
                    self.config.spoken_update_max_chars,
                )
                self._say(task, spoken)
            else:
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
            if self._closed:
                return
            task = self.state.coding_tasks.get(task_id)
            if task is None or task.state != "unknown":
                return
            self._transition(task, "failed", "provider_lost")
            self._settle(task)
            self._save()
        self._dispatch_next()

    def _finish_planning(self, task: CodingTask) -> None:
        """Answer from spec/plan/tasks on disk. No ACP call (US5, SC-009). Caller holds the lock."""
        answer = answer_planning_question(self.paths, self.feature, task.instruction)
        self._transition(task, "running", "hive_spec")
        task.provider_kind = "hive_spec"
        self._event(task, "task.started", {"provider": "hive_spec", "source_path": answer["source_path"]})
        self._say(task, "Task accepted, running.")
        task.evidence.written_result = answer["written"]
        self._transition(task, "completed", answer["source_path"])
        self._settle(task)
        self._save()

    def _launch(self, task_id: str) -> None:
        """Open the provider session for a task, then start its prompt. Never holds the lock while blocking."""
        with self._lock:
            task = self.state.coding_tasks[task_id]
            if is_planning_question(task.instruction):
                if task.state == "cancel_requested":
                    self._transition(task, "cancelled", "cancelled_before_dispatch")
                    self._settle(task)
                    self._save()
                else:
                    self._finish_planning(task)
                planning = True
            else:
                planning = False
                mode = task.mode
        if planning:
            self._dispatch_next()
            return
        try:
            self._ensure_session(mode)
        except (AcpError, VoiceBotError, OSError) as exc:
            # OSError: the agent binary cannot be started (R19 coding_unavailable path).
            with self._lock:
                if self._closed:
                    return
                reason = "coding_unavailable" if isinstance(exc, OSError) else "submit_error"
                self._transition(task, "failed", f"{reason}: {exc}")
                self._settle(task)
                self._save()
            self._dispatch_next()
            return
        with self._lock:
            if self._closed:
                return
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
        with self._lock:
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
            stop = result.get("stopReason") if isinstance(result, dict) else None
            outcome = ("finished", str(stop or ""))
        except AcpDisconnected as exc:
            outcome = ("disconnected", str(exc))
        except AcpTimeout:
            outcome = ("timeout", "")
            self._abandon_provider()
        except AcpRemoteError as exc:
            outcome = ("remote_error", str(exc))
        except (AcpError, AssertionError) as exc:
            outcome = ("remote_error", str(exc))
        if client is not None:
            self._drain(client)
        self._finish(task_id, outcome)
        self._dispatch_next()

    def _finish(self, task_id: str, outcome: tuple[str, str]) -> None:
        kind, detail = outcome
        with self._lock:
            if self._closed:
                return
            task = self.state.coding_tasks[task_id]
            if task.state in TERMINAL_TASK_STATES:
                # Cancel already settled this task (for example while the prompt
                # thread was still unwinding a disconnect). Do not raise illegal_transition.
                return
            pend = self._pending_approval
            if pend is not None and pend["task_id"] == task_id:
                # The provider ended the turn before an answer: nothing executes. This is not a
                # timeout (R6), so it is recorded as a denial with the provider's end reason.
                self._resolve_approval(pend, "denied", {"outcome": {"outcome": "cancelled"}}, f"task_ended:{kind}")
            cancel_requested = task.state == "cancel_requested"
            if kind == "finished":
                task.evidence.stop_reason = detail
            if self._has_unguarded_write(task):
                # R22: a write with no matching approved permission request fails the task,
                # including disconnect and timeout. Reconnect cannot undo a write already seen.
                self._event(task, "write.unguarded", {"write_count": len(task.evidence.write_events)})
                self._transition(task, "failed", "unguarded_write")
            elif kind == "finished":
                if detail == "end_turn":
                    if self._has_update_error(task):
                        # A dropped update may have hidden a write, so no success is reported (R8, R22).
                        self._transition(task, "failed", "evidence_error")
                    elif cancel_requested:
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
                self._transition(task, "unknown", "provider_disconnected", self._correlation_ids(task))
            elif kind == "timeout":
                if cancel_requested:
                    self._transition(task, "failed", "cancel_not_acknowledged")
                else:
                    self._transition(task, "failed", "provider_timeout", self._correlation_ids(task))
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
            if self._closed or self._active_task_id is not None or self._call_ended:
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
                selection_text=str(entry.get("selection_text") or ""),
                file_content=str(entry.get("file_content") or ""),
                document_version=int(entry.get("document_version") or 0),
                dirty=bool(entry.get("dirty")),
                diagnostics=list(entry.get("diagnostics") or []),
                truncated=bool(entry.get("truncated")),
                excluded=str(entry.get("excluded") or ""),
            )
            entry["state"] = "dispatched"
            entry["task_id"] = task.task_id
            self._save()
        self._launch(task.task_id)

    def _new_task(
        self,
        *,
        text: str,
        file_path: str,
        mode: str,
        client_request_id: str,
        queue_id: str | None,
        selection_text: str = "",
        file_content: str = "",
        document_version: int = 0,
        dirty: bool = False,
        diagnostics: list[str] | None = None,
        truncated: bool = False,
        excluded: str = "",
    ) -> CodingTask:
        """Create a task and make it the active one. Caller holds the lock."""
        snapshot = create_context_snapshot(
            self.paths,
            self.state,
            ContextSnapshot(
                workspace_root=str(self.paths.root),
                file_path=file_path,
                selection_text=selection_text,
                file_content=file_content,
                document_version=document_version,
                dirty=dirty,
                instruction=text,
                diagnostics=list(diagnostics or []),
                truncated=truncated,
                excluded=excluded,
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

    def _enqueue(
        self,
        *,
        text: str,
        file_path: str,
        mode: str,
        client_request_id: str,
        selection_text: str = "",
        file_content: str = "",
        document_version: int = 0,
        dirty: bool = False,
        diagnostics: list[str] | None = None,
        truncated: bool = False,
        excluded: str = "",
    ) -> dict[str, Any]:
        """Append a FIFO entry (R5). Caller holds the lock. Raises when the queue is full."""
        depth = sum(1 for q in self.state.queue if q.get("state") in ("queued", "held"))
        if depth >= self.config.queue_depth:
            raise DelegationError(
                "queue_full",
                "the follow-up queue is full",
                spoken="The follow-up queue is full. Nothing was queued.",
            )
        entry = {
            "queue_id": _new_id("q"),
            "session_id": self.session.session_id,
            "task_id": None,
            "text": text,
            "state": "held" if self._pending_approval is not None else "queued",
            "file_path": file_path,
            "mode": mode,
            "client_request_id": client_request_id,
            "selection_text": selection_text,
            "file_content": file_content,
            "document_version": document_version,
            "dirty": dirty,
            "diagnostics": list(diagnostics or []),
            "truncated": truncated,
            "excluded": excluded,
        }
        self.state.queue.append(entry)
        return entry

    def _require_active_session(self) -> None:
        """Refuse ended sessions; a submit or follow-up after an interruption restores `active` (R1)."""
        if self._closed or self._call_ended or self.session.state not in ("active", "interrupted"):
            raise DelegationError(
                "session_not_active",
                "the voice session has ended",
                spoken="The voice session has ended. Nothing was submitted.",
            )
        if self.session.state == "interrupted":
            self.session.state = "active"
            self._save()

    # -- bounded delegation surface (T006, R18) ----------------------------

    def submit(
        self,
        instruction: str,
        *,
        mode: str = "ask",
        file_path: str = "",
        client_request_id: str = "",
        selection_text: str = "",
        file_content: str = "",
        document_version: int = 0,
        dirty: bool = False,
        editor_snapshot: dict[str, Any] | None = None,
        diagnostics: list[str] | None = None,
    ) -> dict[str, Any]:
        """`submit_coding_task`. The only call that issues a task_id (R18)."""
        with self._lock:
            self._require_active_session()
            if not str(client_request_id or "").strip():
                raise DelegationError("missing_client_request_id", "submit requires client_request_id")
            if mode not in ALLOWED_MODES:
                raise DelegationError("invalid_mode", f"mode must be one of {', '.join(ALLOWED_MODES)}")
            if mode == "agent" and not edits_enabled(self.paths):
                raise DelegationError(
                    "agent_mode_disabled",
                    "agent mode is disabled until G6 closes",
                    spoken="Agent mode is disabled. Nothing was submitted.",
                )
            key = self._dedupe_key(client_request_id)
            if key in self.state.dedupe:
                return self._dedupe_result(key)
            text = self._validate_instruction(instruction)
            mapped_diagnostics = list(diagnostics or [])
            mapped_truncated = False
            mapped_excluded = ""
            if editor_snapshot is not None:
                mapped = map_editor_snapshot(
                    editor_snapshot, instruction=text, workspace_root=str(self.paths.root),
                )
                file_path = mapped.file_path or file_path
                selection_text = mapped.selection_text
                file_content = mapped.file_content
                document_version = mapped.document_version
                dirty = mapped.dirty
                mapped_diagnostics = list(mapped.diagnostics)
                mapped_truncated = mapped.truncated
                mapped_excluded = mapped.excluded or ""
            rel = self._resolve_file(file_path)
            # Only a caller that supplied a version (snapshot or explicit, versions start at 1) is
            # checked; with no version there is nothing to compare, so the check is not run.
            live = self._live_buffer(rel) if (rel and self._live_buffer is not None and document_version > 0) else None
            if live is not None:
                live_version, live_dirty = live
                if not (document_version == live_version and bool(dirty) == bool(live_dirty)):
                    raise DelegationError(
                        "stale",
                        "the editor buffer changed; re-snapshot and resubmit",
                        spoken="The editor buffer changed. Re-snapshot and resubmit.",
                    )
            if self._active_task_id is not None:
                entry = self._enqueue(
                    text=text, file_path=rel, mode=mode, client_request_id=client_request_id,
                    selection_text=selection_text, file_content=file_content,
                    document_version=document_version, dirty=dirty,
                    diagnostics=mapped_diagnostics, truncated=mapped_truncated,
                    excluded=mapped_excluded,
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
                selection_text=selection_text, file_content=file_content,
                document_version=document_version, dirty=dirty,
                diagnostics=mapped_diagnostics, truncated=mapped_truncated,
                excluded=mapped_excluded,
            )
            self._save()
            task_id = task.task_id
        self._launch(task_id)
        with self._lock:
            task = self.state.coding_tasks[task_id]
            return {
                "status": task.state, "task_id": task_id, "state": task.state,
                "context_snapshot_id": task.context_snapshot_id,
                "spoken": task.evidence.spoken_update,
            }

    def _transcribe_spoken(
        self,
        audio: bytes | None,
        wav_abs: Path | None,
        stt_model_dir: Path | None,
        stt_adapter: Any | None,
    ) -> str:
        """Shared STT step for spoken submits and spoken approval replies. Raises `DelegationError`."""
        if stt_adapter is None:
            model_dir = stt_model_dir or resolve_pinned_model_dir()
            if model_dir is None:
                raise DelegationError(
                    "stt_model_missing", "pinned STT model or faster_whisper is not available",
                    spoken="Speech recognition is not available. Type the instruction.",
                )
            try:
                stt_adapter = FasterWhisperAdapter(model_dir)
            except SttError as exc:
                raise DelegationError(str(exc), "STT adapter could not start") from exc
        try:
            text = stt_adapter.transcribe(audio) if audio is not None else stt_adapter.transcribe_file(wav_abs)
        except SttError as exc:
            raise DelegationError(str(exc) or "stt_failed", "transcription failed") from exc
        if not (text or "").strip():
            raise DelegationError(
                "stt_failed",
                "transcription was empty",
                spoken="I didn't catch that. Type the instruction.",
            )
        return text

    def reply_spoken(
        self,
        *,
        request_id: str,
        task_id: str,
        audio: bytes | None = None,
        wav_path: str = "",
        editor_snapshot: dict[str, Any] | None = None,
        stt_model_dir: Path | None = None,
        stt_adapter: Any | None = None,
        moshi_live_call: bool = False,
    ) -> dict[str, Any]:
        """Spoken approval reply: transcribe, then route the text to the pending approval only (R6).

        Same gates as `submit_spoken` (stt_provider set, Moshi listen gate, exactly one input), so
        spoken approvals cannot bypass what spoken instructions must pass. The transcript is never
        queued as a follow-up; `reply_approval` decides whether it matches the visible prompt.
        """
        if not self.config.stt_provider:
            raise DelegationError(
                "stt_not_configured", "stt_provider is null",
                spoken="Spoken input is off. Approve by typing or clicking.",
            )
        # The listen gate may start the Moshi server and wait for it. It runs before the runner
        # lock so a slow server cannot freeze typed submits, status, or approvals.
        # R37 (2026-11-15): a live panel call already holds the server slot; its utterance skips the probe.
        listen_code = None if moshi_live_call else moshi_listen_gate(self.config)
        if listen_code:
            raise DelegationError(
                listen_code, "moshi listen layer is not available",
                spoken=MOSHI_SPOKEN.get(listen_code, "Moshi is not available. Approve by typing or clicking."),
            )
        with self._lock:
            self._require_active_session()
            if (audio is None) == (not wav_path):
                raise DelegationError("stt_input_required", "pass exactly one of audio or wav_path")
            wav_abs: Path | None = None
            if wav_path:
                wav_abs = self.paths.root / self._resolve_wav_input(wav_path)
        text = self._transcribe_spoken(audio, wav_abs, stt_model_dir, stt_adapter)
        out = self.reply_approval(
            text, request_id=request_id, task_id=task_id, editor_snapshot=editor_snapshot,
        )
        out["transcript"] = text
        return out

    def submit_spoken(
        self,
        *,
        audio: bytes | None = None,
        wav_path: str = "",
        client_request_id: str = "",
        mode: str = "ask",
        file_path: str = "",
        editor_snapshot: dict[str, Any] | None = None,
        stt_model_dir: Path | None = None,
        stt_adapter: Any | None = None,
        moshi_live_call: bool = False,
    ) -> dict[str, Any]:
        """T042 slice 2: spoken turn. Transcribes with the pinned STT adapter, then submits the text.

        Only reachable when config `stt_provider` is set (default null refuses with
        `stt_not_configured`). Exactly one of `audio` (WAV bytes) or `wav_path` (a file inside the
        workspace) must be given. Failures raise `DelegationError`; nothing falls back silently.
        `stt_adapter` is injectable for tests; otherwise the pinned local model is loaded.
        """
        if not self.config.stt_provider:
            raise DelegationError(
                "stt_not_configured", "stt_provider is null",
                spoken="Spoken input is off. Type the instruction.",
            )
        # T053 / R36: the Moshi listen layer must answer its handshake before a spoken turn.
        # Refusal happens before transcription, so no task is created. The gate runs before the
        # runner lock (see reply_spoken). A live panel call skips it (R37, moshi_live_call).
        listen_code = None if moshi_live_call else moshi_listen_gate(self.config)
        if listen_code:
            raise DelegationError(
                listen_code, "moshi listen layer is not available",
                spoken=MOSHI_SPOKEN.get(listen_code, "Moshi is not available. Type the instruction."),
            )
        with self._lock:
            self._require_active_session()
            if not str(client_request_id or "").strip():
                raise DelegationError("missing_client_request_id", "submit requires client_request_id")
            if (audio is None) == (not wav_path):
                raise DelegationError("stt_input_required", "pass exactly one of audio or wav_path")
            wav_abs: Path | None = None
            if wav_path:
                rel = self._resolve_wav_input(wav_path)
                wav_abs = self.paths.root / rel
        text = self._transcribe_spoken(audio, wav_abs, stt_model_dir, stt_adapter)
        out = self.submit(
            text, mode=mode, file_path=file_path, client_request_id=client_request_id,
            editor_snapshot=editor_snapshot,
        )
        out["transcript"] = text
        return out

    def _dedupe_result(self, key: str) -> dict[str, Any]:
        ref = self.state.dedupe[key]
        if ref.get("task_id"):
            task = self.state.coding_tasks[str(ref["task_id"])]
            return {
                "status": "duplicate", "task_id": task.task_id,
                "context_snapshot_id": task.context_snapshot_id,
                "state": task.state, "spoken": "",
            }
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
                "context_snapshot_id": task.context_snapshot_id,
                "state": task.state,
                "reason": task.reason,
                "transitions": list(task.transitions),
                "approval": task.approval,
            }
            if task.state in TERMINAL_TASK_STATES:
                payload["tests_status"] = task.evidence.tests_status
            return payload

    def task_result(self, task_id: str) -> dict[str, Any]:
        """Status plus the spoken and written text, read under the lock (bridge `GET /v1/task`)."""
        with self._lock:
            payload = self.task_status(task_id)
            task = self._get_task(task_id)
            payload["spoken"] = task.evidence.spoken_update
            payload["written"] = task.evidence.written_result
            return payload

    def submission_view(self, client_request_id: str) -> dict[str, Any]:
        """Where a submit ended up: a task (dispatched) or a queue entry (still waiting).

        A queued submit has no task_id until the queue dispatches it (R5). Callers poll this
        instead of assuming the turn ran. `state` is the task state, or the queue state
        (`queued`, `held`, `dispatched`, `discarded`) while no task exists.
        """
        with self._lock:
            key = self._dedupe_key(client_request_id)
            ref = self.state.dedupe.get(key)
            if ref is None:
                raise DelegationError("unknown_submission", "no submit with that client_request_id")
            if ref.get("task_id"):
                task = self._get_task(str(ref["task_id"]))
                return {
                    "task_id": task.task_id, "context_snapshot_id": task.context_snapshot_id,
                    "state": task.state, "queue_id": ref.get("queue_id"),
                }
            queue_id = ref.get("queue_id")
            entry = next((q for q in self.state.queue if q.get("queue_id") == queue_id), None)
            return {
                "task_id": None, "context_snapshot_id": None, "queue_id": queue_id,
                "state": entry.get("state") if entry else "discarded",
            }

    def wait_submission(self, client_request_id: str, timeout: float) -> dict[str, Any]:
        """Wait until a submit has a task that is terminal, or its queue entry is discarded.

        Returns the last `submission_view`. Used so a queued turn is waited for, not reported
        as finished (queued turns bug). Times out with the last view still non-terminal.
        """
        deadline = self._clock() + timeout
        while True:
            view = self.submission_view(client_request_id)
            if view["task_id"]:
                if view["state"] in TERMINAL_TASK_STATES or self._clock() > deadline:
                    return view
            elif view["state"] == "discarded" or self._clock() > deadline:
                return view
            time.sleep(0.02)

    def task_diff(self, task_id: str) -> dict[str, Any]:
        """Unified diff of recorded write evidence (T032).

        Only when the R33 edits latch is on AND the task recorded a write. Otherwise the
        result is `no_diff_evidence` with empty text.
        """
        with self._lock:
            task = self._get_task(task_id)
            if edits_enabled(self.paths) and task.evidence.write_diffs:
                chunks: list[str] = []
                for d in task.evidence.write_diffs:
                    path = d["path"] or "unknown"
                    chunks.extend(difflib.unified_diff(
                        d["old_text"].splitlines(keepends=True),
                        d["new_text"].splitlines(keepends=True),
                        fromfile=f"a/{path}", tofile=f"b/{path}",
                    ))
                text, truncated = cap_text("".join(chunks), self.config.diff_max_bytes)
                return {"task_id": task_id, "diff": text, "truncated": truncated, "source": "write_evidence"}
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
            # Carry the active snapshot, including excluded, so dispatch cannot refill
            # a secret/binary/unsaved file from disk (R2, R28).
            snap = self.state.context_snapshots.get(active.context_snapshot_id)
            entry = self._enqueue(
                text=clean,
                file_path=active.file_path,
                mode=active.mode,
                client_request_id="",
                selection_text=snap.selection_text if snap else "",
                file_content=snap.file_content if snap else "",
                document_version=snap.document_version if snap else 0,
                dirty=snap.dirty if snap else False,
                diagnostics=list(snap.diagnostics) if snap else [],
                truncated=bool(snap.truncated) if snap else False,
                excluded=snap.excluded if snap else "",
            )
            self._refresh_queue_holds()
            self._save()
            return {"status": "queued", "queue_id": entry["queue_id"], "task_id": None, "state": entry["state"]}

    def cancel(self, task_id: str) -> dict[str, Any]:
        """`cancel_coding_task`. Requested and acknowledged are separate records (R7, SC-011)."""
        with self._lock:
            if self._closed:
                raise DelegationError(
                    "session_not_active",
                    "the voice session has ended",
                    spoken="The voice session has ended. Nothing was cancelled.",
                )
            task = self._get_task(task_id)
            if task.state in TERMINAL_TASK_STATES:
                raise DelegationError("task_already_terminal", f"task is {task.state}")
            if task.state == "cancel_requested":
                return {"task_id": task_id, "state": "cancel_requested", "spoken": "", "rollback": "not_performed"}
            pend = self._pending_approval
            if pend is not None and pend["task_id"] == task_id:
                # User cancel is not a timeout (R6): nothing executes, so record a denial.
                self._resolve_approval(pend, "denied", {"outcome": {"outcome": "cancelled"}}, "task_cancelled")
            was_running = task.state in ("running", "awaiting_approval")
            client = self._client
            connected = client is not None and client.is_connected()
            if task.state == "unknown" or (not connected and task.state != "submitted"):
                # No live provider can acknowledge the cancel, so it is recorded as not acknowledged.
                self._transition(task, "cancel_requested", "user_cancel")
                self._transition(task, "failed", "cancel_not_acknowledged")
                self._settle(task)
                self._save()
                freed_slot = True
            else:
                freed_slot = False
                self._transition(task, "cancel_requested", "user_cancel")
                if was_running and client is not None:
                    try:
                        client.notify("session/cancel", {"sessionId": self._acp_session_id})
                    except AcpDisconnected:
                        pass
                self._save()
        if freed_slot:
            # The active slot is free now. Dispatch queued follow-ups outside the lock, since
            # starting a provider session can block (same rule as _run_prompt and _provider_lost).
            self._dispatch_next()
            return {"task_id": task_id, "state": "failed", "spoken": "", "rollback": "not_performed"}
        return {"task_id": task_id, "state": "cancel_requested", "spoken": "", "rollback": "not_performed"}

    def get_context_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        with self._lock:
            snap = self.state.context_snapshots.get(snapshot_id)
            if snap is None:
                raise DelegationError("unknown_snapshot", snapshot_id)
            return snap.to_dict()

    def _bind_workspace(self, workspace: str) -> None:
        presented = str(workspace or "").strip()
        if not presented:
            raise DelegationError("missing_workspace", "every R18 call binds workspace")
        if not same_workspace(presented, self.paths.root):
            raise DelegationError("workspace_mismatch", "workspace is not bound to this session")

    def _bind_snapshot(self, context_snapshot_id: str) -> None:
        snapshot_id = str(context_snapshot_id or "").strip()
        if not snapshot_id:
            raise DelegationError("missing_context_snapshot_id", "every R18 call binds context_snapshot_id")
        if snapshot_id not in self.state.context_snapshots:
            raise DelegationError("unknown_snapshot", snapshot_id)

    def _queue_editor_action(
        self,
        *,
        kind: str,
        file_path: str = "",
        task_id: str = "",
        context_snapshot_id: str = "",
        text: str = "",
        truncated: bool = False,
    ) -> dict[str, Any]:
        action = {
            "action_id": _new_id("ed"),
            "kind": kind,
            "file_path": file_path,
            "task_id": task_id,
            "context_snapshot_id": context_snapshot_id,
            "text": text,
            "truncated": truncated,
            "opened": False,
        }
        self.state.editor_actions.append(action)
        self._save()
        return action

    def pending_editor_action(self) -> dict[str, Any]:
        with self._lock:
            pending = next((row for row in self.state.editor_actions if not row.get("opened")), None)
            if pending is None:
                return {"pending": False}
            return {
                "pending": True,
                "action_id": pending["action_id"],
                "kind": pending["kind"],
                "file_path": pending.get("file_path") or "",
                "task_id": pending.get("task_id") or "",
                "context_snapshot_id": pending.get("context_snapshot_id") or "",
                "text": pending.get("text") or "",
                "truncated": bool(pending.get("truncated")),
            }

    def ack_editor_action(self, action_id: str) -> dict[str, Any]:
        with self._lock:
            for row in self.state.editor_actions:
                if row.get("action_id") == action_id:
                    row["opened"] = True
                    self._save()
                    return {
                        "status": "opened",
                        "action_id": action_id,
                        "kind": row.get("kind"),
                        "file_path": row.get("file_path") or "",
                        "navigated": row.get("kind") == "navigate",
                        "shown": row.get("kind") == "show_diff",
                    }
            return {"status": "unknown_action", "action_id": action_id}

    def show_diff(self, task_id: str, *, context_snapshot_id: str = "") -> dict[str, Any]:
        diff = self.task_diff(task_id)
        with self._lock:
            task = self._get_task(task_id)
            snapshot_id = context_snapshot_id or task.context_snapshot_id
            self._bind_snapshot(snapshot_id)
            text = diff.get("diff") or task.evidence.written_result
            capped, truncated = cap_text(text, self.config.diff_max_bytes)
            truncated = truncated or bool(diff.get("truncated"))
            action = self._queue_editor_action(
                kind="show_diff",
                file_path=task.file_path,
                task_id=task_id,
                context_snapshot_id=snapshot_id,
                text=capped,
                truncated=truncated,
            )
            return {
                "task_id": task_id,
                "diff": capped,
                "truncated": truncated,
                "queued": True,
                "shown": False,
                "action_id": action["action_id"],
                "context_snapshot_id": snapshot_id,
            }

    def navigate_to(self, file_path: str, *, context_snapshot_id: str = "") -> dict[str, Any]:
        if not str(file_path or "").strip():
            raise DelegationError("missing_file_path", "navigate_to requires a file path")
        rel = self._resolve_file(file_path)
        with self._lock:
            snapshot_id = str(context_snapshot_id or "").strip()
            self._bind_snapshot(snapshot_id)
            action = self._queue_editor_action(
                kind="navigate",
                file_path=rel,
                context_snapshot_id=snapshot_id,
            )
            return {
                "file_path": rel,
                "queued": True,
                "navigated": False,
                "action_id": action["action_id"],
                "context_snapshot_id": snapshot_id,
            }

    def invoke_controller_tool(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """R18: only the named tools exist. Any other name is unbounded_tool (AC 16)."""
        if name not in VOICE_CONTROLLER_TOOLS:
            raise DelegationError("unbounded_tool", name)
        self._bind_workspace(str(kwargs.get("workspace") or ""))
        if name == "submit_coding_task":
            editor = kwargs.get("editor_snapshot")
            return self.submit(
                str(kwargs.get("instruction") or ""),
                mode=str(kwargs.get("mode") or "ask"),
                file_path=str(kwargs.get("file_path") or ""),
                client_request_id=str(kwargs.get("client_request_id") or ""),
                selection_text=str(kwargs.get("selection_text") or ""),
                file_content=str(kwargs.get("file_content") or ""),
                document_version=int(kwargs.get("document_version") or 0),
                dirty=bool(kwargs.get("dirty")),
                editor_snapshot=editor if isinstance(editor, dict) else None,
            )
        snapshot_id = str(kwargs.get("context_snapshot_id") or kwargs.get("snapshot_id") or "")
        self._bind_snapshot(snapshot_id)
        if name != "get_context_snapshot" and name != "navigate_to":
            if not str(kwargs.get("task_id") or "").strip():
                raise DelegationError("missing_task_id", "calls after submit bind task_id")
        if name == "task_status":
            return self.task_status(str(kwargs["task_id"]))
        if name == "task_diff":
            return self.task_diff(str(kwargs["task_id"]))
        if name == "show_diff":
            return self.show_diff(str(kwargs["task_id"]), context_snapshot_id=snapshot_id)
        if name == "queue_follow_up":
            return self.queue_follow_up(str(kwargs.get("text") or ""), task_id=str(kwargs["task_id"]))
        if name == "cancel_coding_task":
            return self.cancel(str(kwargs["task_id"]))
        if name == "get_context_snapshot":
            return self.get_context_snapshot(snapshot_id)
        return self.navigate_to(str(kwargs.get("file_path") or ""), context_snapshot_id=snapshot_id)

    # -- playback, call end (T010) -----------------------------------------

    def interrupt_playback(self) -> dict[str, Any]:
        """Stop talking. Sets the session to `interrupted` and changes no task state (R1, R7, SC-003)."""
        with self._lock:
            task = self._active_task()
            before = task.state if task else None
            if task is not None:
                self._event(task, "speech.interrupted", {})
            if not self._call_ended and self.session.state == "active":
                self.session.state = "interrupted"
            # Stop the speaker too (R1, R13): playback stops, task state does not change.
            from hive_planner.voice_tts import stop_playback  # lazy: no audio stack on import

            stop_playback()
            self._save()
            after = task.state if task else None
            return {
                "event": "speech.interrupted",
                "task_state_before": before,
                "task_state_after": after,
                "state_changed": before != after,
                "session_state": self.session.state,
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

    def _abandon_provider(self) -> None:
        """Cancel the in-flight prompt and drop the child so the next task cannot share it."""
        with self._lock:
            client = self._client
            session_id = self._acp_session_id
            self._client = None
            self._acp_session_id = ""
            self._mode_set = ""
        if client is None:
            return
        try:
            if client.is_connected():
                client.notify("session/cancel", {"sessionId": session_id})
        except AcpError:
            pass
        try:
            client.terminate()
            client.close()
        except (AcpError, OSError):
            pass

    def close(self) -> None:
        """Close the provider session, stop timers, and release the cross-process runner lock."""
        with self._lock:
            self._closed = True
            for timer in self._provider_lost_timers.values():
                timer.cancel()
            pend = self._pending_approval
            if pend is not None:
                pend["timer"].cancel()
            client = self._client
            self._client = None
        try:
            if client is not None:
                client.close()
        finally:
            self._repo_lock.release()

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

