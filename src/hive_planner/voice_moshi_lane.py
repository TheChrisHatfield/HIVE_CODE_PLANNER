"""Moshi tool lane (separate from the final-transcript path). Spec: docs/specs/Moshi_Tool_Lane/spec.md.

Moshi has no function-calling interface. This lane accepts one explicit line in Moshi's text
channel (`0x02`), `TOOL: <name> <json-object>`, and turns it into a *proposal*.

- Only the R18 voice-controller tool names are accepted (`VOICE_CONTROLLER_TOOLS`).
- Arguments must be a JSON object within `MAX_ARG_CHARS`, with only the tool's declared fields.
- Read-only tools (`task_status`, `task_diff`, `get_context_snapshot`) are marked `requires_approval: False`.
  Every other tool is `requires_approval: True` and waits for one exact spoken approval (R6).
- Execution (ML-T4) goes only through `MoshiToolBroker`, which calls the runner's
  `invoke_controller_tool`. The workspace and context snapshot are bound by HIVE, never by Moshi.
- Ambiguous text (zero or more than one TOOL line) is rejected. Final transcripts are not read here.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from hive_planner.voice_bot import VOICE_CONTROLLER_TOOLS, VoiceBotError
from hive_planner.voice_task import NEGATION_RE

MAX_ARG_CHARS = 4_000
READ_ONLY_TOOLS: frozenset[str] = frozenset({"task_status", "task_diff", "get_context_snapshot"})
_TOOL_LINE = re.compile(r"^\s*TOOL:\s*([a-z_]+)\s*(\{.*\})\s*$", re.IGNORECASE | re.MULTILINE)

# Fields Moshi may set per tool. Binding fields (workspace, snapshot, request key) are HIVE-owned.
ALLOWED_ARGS: dict[str, frozenset[str]] = {
    "submit_coding_task": frozenset({"instruction", "mode", "file_path"}),
    "task_status": frozenset({"task_id"}),
    "task_diff": frozenset({"task_id"}),
    "get_context_snapshot": frozenset(),
    "queue_follow_up": frozenset({"task_id", "text"}),
    "cancel_coding_task": frozenset({"task_id"}),
    "show_diff": frozenset({"task_id"}),
    "navigate_to": frozenset({"file_path"}),
}
REQUIRED_ARGS: dict[str, frozenset[str]] = {
    "submit_coding_task": frozenset({"instruction", "mode"}),
    "task_status": frozenset({"task_id"}),
    "task_diff": frozenset({"task_id"}),
    "get_context_snapshot": frozenset(),
    "queue_follow_up": frozenset({"task_id", "text"}),
    "cancel_coding_task": frozenset({"task_id"}),
    "show_diff": frozenset({"task_id"}),
    "navigate_to": frozenset({"file_path"}),
}
BINDING_KEYS: frozenset[str] = frozenset({"workspace", "context_snapshot_id", "snapshot_id", "client_request_id", "editor_snapshot"})
SUBMIT_MODES_FROM_MOSHI: frozenset[str] = frozenset({"ask", "plan"})  # `agent` needs G6 + R33 (R6)


class ToolLaneError(ValueError):
    """Refusal code for a Moshi text line that cannot become a proposal."""


@dataclass
class ToolProposal:
    tool: str
    args: dict[str, Any]
    requires_approval: bool
    status: str = "proposed"  # never "executed" by the parser (R23 command separation)
    refusals: list[str] = field(default_factory=list)


def parse_tool_proposal(text: str) -> ToolProposal:
    """Parse exactly one `TOOL: <name> {json}` line. Raises ToolLaneError with a refusal code."""
    if not isinstance(text, str) or not text.strip():
        raise ToolLaneError("no_tool_line")
    matches = _TOOL_LINE.findall(text)
    if not matches:
        raise ToolLaneError("no_tool_line")
    if len(matches) > 1:
        raise ToolLaneError("ambiguous_tool_line")
    name, raw_args = matches[0][0].lower(), matches[0][1]
    if name not in VOICE_CONTROLLER_TOOLS:
        raise ToolLaneError("unknown_tool")
    if len(raw_args) > MAX_ARG_CHARS:
        raise ToolLaneError("args_too_long")
    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError as exc:
        raise ToolLaneError("args_not_json") from exc
    if not isinstance(args, dict):
        raise ToolLaneError("args_not_object")
    return ToolProposal(tool=name, args=args, requires_approval=name not in READ_ONLY_TOOLS)


def validate_args(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """R23 tool-argument validation. Returns a copy with only declared fields; raises ToolLaneError."""
    for key in args:
        if key in BINDING_KEYS:
            raise ToolLaneError("binding_not_allowed")
        if key not in ALLOWED_ARGS[tool]:
            raise ToolLaneError("unknown_arg")
    for key in REQUIRED_ARGS[tool]:
        if key not in args:
            raise ToolLaneError("missing_arg")
    clean: dict[str, Any] = {}
    for key, value in args.items():
        if not isinstance(value, str) or len(value) > MAX_ARG_CHARS:
            raise ToolLaneError("bad_arg_type")
        if key in ("instruction", "text") and not value.strip():
            raise ToolLaneError("empty_arg")
        clean[key] = value
    if tool == "submit_coding_task" and clean["mode"] not in SUBMIT_MODES_FROM_MOSHI:
        raise ToolLaneError("agent_mode_refused")
    return clean


def action_label(tool: str, args: dict[str, Any]) -> str:
    """Short visible label for the approval prompt; the reply must contain it (R6)."""
    base = tool.replace("_", " ")
    task_id = str(args.get("task_id") or "").strip()
    return f"{base} {task_id}" if task_id else base


class MoshiToolBroker:
    """ML-T4: turn an approved Moshi proposal into a runner call (R6 approval, R23 binding).

    One pending approval at a time (R27). Read-only proposals run at once. Every other proposal
    waits for a reply that names its label and says approve or deny; silence past the timeout
    records `timed_out` and runs nothing. `runner` is a `VoiceTaskRunner`; only its
    `invoke_controller_tool`, `pending_approval_view`, and `config` are used.
    """

    def __init__(
        self,
        runner: Any,
        *,
        workspace: str,
        context_snapshot_id: str = "",
        approval_timeout_s: float | None = None,
    ) -> None:
        self._runner = runner
        self._workspace = workspace
        self._snapshot_id = context_snapshot_id
        self._timeout = float(approval_timeout_s if approval_timeout_s is not None else runner.config.approval_timeout_s)
        self._lock = threading.Lock()
        self._pending: dict[str, Any] | None = None
        self._closed = False
        self.log: list[dict[str, Any]] = []

    def set_snapshot(self, context_snapshot_id: str) -> None:
        with self._lock:
            self._snapshot_id = context_snapshot_id

    @property
    def pending(self) -> dict[str, Any] | None:
        with self._lock:
            if self._pending is None:
                return None
            return {k: self._pending[k] for k in ("request_id", "tool", "label")}

    def offer(self, text: str) -> dict[str, Any]:
        """Parse one Moshi text line. Refusals and pending approvals return; nothing else happens."""
        try:
            proposal = parse_tool_proposal(text)
            args = validate_args(proposal.tool, proposal.args)
        except ToolLaneError as exc:
            return self._record({"status": "refused", "reason": str(exc)})
        with self._lock:
            if self._closed:
                return self._record({"status": "refused", "reason": "session_closed"})
            if not proposal.requires_approval:
                return self._record(self._execute(proposal.tool, args))
            view = self._runner.pending_approval_view()
            if self._pending is not None or view.get("pending"):
                return self._record({"status": "refused", "reason": "approval_already_pending"})
            if proposal.tool == "submit_coding_task":
                args = {**args, "client_request_id": f"moshi-{uuid.uuid4().hex}"}
            request_id = uuid.uuid4().hex
            label = action_label(proposal.tool, args)
            timer = threading.Timer(self._timeout, self._on_timeout, args=(request_id,))
            timer.daemon = True
            self._pending = {"request_id": request_id, "tool": proposal.tool, "args": args, "label": label, "timer": timer}
            timer.start()
            return self._record({
                "status": "pending_approval",
                "request_id": request_id,
                "action": label,
                "spoken": f"Approval needed to {label}. Say approve or deny {label}.",
            })

    def reply(self, text: str) -> dict[str, Any]:
        """Route a reply to the pending approval only. Exact label plus one of approve/deny (R6)."""
        with self._lock:
            pend = self._pending
            if pend is None:
                return self._record({"status": "no_pending_approval"})
            label = pend["label"].lower()
            clean = (text or "").strip().lower()
            if label not in clean:
                return self._record({"status": "reprompt", "spoken": f"Say approve or deny {pend['label']}."})
            decision = clean.replace(label, " ", 1)
            says_yes = re.search(r"\bapprove\b", decision) is not None
            says_no = re.search(r"\bdeny\b", decision) is not None
            if NEGATION_RE.search(decision) is not None or says_yes == says_no:
                return self._record({"status": "reprompt", "spoken": f"Say approve or deny {pend['label']}."})
            pend["timer"].cancel()
            self._pending = None
            if says_no:
                return self._record({"status": "denied", "action": pend["label"], "spoken": "Denied. Nothing was executed."})
            execution = self._execute(pend["tool"], pend["args"])
            return self._record({"status": "approved", "action": pend["label"], "execution": execution})

    def close(self) -> None:
        """Session ended: drop any pending approval so nothing runs after the call (R25)."""
        with self._lock:
            self._closed = True
            if self._pending is not None:
                self._pending["timer"].cancel()
                self._pending = None

    def _on_timeout(self, request_id: str) -> None:
        with self._lock:
            pend = self._pending
            if pend is None or pend["request_id"] != request_id:
                return
            self._pending = None
            self._record({"status": "timed_out", "action": pend["label"]})

    def _execute(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        kwargs: dict[str, Any] = dict(args)
        kwargs["workspace"] = self._workspace
        if tool != "submit_coding_task":
            kwargs["context_snapshot_id"] = self._snapshot_id
        try:
            out = self._runner.invoke_controller_tool(tool, **kwargs)
        except VoiceBotError as exc:
            return {"status": "refused", "reason": getattr(exc, "code", None) or str(exc)}
        return {"status": "executed", "tool": tool, "result": out}

    def _record(self, row: dict[str, Any]) -> dict[str, Any]:
        self.log.append(row)
        return row
