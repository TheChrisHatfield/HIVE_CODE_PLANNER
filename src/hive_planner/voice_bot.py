"""Voice_Bot contracts — HIVE-owned session, task, context, and evidence (hook: voice.experience)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from hive_planner.config import RepoPaths, validate_feature_id

SCHEMA_VERSION = "voice-bot.v1"
VOICE_BOT_DIR = Path(".hive") / "voice-bot"
STATE_FILE = "state.json"
CONFIG_FILE = "config.json"

VoiceSessionState = Literal["idle", "active", "interrupted", "ended"]
# R20 task states. Queue entries (R5) are not tasks and live in VoiceBotState.queue.
CodingTaskState = Literal[
    "submitted",
    "running",
    "awaiting_approval",
    "cancel_requested",
    "unknown",
    "completed",
    "failed",
    "cancelled",
]
CODING_TASK_STATES: tuple[str, ...] = (
    "submitted",
    "running",
    "awaiting_approval",
    "cancel_requested",
    "unknown",
    "completed",
    "failed",
    "cancelled",
)
TERMINAL_TASK_STATES: tuple[str, ...] = ("completed", "failed", "cancelled")
TestsStatus = Literal["not_run", "passed", "failed", "unknown"]


class VoiceBotError(Exception):
    """Voice_Bot contract or persistence error."""


_R24_FIELDS = ("latency_target_ms", "first_spoken_update_target_ms")


@dataclass(frozen=True)
class VoiceBotConfig:
    """Single config object for R21 limits and R24 budgets (T001a).

    R21 defaults are provisional. R24 targets stay ``None`` (no claimed
    target) until the T018 baseline is recorded in the evidence register.
    """

    instruction_max_chars: int = 4_000
    snapshot_max_bytes: int = 64 * 1024
    approval_timeout_s: int = 120
    queue_depth: int = 5
    spoken_update_max_chars: int = 300
    diff_max_bytes: int = 256 * 1024
    progress_interval_s: int = 30
    reconnect_window_s: int = 300
    latency_target_ms: int | None = None
    first_spoken_update_target_ms: int | None = None

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            if value is None and f.name in _R24_FIELDS:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise VoiceBotError(f"voice_bot config '{f.name}' must be a positive integer")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceBotConfig:
        allowed = {f.name for f in fields(cls)}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise VoiceBotError(f"unknown voice_bot config keys: {', '.join(unknown)}")
        return cls(**data)


DEFAULT_VOICE_BOT_CONFIG = VoiceBotConfig()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class CartridgeTrace:
    """Links a voice turn to the active HIVE cartridge and Rosetta context."""

    feature_id: str
    cartridge_id: str | None = None
    manifest_path: str = "cartridge/manifest.json"
    source_map_path: str = ""
    rosetta_hooks: tuple[str, ...] = ()
    spec_path: str = ""
    plan_path: str = ""
    tasks_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "cartridge_id": self.cartridge_id,
            "manifest_path": self.manifest_path,
            "source_map_path": self.source_map_path,
            "rosetta_hooks": list(self.rosetta_hooks),
            "spec_path": self.spec_path,
            "plan_path": self.plan_path,
            "tasks_path": self.tasks_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CartridgeTrace:
        hooks = data.get("rosetta_hooks") or []
        if not isinstance(hooks, list):
            hooks = []
        return cls(
            feature_id=str(data.get("feature_id") or ""),
            cartridge_id=data.get("cartridge_id"),
            manifest_path=str(data.get("manifest_path") or "cartridge/manifest.json"),
            source_map_path=str(data.get("source_map_path") or ""),
            rosetta_hooks=tuple(str(h) for h in hooks),
            spec_path=str(data.get("spec_path") or ""),
            plan_path=str(data.get("plan_path") or ""),
            tasks_path=str(data.get("tasks_path") or ""),
        )


@dataclass
class ContextSnapshot:
    workspace_root: str
    file_path: str
    selection_text: str
    document_version: int
    dirty: bool
    instruction: str
    snapshot_id: str = ""
    diagnostics: list[str] = field(default_factory=list)
    cartridge_trace: CartridgeTrace | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "snapshot_id": self.snapshot_id,
            "workspace_root": self.workspace_root,
            "file_path": self.file_path,
            "selection_text": self.selection_text,
            "document_version": self.document_version,
            "dirty": self.dirty,
            "diagnostics": list(self.diagnostics),
            "instruction": self.instruction,
            "created_at": self.created_at or _utc_now(),
        }
        if self.cartridge_trace is not None:
            payload["cartridge_trace"] = self.cartridge_trace.to_dict()
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextSnapshot:
        trace_raw = data.get("cartridge_trace")
        trace = CartridgeTrace.from_dict(trace_raw) if isinstance(trace_raw, dict) else None
        diags = data.get("diagnostics") or []
        if not isinstance(diags, list):
            diags = []
        return cls(
            snapshot_id=str(data.get("snapshot_id") or ""),
            workspace_root=str(data.get("workspace_root") or ""),
            file_path=str(data.get("file_path") or ""),
            selection_text=str(data.get("selection_text") or ""),
            document_version=int(data.get("document_version") or 0),
            dirty=bool(data.get("dirty")),
            diagnostics=[str(d) for d in diags],
            instruction=str(data.get("instruction") or ""),
            cartridge_trace=trace,
            created_at=str(data.get("created_at") or ""),
        )


@dataclass
class TaskEvidence:
    written_result: str = ""
    spoken_update: str = ""
    tests_status: TestsStatus = "not_run"
    stop_reason: str = ""
    provider_turn_finished: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskEvidence:
        status = data.get("tests_status", "not_run")
        if status not in ("not_run", "passed", "failed", "unknown"):
            status = "unknown"
        return cls(
            written_result=str(data.get("written_result") or ""),
            spoken_update=str(data.get("spoken_update") or ""),
            tests_status=status,
            stop_reason=str(data.get("stop_reason") or ""),
            provider_turn_finished=bool(data.get("provider_turn_finished")),
        )


@dataclass
class CodingTask:
    task_id: str
    voice_session_id: str
    context_snapshot_id: str
    state: CodingTaskState = "submitted"
    provider_session_id: str = ""
    provider_kind: str = ""
    evidence: TaskEvidence = field(default_factory=TaskEvidence)
    created_at: str = ""
    updated_at: str = ""
    client_request_id: str = ""  # submit dedupe key with session id (R18, R29)
    mode: str = "ask"
    instruction: str = ""
    file_path: str = ""
    reason: str = ""  # reason of the most recent transition
    transitions: list[dict[str, str]] = field(default_factory=list)  # R20 record (SC-011)
    events: list[dict[str, Any]] = field(default_factory=list)  # normalized R17 events
    raw_events: list[Any] = field(default_factory=list)  # raw provider payloads (R17)
    approval: dict[str, Any] | None = None  # current or last approval (R6)
    approvals: list[dict[str, Any]] = field(default_factory=list)  # history of approvals (R6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "voice_session_id": self.voice_session_id,
            "context_snapshot_id": self.context_snapshot_id,
            "state": self.state,
            "provider_session_id": self.provider_session_id,
            "provider_kind": self.provider_kind,
            "evidence": self.evidence.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "client_request_id": self.client_request_id,
            "mode": self.mode,
            "instruction": self.instruction,
            "file_path": self.file_path,
            "reason": self.reason,
            "transitions": list(self.transitions),
            "events": list(self.events),
            "raw_events": list(self.raw_events),
            "approval": self.approval,
            "approvals": list(self.approvals),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodingTask:
        ev = data.get("evidence")
        evidence = TaskEvidence.from_dict(ev) if isinstance(ev, dict) else TaskEvidence()
        state = data.get("state", "submitted")
        if state not in CODING_TASK_STATES:
            state = "unknown"
        return cls(
            task_id=str(data.get("task_id") or ""),
            voice_session_id=str(data.get("voice_session_id") or ""),
            context_snapshot_id=str(data.get("context_snapshot_id") or ""),
            state=state,
            provider_session_id=str(data.get("provider_session_id") or ""),
            provider_kind=str(data.get("provider_kind") or ""),
            evidence=evidence,
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            client_request_id=str(data.get("client_request_id") or ""),
            mode=str(data.get("mode") or "ask"),
            instruction=str(data.get("instruction") or ""),
            file_path=str(data.get("file_path") or ""),
            reason=str(data.get("reason") or ""),
            transitions=list(data.get("transitions") or []),
            events=list(data.get("events") or []),
            raw_events=list(data.get("raw_events") or []),
            approval=data.get("approval") if isinstance(data.get("approval"), dict) else None,
            approvals=list(data.get("approvals") or []),
        )


@dataclass
class VoiceSession:
    session_id: str
    state: VoiceSessionState = "idle"
    feature_id: str = ""
    cartridge_trace: CartridgeTrace | None = None
    provider_voice: str = ""
    started_at: str = ""
    ended_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "session_id": self.session_id,
            "state": self.state,
            "feature_id": self.feature_id,
            "provider_voice": self.provider_voice,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }
        if self.cartridge_trace is not None:
            payload["cartridge_trace"] = self.cartridge_trace.to_dict()
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceSession:
        trace_raw = data.get("cartridge_trace")
        trace = CartridgeTrace.from_dict(trace_raw) if isinstance(trace_raw, dict) else None
        state = data.get("state", "idle")
        if state not in ("idle", "active", "interrupted", "ended"):
            state = "idle"
        return cls(
            session_id=str(data.get("session_id") or ""),
            state=state,
            feature_id=str(data.get("feature_id") or ""),
            cartridge_trace=trace,
            provider_voice=str(data.get("provider_voice") or ""),
            started_at=str(data.get("started_at") or ""),
            ended_at=str(data.get("ended_at") or ""),
        )


@dataclass
class VoiceBotState:
    schema_version: str = SCHEMA_VERSION
    voice_session: VoiceSession | None = None
    context_snapshots: dict[str, ContextSnapshot] = field(default_factory=dict)
    coding_tasks: dict[str, CodingTask] = field(default_factory=dict)
    # R5 queue entries: {queue_id, session_id, task_id, text, state, ...}. No task_id until dispatched.
    queue: list[dict[str, Any]] = field(default_factory=list)
    # R29 dedupe: "session_id|client_request_id" -> {"task_id": ..., "queue_id": ...}
    dedupe: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "voice_session": self.voice_session.to_dict() if self.voice_session else None,
            "context_snapshots": {
                k: v.to_dict() for k, v in self.context_snapshots.items()
            },
            "coding_tasks": {k: v.to_dict() for k, v in self.coding_tasks.items()},
            "queue": list(self.queue),
            "dedupe": dict(self.dedupe),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceBotState:
        vs_raw = data.get("voice_session")
        voice_session = VoiceSession.from_dict(vs_raw) if isinstance(vs_raw, dict) else None
        snaps_raw = data.get("context_snapshots") or {}
        tasks_raw = data.get("coding_tasks") or {}
        snapshots: dict[str, ContextSnapshot] = {}
        tasks: dict[str, CodingTask] = {}
        if isinstance(snaps_raw, dict):
            for key, val in snaps_raw.items():
                if isinstance(val, dict):
                    snapshots[str(key)] = ContextSnapshot.from_dict(val)
        if isinstance(tasks_raw, dict):
            for key, val in tasks_raw.items():
                if isinstance(val, dict):
                    tasks[str(key)] = CodingTask.from_dict(val)
        version = str(data.get("schema_version") or SCHEMA_VERSION)
        queue_raw = data.get("queue") or []
        dedupe_raw = data.get("dedupe") or {}
        return cls(
            schema_version=version,
            voice_session=voice_session,
            context_snapshots=snapshots,
            coding_tasks=tasks,
            queue=[q for q in queue_raw if isinstance(q, dict)] if isinstance(queue_raw, list) else [],
            dedupe=dict(dedupe_raw) if isinstance(dedupe_raw, dict) else {},
        )


def voice_bot_state_path(paths: RepoPaths) -> Path:
    return paths.root / VOICE_BOT_DIR / STATE_FILE


def voice_bot_config_path(paths: RepoPaths) -> Path:
    return paths.root / VOICE_BOT_DIR / CONFIG_FILE


def load_voice_bot_config(paths: RepoPaths) -> VoiceBotConfig:
    """Load `.hive/voice-bot/config.json` overrides; missing file means R21 defaults."""
    path = voice_bot_config_path(paths)
    if not path.is_file():
        return DEFAULT_VOICE_BOT_CONFIG
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise VoiceBotError(f"Could not read voice-bot config: {exc}") from exc
    if not isinstance(data, dict):
        raise VoiceBotError("voice-bot config must be a JSON object")
    return VoiceBotConfig.from_dict(data)


def validate_context_snapshot(
    snapshot: ContextSnapshot,
    config: VoiceBotConfig | None = None,
) -> None:
    cfg = config or DEFAULT_VOICE_BOT_CONFIG
    if not snapshot.workspace_root.strip():
        raise VoiceBotError("workspace_root is required")
    if not snapshot.instruction.strip():
        raise VoiceBotError("instruction is required")
    if len(snapshot.instruction) > cfg.instruction_max_chars:
        raise VoiceBotError("instruction exceeds configured limit")
    if ".." in snapshot.file_path.replace("\\", "/"):
        raise VoiceBotError("file_path must stay inside the workspace")
    if len(snapshot.selection_text.encode("utf-8")) > cfg.snapshot_max_bytes:
        raise VoiceBotError("selection_text exceeds configured limit")


def grounded_spoken_update(evidence: TaskEvidence) -> str:
    """Return spoken_update only when it is backed by recorded evidence."""
    if not evidence.spoken_update.strip():
        return ""
    if evidence.provider_turn_finished and not evidence.written_result.strip():
        return ""
    if evidence.tests_status == "not_run" and "passed" in evidence.spoken_update.lower():
        return ""
    return evidence.spoken_update.strip()


def resolve_cartridge_trace(paths: RepoPaths, feature: str) -> CartridgeTrace:
    feature = validate_feature_id(feature)
    manifest_path = paths.cartridge / "manifest.json"
    cartridge_id: str | None = None
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cartridge_id = manifest.get("cartridge_id")
        except (json.JSONDecodeError, OSError):
            cartridge_id = None
    rel_manifest = manifest_path.relative_to(paths.root).as_posix() if manifest_path.is_file() else "cartridge/manifest.json"
    source_map = paths.cartridge / "mappings" / "source-map.json"
    rel_map = source_map.relative_to(paths.root).as_posix() if source_map.is_file() else ""
    spec = paths.root / "docs" / "specs" / feature / "spec.md"
    plan = paths.root / "docs" / "specs" / feature / "plan.md"
    tasks = paths.root / "docs" / "specs" / feature / "tasks.md"
    return CartridgeTrace(
        feature_id=feature,
        cartridge_id=cartridge_id,
        manifest_path=rel_manifest,
        source_map_path=rel_map,
        rosetta_hooks=(
            "planning.rosetta",
            "voice.experience",
            "integration.strategy",
            "agent.handoff",
        ),
        spec_path=spec.relative_to(paths.root).as_posix() if spec.is_file() else "",
        plan_path=plan.relative_to(paths.root).as_posix() if plan.is_file() else "",
        tasks_path=tasks.relative_to(paths.root).as_posix() if tasks.is_file() else "",
    )


def load_state(paths: RepoPaths) -> VoiceBotState:
    path = voice_bot_state_path(paths)
    if not path.is_file():
        return VoiceBotState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise VoiceBotError(f"Could not read voice-bot state: {exc}") from exc
    if not isinstance(data, dict):
        raise VoiceBotError("voice-bot state must be a JSON object")
    state = VoiceBotState.from_dict(data)
    if state.schema_version != SCHEMA_VERSION:
        state.schema_version = SCHEMA_VERSION
    return state


def save_state(paths: RepoPaths, state: VoiceBotState) -> Path:
    """Atomically replace the state file. Unique temp name and a short retry on Windows file locks."""
    dest = voice_bot_state_path(paths)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state.to_dict(), indent=2)
    for attempt in range(10):
        tmp = dest.with_name(f"{dest.name}.{uuid.uuid4().hex[:8]}.tmp")
        tmp.write_text(payload, encoding="utf-8")
        try:
            tmp.replace(dest)
            return dest
        except PermissionError:
            # Another reader holds the destination open (common on Windows); retry briefly.
            tmp.unlink(missing_ok=True)
            if attempt == 9:
                raise
            time.sleep(0.02 * (attempt + 1))
    return dest


def init_voice_session(paths: RepoPaths, feature: str, *, provider_voice: str = "") -> VoiceBotState:
    feature = validate_feature_id(feature)
    trace = resolve_cartridge_trace(paths, feature)
    session = VoiceSession(
        session_id=_new_id("vs"),
        state="active",
        feature_id=feature,
        cartridge_trace=trace,
        provider_voice=provider_voice,
        started_at=_utc_now(),
    )
    state = VoiceBotState(voice_session=session)
    save_state(paths, state)
    return state


def create_context_snapshot(
    paths: RepoPaths,
    state: VoiceBotState,
    snapshot: ContextSnapshot,
) -> ContextSnapshot:
    if state.voice_session is None:
        raise VoiceBotError("No active voice session")
    if not snapshot.snapshot_id:
        snapshot.snapshot_id = _new_id("ctx")
    if state.voice_session.cartridge_trace and snapshot.cartridge_trace is None:
        snapshot.cartridge_trace = state.voice_session.cartridge_trace
    if not snapshot.created_at:
        snapshot.created_at = _utc_now()
    validate_context_snapshot(snapshot, load_voice_bot_config(paths))
    state.context_snapshots[snapshot.snapshot_id] = snapshot
    save_state(paths, state)
    return snapshot


def resolve_cursor_agent_cli() -> dict[str, Any]:
    """Locate the Cursor Agent CLI (`agent`) for G2 / ACP transport (T003)."""
    resolved = shutil.which("agent") or shutil.which("cursor-agent")
    if not resolved and sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            for name in ("agent.cmd", "cursor-agent.cmd", "agent.exe", "cursor-agent.exe"):
                candidate = Path(local) / "cursor-agent" / name
                if candidate.is_file():
                    resolved = str(candidate)
                    break
    if not resolved:
        return {
            "available": False,
            "path": None,
            "version": None,
            "acp_subcommand": False,
        }
    version: str | None = None
    acp_subcommand = False
    try:
        proc = subprocess.run(
            [resolved, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode == 0:
            version = (proc.stdout or proc.stderr or "").strip().splitlines()[0] or None
    except (OSError, subprocess.TimeoutExpired):
        version = None
    try:
        proc = subprocess.run(
            [resolved, "acp", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        acp_subcommand = proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        acp_subcommand = False
    return {
        "available": True,
        "path": resolved,
        "version": version,
        "acp_subcommand": acp_subcommand,
    }


def acp_probe(
    paths: RepoPaths,
    feature: str,
    *,
    agent_path: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Start the Cursor Agent ACP child and send one `initialize` (T003 wiring).

    No model call is made. Failures (missing CLI, disconnect, timeout, remote error)
    raise VoiceBotError so the CLI cannot report success for a failed probe.
    """
    from hive_planner.voice_acp import AcpError, open_agent_acp

    validate_feature_id(feature)
    path = agent_path or resolve_cursor_agent_cli().get("path")
    if not path:
        raise VoiceBotError("Cursor Agent CLI not found; install `agent` or pass agent_path")
    client = open_agent_acp(path, cwd=str(paths.root))
    pid = client.pid
    try:
        result = client.request(
            "initialize",
            {"protocolVersion": 1, "clientCapabilities": {}},
            timeout=timeout,
        )
    except AcpError as exc:
        raise VoiceBotError(f"ACP probe failed: {exc}") from exc
    finally:
        client.close()
    protocol = result.get("protocolVersion") if isinstance(result, dict) else None
    if protocol is None:
        raise VoiceBotError("ACP probe failed: initialize result has no protocolVersion")
    return {
        "ok": True,
        "feature": feature,
        "agent_path": path,
        "pid": pid,
        "protocol_version": protocol,
    }


def status_summary(paths: RepoPaths, feature: str | None = None) -> dict[str, Any]:
    from hive_planner.spec_drift import parse_active_feature

    active = feature or parse_active_feature(paths) or "Voice_Bot"
    try:
        active = validate_feature_id(active)
    except ValueError:
        active = "Voice_Bot"
    trace = resolve_cartridge_trace(paths, active)
    state = load_state(paths)
    session = state.voice_session
    return {
        "schema_version": SCHEMA_VERSION,
        "feature": active,
        "cartridge_id": trace.cartridge_id,
        "spec_ready": bool(trace.spec_path),
        "voice_session": session.state if session else None,
        "voice_session_id": session.session_id if session else None,
        "snapshots": len(state.context_snapshots),
        "tasks": len(state.coding_tasks),
        "state_path": voice_bot_state_path(paths).relative_to(paths.root).as_posix(),
        "cartridge_trace": trace.to_dict(),
        "cursor_agent_cli": resolve_cursor_agent_cli(),
    }
