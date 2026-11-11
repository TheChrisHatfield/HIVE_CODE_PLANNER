"""Voice_Bot contracts — HIVE-owned session, task, context, and evidence (hook: voice.experience)."""

from __future__ import annotations

import fnmatch
import importlib.util
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from hive_planner.config import RepoPaths, validate_feature_id

SCHEMA_VERSION = "voice-bot.v1"
VOICE_BOT_DIR = Path(".hive") / "voice-bot"
VOICE_DEPLOY_PACK_DIR = VOICE_BOT_DIR / "deploy-pack"
VOICE_DEPLOY_PACK_SCHEMA = "voice-deploy-pack.v1"
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

# R18 bounded voice-controller tools. A probe for any other name must fail.
VOICE_CONTROLLER_TOOLS: frozenset[str] = frozenset(
    {
        "submit_coding_task",
        "task_status",
        "task_diff",
        "queue_follow_up",
        "cancel_coding_task",
        "get_context_snapshot",
        "show_diff",
        "navigate_to",
    }
)

# T013: no STT provider is claimed until the evidence register pins one.
STT_PROVIDER: str | None = None
# R19 / G1: native Composer submit is not a public API. ACP is the coding session (T028).
NATIVE_CHAT_PATH = "labeled_acp_fallback"
# T016: Hive does not register an in-chat MCP microphone loop.
IN_CHAT_MCP_MICROPHONE = False
# R30: Voice_Bot deploy extra. Hive core stays dependency-free; `. [voice]` ships Moshi + Pipecat.
VOICE_EXTRA_NAME = "voice"
VOICE_STACK_PYPI: tuple[str, ...] = ("moshi", "pipecat-ai")
VOICE_STACK_MODULES: dict[str, str] = {"moshi": "moshi", "pipecat-ai": "pipecat"}
AGENT_INSTALL_WIN32 = "irm 'https://cursor.com/install?win32=true' | iex"
AGENT_INSTALL_UNIX = "curl https://cursor.com/install -fsS | bash"

_SECRET_NAME_GLOBS: tuple[str, ...] = (".env*", "*.pem", "*.key", "id_rsa*", "credentials*")
_SECRET_CONTENT: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S{16,}"),
)


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
    edits_enabled: bool = False

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "edits_enabled":
                if not isinstance(value, bool):
                    raise VoiceBotError("voice_bot config 'edits_enabled' must be a boolean")
                continue
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
    source_excerpt_ids: tuple[str, ...] = ()

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
            "source_excerpt_ids": list(self.source_excerpt_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CartridgeTrace:
        hooks = data.get("rosetta_hooks") or []
        if not isinstance(hooks, list):
            hooks = []
        excerpts = data.get("source_excerpt_ids") or []
        if not isinstance(excerpts, list):
            excerpts = []
        return cls(
            feature_id=str(data.get("feature_id") or ""),
            cartridge_id=data.get("cartridge_id"),
            manifest_path=str(data.get("manifest_path") or "cartridge/manifest.json"),
            source_map_path=str(data.get("source_map_path") or ""),
            rosetta_hooks=tuple(str(h) for h in hooks),
            spec_path=str(data.get("spec_path") or ""),
            plan_path=str(data.get("plan_path") or ""),
            tasks_path=str(data.get("tasks_path") or ""),
            source_excerpt_ids=tuple(str(item) for item in excerpts if str(item).strip()),
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
    excluded: str = ""  # secret | binary | unsaved | ""
    truncated: bool = False
    file_content: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "snapshot_id": self.snapshot_id,
            "workspace_root": self.workspace_root,
            "file_path": self.file_path,
            "selection_text": self.selection_text,
            "file_content": self.file_content,
            "document_version": self.document_version,
            "dirty": self.dirty,
            "diagnostics": list(self.diagnostics),
            "instruction": self.instruction,
            "created_at": self.created_at or _utc_now(),
            "excluded": self.excluded,
            "truncated": self.truncated,
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
            file_content=str(data.get("file_content") or ""),
            document_version=int(data.get("document_version") or 0),
            dirty=bool(data.get("dirty")),
            diagnostics=[str(d) for d in diags],
            instruction=str(data.get("instruction") or ""),
            cartridge_trace=trace,
            created_at=str(data.get("created_at") or ""),
            excluded=str(data.get("excluded") or ""),
            truncated=bool(data.get("truncated")),
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
    prior_state: str = ""  # last non-unknown state, for R26 reconnect

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
            "prior_state": self.prior_state,
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
            prior_state=str(data.get("prior_state") or ""),
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
    # Editor adapter commands (R18 navigate_to / show_diff). Queued until the extension acks.
    editor_actions: list[dict[str, Any]] = field(default_factory=list)

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
            "editor_actions": list(self.editor_actions),
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
        editor_raw = data.get("editor_actions") or []
        return cls(
            schema_version=version,
            voice_session=voice_session,
            context_snapshots=snapshots,
            coding_tasks=tasks,
            queue=[q for q in queue_raw if isinstance(q, dict)] if isinstance(queue_raw, list) else [],
            dedupe=dict(dedupe_raw) if isinstance(dedupe_raw, dict) else {},
            editor_actions=[row for row in editor_raw if isinstance(row, dict)] if isinstance(editor_raw, list) else [],
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
    if len(snapshot.file_content.encode("utf-8")) > cfg.snapshot_max_bytes:
        raise VoiceBotError("file_content exceeds configured limit")


def g6_register_pass(paths: RepoPaths) -> bool:
    """True only when the G6 evidence-register result cell is pass (R33)."""
    path = evidence_register_path(paths)
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        if not line.startswith("| G6 |"):
            continue
        cells = line.split("|")
        if len(cells) < 6:
            return False
        cell = cells[5].strip().strip("*").casefold()
        return cell == "pass"
    return False


def edits_enabled(paths: RepoPaths | None = None) -> bool:
    """R33: G6 register pass and config edits_enabled true. Missing either stays off (T015)."""
    if paths is None:
        return False
    cfg = load_voice_bot_config(paths)
    return bool(cfg.edits_enabled) and g6_register_pass(paths)


def hybrid_speech_path() -> str:
    """T013: typed instruction until an STT provider is pinned in the evidence register."""
    return "typed_instruction" if not STT_PROVIDER else "stt"


def native_chat_path() -> str:
    """T028 / R19: labeled ACP coding session until all four G1 questions pass on a pinned native API."""
    return NATIVE_CHAT_PATH


def _module_installed(name: str) -> bool:
    """True when this Python already has the module (from `. [voice]` or a prior install)."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def agent_install_command() -> str:
    return AGENT_INSTALL_WIN32 if sys.platform == "win32" else AGENT_INSTALL_UNIX


def voice_runtime_plan() -> dict[str, Any]:
    """What a self-contained Voice_Bot deploy must install (R30). Does not run pip."""
    agent = resolve_cursor_agent_cli()
    pip_items = []
    for pypi_name in VOICE_STACK_PYPI:
        module = VOICE_STACK_MODULES[pypi_name]
        present = _module_installed(module)
        pip_items.append(
            {
                "package": pypi_name,
                "module": module,
                "installed": present,
                "action": "skip" if present else "pip_install",
            }
        )
    agent_present = bool(agent.get("available"))
    return {
        "extra": VOICE_EXTRA_NAME,
        "pip_install": f'py -3.11 -m pip install -e ".[{VOICE_EXTRA_NAME}]"',
        "packages": pip_items,
        "cursor_agent_cli": {
            "installed": agent_present,
            "path": agent.get("path"),
            "version": agent.get("version"),
            "action": "skip" if agent_present else "official_installer",
            "command": agent_install_command(),
        },
        "speech_path": hybrid_speech_path(),
        "native_chat_path": native_chat_path(),
    }


def ensure_voice_runtime(*, install: bool = False, install_agent: bool = False) -> dict[str, Any]:
    """Install the Hive voice extra into this Python. Optionally run the official Cursor CLI installer.

    Dry-run (`install=False`) is the default. `--install` runs pip for missing Moshi/Pipecat only.
    Moshi still does not pin STT until G3 evidence exists; typed path stays until then.
    """
    plan = voice_runtime_plan()
    results: list[dict[str, Any]] = []
    if install:
        missing = [row["package"] for row in plan["packages"] if row["action"] == "pip_install"]
        if missing:
            cmd = [sys.executable, "-m", "pip", "install", *missing]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            results.append(
                {
                    "step": "pip_install",
                    "packages": missing,
                    "ok": proc.returncode == 0,
                    "returncode": proc.returncode,
                }
            )
            plan = voice_runtime_plan()
        else:
            results.append({"step": "pip_install", "packages": [], "ok": True, "returncode": 0})
        if install_agent and plan["cursor_agent_cli"]["action"] == "official_installer":
            if sys.platform == "win32":
                agent_cmd = ["powershell", "-NoProfile", "-Command", AGENT_INSTALL_WIN32]
            else:
                agent_cmd = ["bash", "-lc", AGENT_INSTALL_UNIX]
            proc = subprocess.run(agent_cmd, capture_output=True, text=True, check=False)
            results.append(
                {
                    "step": "agent_install",
                    "ok": proc.returncode == 0,
                    "returncode": proc.returncode,
                }
            )
            plan = voice_runtime_plan()
    overall_ok = all(step.get("ok", True) for step in results) if install else True
    return {"ok": overall_ok, "installed": install, "plan": plan, "steps": results}


def _voice_pack_install_md(repo_root: Path, output_dir: Path, *, wheels: bool) -> str:
    try:
        rel_pack = str(output_dir.relative_to(repo_root.resolve()))
    except ValueError:
        rel_pack = str(output_dir)
    offline = (
        f'py -3.11 -m pip install --no-index --find-links "{output_dir / "wheels"}" -e ".[{VOICE_EXTRA_NAME}]"'
        if wheels
        else ""
    )
    lines = [
        "# Voice_Bot deploy pack (R30)",
        "",
        "Copy the Hive Code Planner repo **and** this pack folder to the target machine.",
        "",
        "## Online target (PyPI reachable)",
        "",
        "```text",
        "cd <hive-repo>",
        f'py -3.11 -m pip install -e ".[{VOICE_EXTRA_NAME}]"',
        "py -3.11 -m hive_planner voice-bot ensure-runtime --install",
        "py -3.11 -m hive_planner voice-bot ensure-runtime --install --install-agent",
        "```",
        "",
    ]
    if wheels:
        lines.extend(
            [
                "## Offline target (wheels included)",
                "",
                "```text",
                "cd <hive-repo>",
                offline,
                "py -3.11 -m hive_planner voice-bot ensure-runtime",
                "```",
                "",
                "`ensure-runtime` without `--install` only reports missing pieces when wheels already satisfied pip.",
                "",
            ]
        )
    lines.extend(
        [
            f"Pack folder: `{rel_pack}`",
            "",
            "Cursor `agent` is not a PyPI wheel; use `ensure-runtime --install --install-agent` on first setup.",
            "Editor adapter: install `extensions/hive-voice-bot/` in Cursor/VS Code separately.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_voice_deploy_pack(
    repo_root: Path,
    output_dir: Path | None = None,
    *,
    download_wheels: bool = False,
) -> dict[str, Any]:
    """Write a portable Voice_Bot pack (manifest + install doc) for other machines (R30)."""
    from hive_planner import __version__ as hive_version

    root = repo_root.resolve()
    out = (output_dir or (root / VOICE_DEPLOY_PACK_DIR)).resolve()
    out.mkdir(parents=True, exist_ok=True)
    plan = voice_runtime_plan()
    wheels_dir = out / "wheels"
    steps: list[dict[str, Any]] = []

    req_path = out / "requirements-voice.txt"
    req_path.write_text("\n".join(VOICE_STACK_PYPI) + "\n", encoding="utf-8")

    if download_wheels:
        wheels_dir.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-m", "pip", "download", "-d", str(wheels_dir), *VOICE_STACK_PYPI]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        steps.append(
            {
                "step": "pip_download",
                "packages": list(VOICE_STACK_PYPI),
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
            }
        )
        if proc.returncode != 0:
            return {
                "ok": False,
                "output_dir": str(out),
                "steps": steps,
                "stderr": (proc.stderr or "")[-2000:],
            }

    wheel_names = sorted(p.name for p in wheels_dir.glob("*")) if wheels_dir.is_dir() else []
    offline_cmd = (
        f'py -3.11 -m pip install --no-index --find-links "{wheels_dir}" -e ".[{VOICE_EXTRA_NAME}]"'
        if wheel_names
        else None
    )
    manifest: dict[str, Any] = {
        "schema": VOICE_DEPLOY_PACK_SCHEMA,
        "hive_planner_version": hive_version,
        "repo_root_hint": str(root),
        "extra": VOICE_EXTRA_NAME,
        "packages": list(VOICE_STACK_PYPI),
        "runtime_plan": plan,
        "wheels": wheel_names,
        "target_install": {
            "online_pip": plan["pip_install"],
            "offline_pip": offline_cmd,
            "ensure_runtime": "py -3.11 -m hive_planner voice-bot ensure-runtime --install",
            "ensure_agent": "py -3.11 -m hive_planner voice-bot ensure-runtime --install --install-agent",
        },
        "pack_command": "py -3.11 -m hive_planner voice-bot pack --download-wheels",
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    install_path = out / "INSTALL.md"
    install_path.write_text(
        _voice_pack_install_md(root, out, wheels=bool(wheel_names)),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "output_dir": str(out),
        "manifest": str(manifest_path),
        "install_doc": str(install_path),
        "requirements": str(req_path),
        "wheels_dir": str(wheels_dir) if wheel_names else None,
        "wheel_count": len(wheel_names),
        "download_wheels": download_wheels,
        "steps": steps,
    }


def probe_optional_voice_providers() -> dict[str, Any]:
    """Report declared voice-stack packages and whether this deploy already installed them (R30)."""
    plan = voice_runtime_plan()
    moshi = next(row for row in plan["packages"] if row["package"] == "moshi")
    pipecat = next(row for row in plan["packages"] if row["package"] == "pipecat-ai")
    agent = plan["cursor_agent_cli"]
    return {
        "hive_ships_these": True,
        "extra": VOICE_EXTRA_NAME,
        "speech_path": plan["speech_path"],
        "moshi": {"declared": True, "installed": moshi["installed"], "source": "hive_voice_extra"},
        "pipecat": {"declared": True, "installed": pipecat["installed"], "source": "hive_voice_extra"},
        "cursor_agent_cli": {
            "declared": True,
            "installed": agent["installed"],
            "path": agent["path"],
            "version": agent["version"],
            "source": "hive_voice_ensure_runtime",
            "command": agent["command"],
        },
    }


def latency_meets_target(elapsed_ms: int, target_ms: int | None) -> bool:
    """R24: a missing target is not a product claim. A set target must change this check."""
    if target_ms is None:
        return True
    return elapsed_ms <= target_ms


def event_delta_ms(events: list[dict[str, Any]], start_name: str, end_name: str) -> int | None:
    """Elapsed milliseconds between two named task events, or None if either is missing."""
    start_at = next((e.get("at") for e in events if e.get("name") == start_name), None)
    end_at = next((e.get("at") for e in events if e.get("name") == end_name), None)
    if not start_at or not end_at:
        return None
    try:
        start = datetime.fromisoformat(str(start_at).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(end_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((end - start).total_seconds() * 1000))


def buffers_match(snapshot: ContextSnapshot, live_version: int, live_dirty: bool) -> bool:
    return snapshot.document_version == live_version and snapshot.dirty is live_dirty


def _basename(file_path: str) -> str:
    return Path(str(file_path).replace("\\", "/")).name


def secret_filename(file_path: str) -> bool:
    name = _basename(file_path)
    return any(fnmatch.fnmatch(name, glob) for glob in _SECRET_NAME_GLOBS)


def secret_content(text: str) -> bool:
    return any(pat.search(text or "") for pat in _SECRET_CONTENT)


def _clear_snapshot_payload(snapshot: ContextSnapshot) -> None:
    snapshot.selection_text = ""
    snapshot.file_content = ""


def apply_snapshot_exclusions(snapshot: ContextSnapshot, *, content: str | None = None) -> ContextSnapshot:
    """Clear payload and set `excluded` (R2, R28). Never send secret, binary, or unsaved bytes."""
    text = snapshot.selection_text if content is None else content
    blob = "\n".join(part for part in (text, snapshot.file_content, content or "") if part)
    if snapshot.dirty:
        snapshot.excluded = "unsaved"
        _clear_snapshot_payload(snapshot)
        return snapshot
    if "\x00" in blob:
        snapshot.excluded = "binary"
        _clear_snapshot_payload(snapshot)
        return snapshot
    if secret_filename(snapshot.file_path) or secret_content(blob):
        snapshot.excluded = "secret"
        _clear_snapshot_payload(snapshot)
        return snapshot
    return snapshot


def map_editor_snapshot(editor: dict[str, Any], *, instruction: str, workspace_root: str) -> ContextSnapshot:
    """Map the T007 editor object onto HIVE `ContextSnapshot.selection_text` (T008, R2)."""
    selection = editor.get("selection")
    text = ""
    truncated = False
    if isinstance(selection, dict):
        text = str(selection.get("text") or "")
        truncated = bool(selection.get("truncated"))
    elif isinstance(selection, str):
        text = selection
    diags_raw = editor.get("diagnostics") or []
    diags: list[str] = []
    if isinstance(diags_raw, list):
        for item in diags_raw:
            if isinstance(item, dict):
                diags.append(f"{item.get('severity', '')}: {item.get('message', '')}".strip(": "))
            else:
                diags.append(str(item))
    file_path = str(editor.get("file") or "")
    reason = str(editor.get("reason") or "")
    if reason == "no_active_file":
        file_path = ""
    file_content = str(editor.get("file_content") or "")
    truncated = truncated or bool(editor.get("file_truncated")) or bool(editor.get("diagnostics_truncated"))
    snap = ContextSnapshot(
        workspace_root=workspace_root,
        file_path=file_path,
        selection_text=text,
        file_content=file_content,
        document_version=int(editor.get("document_version") or 0),
        dirty=bool(editor.get("dirty")),
        instruction=instruction,
        diagnostics=diags,
        truncated=truncated,
    )
    return apply_snapshot_exclusions(snap)


class VoiceAdapter:
    """Replaceable speech adapter. HIVE contracts do not depend on the concrete class (R11)."""

    name = "base"
    cancel_on_interruption = False

    def transcribe(self, audio: bytes) -> str:
        raise VoiceBotError("stt_unavailable")

    def speak(self, text: str) -> dict[str, Any]:
        """Play or record a spoken update. Typed path must not emit audio (R32)."""
        raise VoiceBotError("tts_unavailable")


class TypedInstructionAdapter(VoiceAdapter):
    name = "typed"

    def transcribe(self, audio: bytes) -> str:
        raise VoiceBotError("stt_unavailable")

    def speak(self, text: str) -> dict[str, Any]:
        return {"played": False, "audio": False, "text": str(text or ""), "path": "typed"}


class SecondStubAdapter(VoiceAdapter):
    name = "stub2"

    def transcribe(self, audio: bytes) -> str:
        raise VoiceBotError("stt_unavailable")

    def speak(self, text: str) -> dict[str, Any]:
        return {"played": False, "audio": False, "text": str(text or ""), "path": "stub2"}


class PipecatVoiceAdapter(VoiceAdapter):
    """Pipecat-backed playback. Coding cancel stays independent of interruption (R13, R32)."""

    name = "pipecat"
    cancel_on_interruption = False

    def speak(self, text: str) -> dict[str, Any]:
        if not _module_installed("pipecat"):
            raise VoiceBotError("pipecat_unavailable")
        return {
            "played": False,
            "audio": False,
            "text": str(text or ""),
            "path": "pipecat",
            "cancel_on_interruption": self.cancel_on_interruption,
        }


def pipecat_cancel_on_interruption() -> bool | None:
    """R13 equivalent. None when Pipecat is not importable; False when the adapter is used."""
    if not _module_installed("pipecat"):
        return None
    return PipecatVoiceAdapter.cancel_on_interruption


def adapter_contract_names() -> tuple[str, ...]:
    return ("session", "task", "permission", "evidence")


def grounded_spoken_update(evidence: TaskEvidence) -> str:
    """Return spoken_update only when it is backed by recorded evidence."""
    if not evidence.spoken_update.strip():
        return ""
    if evidence.provider_turn_finished and not evidence.written_result.strip():
        return ""
    if evidence.tests_status == "not_run" and "passed" in evidence.spoken_update.lower():
        return ""
    return evidence.spoken_update.strip()


def load_source_excerpt_ids(paths: RepoPaths) -> tuple[str, ...]:
    """Ids from `cartridge/mappings/source-map.json` (R2). Missing map → empty, never invented."""
    source_map = paths.cartridge / "mappings" / "source-map.json"
    if not source_map.is_file():
        return ()
    try:
        data = json.loads(source_map.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ()
    rows = data.get("mappings") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return ()
    ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        layer = str(row.get("layer") or "source").strip()
        cartridge = str(row.get("cartridge") or "").strip()
        if not cartridge:
            continue
        excerpt_id = f"{layer}:{cartridge}"
        if excerpt_id in seen:
            continue
        seen.add(excerpt_id)
        ids.append(excerpt_id)
    return tuple(ids)


_PLANNING_MARKERS: tuple[tuple[str, str], ...] = (
    ("acceptance criteria", "acceptance"),
    ("current spec", "spec"),
    ("active spec", "spec"),
    ("what does the spec", "spec"),
    ("current plan", "plan"),
    ("active plan", "plan"),
    ("current tasks", "tasks"),
)


def is_planning_question(text: str) -> bool:
    """US5 / SC-009: questions that must be answered from Spec Kit artifacts, not invented."""
    lowered = (text or "").lower()
    return any(marker in lowered for marker, _kind in _PLANNING_MARKERS)


def _extract_markdown_section(markdown: str, heading: str) -> str:
    lines = markdown.splitlines()
    start = None
    start_level = 0
    wanted = heading.lower()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") and wanted in stripped.lower():
            start = index
            start_level = len(stripped) - len(stripped.lstrip("#"))
            break
    if start is None:
        return markdown.strip()
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            if level <= start_level:
                end = index
                break
    return "\n".join(lines[start:end]).strip()


def answer_planning_question(paths: RepoPaths, feature: str, instruction: str) -> dict[str, str]:
    """Return written text copied from spec/plan/tasks. Never synthesizes requirements (SC-009)."""
    feature = validate_feature_id(feature)
    lowered = (instruction or "").lower()
    kind = "spec"
    for marker, mapped in _PLANNING_MARKERS:
        if marker in lowered:
            kind = mapped
            break
    rel = {
        "acceptance": f"docs/specs/{feature}/spec.md",
        "spec": f"docs/specs/{feature}/spec.md",
        "plan": f"docs/specs/{feature}/plan.md",
        "tasks": f"docs/specs/{feature}/tasks.md",
    }[kind]
    path = paths.root / rel
    if not path.is_file():
        return {
            "source_path": rel,
            "written": f"No {rel} is on disk. Nothing was invented.",
        }
    try:
        body = path.read_text(encoding="utf-8")
    except OSError:
        return {
            "source_path": rel,
            "written": f"{rel} could not be read. Nothing was invented.",
        }
    excerpt = _extract_markdown_section(body, "Acceptance criteria") if kind == "acceptance" else body.strip()
    return {"source_path": rel, "written": f"From {rel}:\n\n{excerpt}"}


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
        source_excerpt_ids=load_source_excerpt_ids(paths),
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
    cfg = load_voice_bot_config(paths)
    if not snapshot.file_content and snapshot.file_path and not snapshot.dirty:
        candidate = (paths.root / snapshot.file_path).resolve()
        try:
            candidate.relative_to(paths.root.resolve())
        except ValueError:
            candidate = None
        if candidate is not None and candidate.is_file():
            try:
                raw_file = candidate.read_bytes()
            except OSError:
                raw_file = b""
            if b"\x00" in raw_file:
                snapshot.file_content = ""
                snapshot.excluded = snapshot.excluded or "binary"
            else:
                text = raw_file.decode("utf-8", errors="replace")
                if len(raw_file) > cfg.snapshot_max_bytes:
                    snapshot.file_content = raw_file[: cfg.snapshot_max_bytes].decode("utf-8", errors="ignore")
                    snapshot.truncated = True
                else:
                    snapshot.file_content = text
    apply_snapshot_exclusions(snapshot)
    for field_name in ("selection_text", "file_content"):
        value = getattr(snapshot, field_name)
        raw = value.encode("utf-8")
        if len(raw) > cfg.snapshot_max_bytes:
            setattr(snapshot, field_name, raw[: cfg.snapshot_max_bytes].decode("utf-8", errors="ignore"))
            snapshot.truncated = True
    validate_context_snapshot(snapshot, cfg)
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


_FIXTURE_AGENT_MARKERS: tuple[str, ...] = (
    "acp_turn_server.py",
    "acp_fake_server.py",
    "tests/fixtures/",
    "tests\\fixtures\\",
)


def is_fixture_agent_path(agent_path: str) -> bool:
    """True when the child is a test fixture, which must never write G2 or G6 pass (R31, R34)."""
    lowered = str(agent_path or "").replace("\\", "/").casefold()
    return any(marker.replace("\\", "/").casefold() in lowered for marker in _FIXTURE_AGENT_MARKERS)


def cursor_agent_login_state(*, agent_path: str | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Logged-in iff `CURSOR_API_KEY` is set or `agent status` is not 'Not logged in' (R31)."""
    environ = env if env is not None else os.environ
    if str(environ.get("CURSOR_API_KEY") or "").strip():
        return {"logged_in": True, "source": "CURSOR_API_KEY", "raw": "CURSOR_API_KEY"}
    path = agent_path or resolve_cursor_agent_cli().get("path")
    if not path:
        return {"logged_in": False, "source": "missing_cli", "raw": ""}
    try:
        proc = subprocess.run(
            [str(path), "status"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        raw = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"logged_in": False, "source": "status_error", "raw": str(exc)}
    lowered = raw.lower()
    if "not logged in" in lowered:
        return {"logged_in": False, "source": "agent_status", "raw": raw[:2000]}
    if "logged in" in lowered:
        return {"logged_in": True, "source": "agent_status", "raw": raw[:2000]}
    return {"logged_in": False, "source": "agent_status", "raw": raw[:2000]}


def evidence_register_path(paths: RepoPaths) -> Path:
    return paths.root / "docs" / "specs" / "Voice_Bot" / "evidence-register.md"


def apply_g2_register_result(text: str, result: str, date: str, note: str) -> str:
    """Replace the G2 table result cell. Other rows are unchanged."""
    if result not in ("pass", "fail", "blocked"):
        raise VoiceBotError(f"invalid G2 result {result}")
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("| G2 |"):
            cells = line.rstrip("\n").split("|")
            if len(cells) >= 8:
                cells[5] = f" **{result}** "
                cells[6] = f" {date} "
                cells[7] = f" {note.replace('|', '/')} "
                line = "|".join(cells) + "\n"
        lines.append(line)
    return "".join(lines)


def record_g2_evidence(paths: RepoPaths, result: str, note: str) -> Path:
    path = evidence_register_path(paths)
    if not path.is_file():
        raise VoiceBotError(f"evidence register missing: {path}")
    updated = apply_g2_register_result(path.read_text(encoding="utf-8"), result, _utc_now()[:10], note)
    path.write_text(updated, encoding="utf-8")
    return path


def live_prompt(
    paths: RepoPaths,
    feature: str,
    *,
    agent_path: str | None = None,
    timeout: float = 60.0,
    instruction: str = "Read-only G2 probe. Do not modify files.",
    record: bool = False,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """One live `session/prompt`. Fixture paths and logged-out CLI never write G2 pass (R31)."""
    from hive_planner.voice_acp import AcpError, open_agent_acp

    validate_feature_id(feature)
    path = agent_path or resolve_cursor_agent_cli().get("path")
    login = cursor_agent_login_state(agent_path=path, env=env)
    fixture = is_fixture_agent_path(str(path or ""))
    payload: dict[str, Any] = {
        "ok": False,
        "g2": "blocked",
        "feature": feature,
        "agent_path": path,
        "login": login,
        "fixture": fixture,
        "recorded": False,
        "reason": "",
        "stop_reason": "",
    }

    def maybe_record(result: str, note: str) -> None:
        if result == "pass" and fixture:
            raise VoiceBotError("fixture agent must not write G2 pass")
        if result == "pass" and not login["logged_in"]:
            raise VoiceBotError("logged-out agent must not write G2 pass")
        if record:
            record_g2_evidence(paths, result, note)
            payload["recorded"] = True

    if fixture:
        payload["reason"] = "fixture_agent"
        maybe_record("blocked", "fixture path refused (R31)")
        return payload
    if not path:
        payload["reason"] = "missing_cli"
        maybe_record("blocked", "Cursor Agent CLI not found")
        return payload
    if not login["logged_in"]:
        payload["reason"] = "not_logged_in"
        maybe_record("blocked", f"not logged in ({login['source']})")
        return payload

    def handler(method: str, params: Any) -> Any:
        if method == "session/request_permission":
            return {"outcome": {"outcome": "cancelled"}}
        if method in _FS_READ_METHODS:
            return _read_workspace_text(paths.root, params)
        if method in _FS_WRITE_METHODS or method.startswith("terminal/") or method in _PLAN_METHODS:
            raise VoiceBotError("g2_write_cancelled")
        return None

    client = open_agent_acp(path, cwd=str(paths.root), server_request_handler=handler)
    try:
        client.request("initialize", {"protocolVersion": 1, "clientCapabilities": {}}, timeout=timeout)
        created = client.request("session/new", {"cwd": str(paths.root), "mcpServers": []}, timeout=timeout)
        session_id = created.get("sessionId") if isinstance(created, dict) else None
        if not session_id:
            raise VoiceBotError("session/new returned no sessionId")
        client.request("session/set_mode", {"sessionId": session_id, "modeId": "ask"}, timeout=timeout)
        prompt = client.request(
            "session/prompt",
            {"sessionId": session_id, "prompt": [{"type": "text", "text": instruction}]},
            timeout=timeout,
        )
        stop = prompt.get("stopReason") if isinstance(prompt, dict) else ""
        payload["ok"] = True
        payload["g2"] = "pass"
        payload["reason"] = "live_prompt"
        payload["stop_reason"] = str(stop or "")
        maybe_record("pass", f"live session/prompt stopReason={payload['stop_reason']}")
        return payload
    except (AcpError, VoiceBotError, OSError) as exc:
        payload["g2"] = "fail"
        payload["reason"] = str(exc)
        maybe_record("fail", str(exc)[:200])
        return payload
    finally:
        client.close()


def apply_g6_register_result(text: str, result: str, date: str, note: str) -> str:
    """Replace the G6 claims-table result cell. Other rows are unchanged."""
    if result not in ("pass", "fail", "blocked"):
        raise VoiceBotError(f"invalid G6 result {result}")
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("| G6 |"):
            cells = line.rstrip("\n").split("|")
            if len(cells) >= 8:
                cells[5] = f" **{result}** "
                cells[6] = f" {date} "
                cells[7] = f" {note.replace('|', '/')} "
                line = "|".join(cells) + "\n"
            elif len(cells) >= 4:
                closed = " **Yes** " if result == "pass" else " No "
                cells[2] = closed
                if len(cells) >= 4:
                    cells[3] = f" {note.replace('|', '/')[:180]} "
                line = "|".join(cells) + "\n"
        lines.append(line)
    return "".join(lines)


def record_g6_evidence(paths: RepoPaths, result: str, note: str) -> Path:
    path = evidence_register_path(paths)
    if not path.is_file():
        raise VoiceBotError(f"evidence register missing: {path}")
    updated = apply_g6_register_result(path.read_text(encoding="utf-8"), result, _utc_now()[:10], note)
    path.write_text(updated, encoding="utf-8")
    return path


def summarize_permission_params(params: Any) -> dict[str, Any]:
    """Keep a small, non-secret view of a live session/request_permission payload."""
    if not isinstance(params, dict):
        return {"type": type(params).__name__}
    options = params.get("options") or []
    option_kinds: list[str] = []
    option_ids: list[str] = []
    if isinstance(options, list):
        for opt in options[:8]:
            if isinstance(opt, dict):
                option_kinds.append(str(opt.get("kind") or "")[:80])
                option_ids.append(str(opt.get("optionId") or "")[:80])
    tool = params.get("toolCall") if isinstance(params.get("toolCall"), dict) else {}
    return {
        "param_keys": sorted(str(k) for k in params.keys()),
        "kind": str(params.get("kind") or ""),
        "option_kinds": option_kinds,
        "option_ids": option_ids,
        "tool_kind": str(tool.get("kind") or ""),
        "tool_title": str(tool.get("title") or "")[:120],
    }


def permission_shape_ok(summary: dict[str, Any]) -> bool:
    """True when the live payload is a permission, fs write, or terminal create (R34)."""
    method = str(summary.get("method") or "").casefold()
    if method in ("fs/write_text_file", "fs/writetextfile") or method.startswith("terminal/"):
        return True
    if method == "cursor/create_plan":
        return True
    keys = summary.get("param_keys") or []
    return "options" in keys or "toolCall" in keys


LIVE_PERMISSION_PROBE_REL = Path(".hive") / "voice-bot" / "g6-live-probe.tmp"
LIVE_PERMISSION_INSTRUCTION = (
    "G6 permission probe. Create a new file at .hive/voice-bot/g6-live-probe.tmp "
    "containing the word probe. The client will cancel every permission request. "
    "Do not write if permission is cancelled."
)

ACP_G6_INITIALIZE = {
    "protocolVersion": 1,
    "clientInfo": {"name": "hive-voice-bot-g6", "version": "1"},
    "clientCapabilities": {
        "fs": {"readTextFile": True, "writeTextFile": True},
        "terminal": True,
    },
}

_FS_WRITE_METHODS = frozenset({"fs/write_text_file", "fs/writeTextFile"})
_FS_READ_METHODS = frozenset({"fs/read_text_file", "fs/readTextFile"})
_PLAN_METHODS = frozenset({"cursor/create_plan"})
_READ_CAP_BYTES = 64 * 1024


def _g6_gate_summary(method: str, params: Any) -> dict[str, Any]:
    summary = summarize_permission_params(params)
    summary["method"] = method
    return summary


def reject_permission_result(params: Any) -> dict[str, Any]:
    """Select the live ACP reject option when present; otherwise cancel (R34)."""
    options = params.get("options") if isinstance(params, dict) else None
    if isinstance(options, list):
        for opt in options:
            if not isinstance(opt, dict):
                continue
            oid = str(opt.get("optionId") or "")
            kind = str(opt.get("kind") or "")
            blob = f"{oid} {kind}".casefold()
            if "reject" in blob or "deny" in blob or "cancel" in blob:
                return {"outcome": {"outcome": "selected", "optionId": oid or kind or "reject_once"}}
    return {"outcome": {"outcome": "cancelled"}}


def _read_workspace_text(root: Path, params: Any) -> dict[str, str]:
    if not isinstance(params, dict):
        raise VoiceBotError("fs_read_invalid")
    raw = str(params.get("path") or "")
    if not raw:
        raise VoiceBotError("fs_read_missing_path")
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    try:
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        raise VoiceBotError("fs_read_outside_workspace") from None
    if not resolved.is_file():
        raise VoiceBotError("fs_read_missing")
    data = resolved.read_bytes()[:_READ_CAP_BYTES]
    return {"content": data.decode("utf-8", errors="replace")}


def live_permission(
    paths: RepoPaths,
    feature: str,
    *,
    agent_path: str | None = None,
    timeout: float = 120.0,
    instruction: str = LIVE_PERMISSION_INSTRUCTION,
    record: bool = False,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """One live ACP session that must observe session/request_permission (R34). Always cancel."""
    from hive_planner.voice_acp import AcpDisconnected, AcpError, open_agent_acp

    validate_feature_id(feature)
    path = agent_path or resolve_cursor_agent_cli().get("path")
    login = cursor_agent_login_state(agent_path=path, env=env)
    fixture = is_fixture_agent_path(str(path or ""))
    seen: list[dict[str, Any]] = []
    payload: dict[str, Any] = {
        "ok": False,
        "g6": "blocked",
        "feature": feature,
        "agent_path": path,
        "login": login,
        "fixture": fixture,
        "recorded": False,
        "reason": "",
        "stop_reason": "",
        "mode": "",
        "permissions": seen,
        "wrote": False,
    }

    def maybe_record(result: str, note: str) -> None:
        if result == "pass" and fixture:
            raise VoiceBotError("fixture agent must not write G6 pass")
        if result == "pass" and not login["logged_in"]:
            raise VoiceBotError("logged-out agent must not write G6 pass")
        if record:
            record_g6_evidence(paths, result, note)
            payload["recorded"] = True

    if fixture:
        payload["reason"] = "fixture_agent"
        maybe_record("blocked", "fixture path refused (R34)")
        return payload
    if not path:
        payload["reason"] = "missing_cli"
        maybe_record("blocked", "Cursor Agent CLI not found")
        return payload
    if not login["logged_in"]:
        payload["reason"] = "not_logged_in"
        maybe_record("blocked", f"not logged in ({login['source']})")
        return payload

    gated_event = threading.Event()
    watchdog_stop = threading.Event()
    session_holder: dict[str, str] = {"id": ""}

    def handler(method: str, params: Any) -> Any:
        if method == "session/request_permission":
            seen.append(_g6_gate_summary(method, params))
            gated_event.set()
            return reject_permission_result(params)
        if method in _PLAN_METHODS:
            seen.append(_g6_gate_summary(method, params))
            gated_event.set()
            return {"outcome": {"outcome": "cancelled"}}
        if method in _FS_WRITE_METHODS or method.startswith("terminal/"):
            seen.append(_g6_gate_summary(method, params))
            gated_event.set()
            raise VoiceBotError("g6_write_cancelled")
        if method in _FS_READ_METHODS:
            return _read_workspace_text(paths.root, params)
        payload.setdefault("server_methods", []).append(method)
        raise VoiceBotError(f"g6_method_refused:{method}")

    def stop_after_gate() -> None:
        gated_event.wait(timeout)
        if watchdog_stop.is_set() or not gated_event.is_set():
            return
        time.sleep(0.05)
        sid = session_holder["id"]
        try:
            if sid:
                client.notify("session/cancel", {"sessionId": sid})
        except (AcpDisconnected, OSError):
            pass
        deadline = time.monotonic() + 0.4
        while time.monotonic() < deadline and not probe_wrote():
            time.sleep(0.05)
        try:
            client.terminate()
        except OSError:
            pass

    def collect_updates() -> None:
        kinds: list[str] = []
        while True:
            try:
                item = client.notifications.get_nowait()
            except queue.Empty:
                break
            if not item:
                continue
            if item.get("method") != "session/update":
                kinds.append(str(item.get("method") or ""))
                continue
            upd = (item.get("params") or {}).get("update") or {}
            if isinstance(upd, dict):
                kinds.append(str(upd.get("sessionUpdate") or "session/update"))
        payload["update_kinds"] = [k for k in kinds if k][:24]

    def probe_wrote() -> bool:
        return (paths.root / LIVE_PERMISSION_PROBE_REL).is_file()

    def finish_pass(stop: str, extra: str = "") -> dict[str, Any]:
        payload["ok"] = True
        payload["g6"] = "pass"
        payload["reason"] = "live_permission"
        payload["stop_reason"] = str(stop or "")
        payload["wrote"] = False
        methods = ",".join(sorted({str(item.get("method") or "session/request_permission") for item in seen}))
        note = f"live gate {methods} n={len(seen)} stopReason={payload['stop_reason']}"
        if extra:
            note = f"{note} {extra}"[:200]
        maybe_record("pass", note)
        return payload

    leftover = paths.root / LIVE_PERMISSION_PROBE_REL
    if leftover.is_file():
        leftover.unlink()
    client = open_agent_acp(path, cwd=str(paths.root), server_request_handler=handler)
    watcher = threading.Thread(target=stop_after_gate, name="g6-stop-after-gate", daemon=True)
    try:
        watcher.start()
        client.request("initialize", ACP_G6_INITIALIZE, timeout=timeout)
        created = client.request("session/new", {"cwd": str(paths.root), "mcpServers": []}, timeout=timeout)
        session_id = created.get("sessionId") if isinstance(created, dict) else None
        if not session_id:
            raise VoiceBotError("session/new returned no sessionId")
        session_holder["id"] = str(session_id)
        try:
            client.request(
                "session/set_mode",
                {"sessionId": session_id, "modeId": "agent"},
                timeout=timeout,
            )
            payload["mode"] = "agent"
        except (AcpError, VoiceBotError):
            payload["mode"] = "default"
        if seen and any(permission_shape_ok(item) for item in seen) and not probe_wrote():
            collect_updates()
            return finish_pass("", extra="from set_mode")
        prompt = client.request(
            "session/prompt",
            {"sessionId": session_id, "prompt": [{"type": "text", "text": instruction}]},
            timeout=timeout,
        )
        stop = prompt.get("stopReason") if isinstance(prompt, dict) else ""
        collect_updates()
        wrote = probe_wrote()
        payload["wrote"] = wrote
        payload["stop_reason"] = str(stop or "")
        gated = seen and any(permission_shape_ok(item) for item in seen)
        if gated and not wrote:
            return finish_pass(str(stop or ""))
        payload["g6"] = "fail"
        payload["reason"] = "unguarded_write" if wrote else "no_permission_request"
        maybe_record("fail", f"{payload['reason']} stopReason={payload['stop_reason']}")
        return payload
    except (AcpError, VoiceBotError, OSError) as exc:
        collect_updates()
        wrote = probe_wrote()
        payload["wrote"] = wrote
        gated = seen and any(permission_shape_ok(item) for item in seen)
        if gated and not wrote:
            return finish_pass("", extra=str(exc)[:80])
        payload["g6"] = "fail"
        payload["reason"] = "unguarded_write" if wrote else str(exc)
        maybe_record("fail", str(payload["reason"])[:200])
        return payload
    finally:
        watchdog_stop.set()
        gated_event.set()
        client.close()


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
        "optional_providers": probe_optional_voice_providers(),
        "native_chat_path": native_chat_path(),
        "speech_path": hybrid_speech_path(),
    }
