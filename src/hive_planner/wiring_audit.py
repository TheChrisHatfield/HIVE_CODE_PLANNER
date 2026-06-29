"""Machine-enforceable Integration wiring audit attestation (CL pre-flight gate)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
from hive_planner.config import RepoPaths, validate_feature_id
from hive_planner.spec_drift import handoff_artifact_paths, parse_active_feature

WIRING_AUDIT_REL = Path(".hive") / "wiring-audit.json"
WIRING_AUDIT_VERSION = 1
DEFAULT_MAX_AGE_HOURS = 168

TASKS_WIRING_AUDIT_HEADING = "## After each implementation task — Integration wiring audit (required)"
UNCHECKED_TASK_RE = re.compile(r"^-\s*\[\s*\]\s+.+$")
WIRING_AUDIT_SECTION_RE = re.compile(
    r"^## .*Integration wiring audit.*$",
    re.MULTILINE | re.IGNORECASE,
)

REQUIRED_CHECKS = (
    "trace_verified",
    "no_false_success",
    "integration_evidence",
)


class WiringAuditError(Exception):
    """Wiring audit record or validation failed."""


@dataclass
class WiringAuditReport:
    ok: bool
    feature: str | None = None
    detail: str = ""
    missing: list[str] = field(default_factory=list)
    attestation_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "feature": self.feature,
            "detail": self.detail,
            "missing": self.missing,
            "attestation_path": self.attestation_path,
        }


def wiring_audit_enforced(paths: RepoPaths) -> bool:
    override = os.environ.get("HIVE_WIRING_AUDIT", "").strip().lower()
    if override in {"0", "false", "no", "off"}:
        return False
    if override in {"1", "true", "yes", "on"}:
        return True
    from hive_planner.agent_handoff import normalize_agent_handoff_mode
    from hive_planner.project_profile import read_project_profile

    meta = read_project_profile(paths.root)
    if not meta:
        return False
    if meta.agent_handoff_mode:
        return normalize_agent_handoff_mode(meta.agent_handoff_mode) == AGENT_HANDOFF_UNIFIED
    return bool(meta.spec_kit_enabled and meta.continual_learning_enabled)


def wiring_audit_path(paths: RepoPaths) -> Path:
    return paths.root / WIRING_AUDIT_REL


def _parse_iso_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _find_wiring_audit_section(tasks_text: str) -> str:
    start = tasks_text.find(TASKS_WIRING_AUDIT_HEADING)
    if start >= 0:
        return tasks_text[start + len(TASKS_WIRING_AUDIT_HEADING) :]
    match = WIRING_AUDIT_SECTION_RE.search(tasks_text)
    if not match:
        return ""
    section = tasks_text[match.end() :]
    return section


def _unchecked_wiring_items(tasks_text: str) -> list[str]:
    section = _find_wiring_audit_section(tasks_text)
    if not section:
        return []
    next_heading = re.search(r"^## ", section, re.MULTILINE)
    if next_heading:
        section = section[: next_heading.start()]
    unchecked: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if UNCHECKED_TASK_RE.match(stripped):
            unchecked.append(stripped)
    return unchecked


def _load_attestation(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def record_wiring_audit(
    paths: RepoPaths,
    *,
    feature: str | None = None,
    evidence: str,
    summary: str = "",
    max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
) -> Path:
    active = feature or parse_active_feature(paths)
    if not active:
        raise WiringAuditError("Could not resolve active feature — set ## Active feature in AGENTS.md or pass --feature")
    try:
        validate_feature_id(active)
    except ValueError as exc:
        raise WiringAuditError(str(exc)) from exc

    evidence = evidence.strip()
    if not evidence:
        raise WiringAuditError("--evidence is required (integration-level validation command or result)")

    payload = {
        "version": WIRING_AUDIT_VERSION,
        "feature": active,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "evidence": evidence,
        "summary": summary.strip(),
        "max_age_hours": max_age_hours,
        "checks": {key: True for key in REQUIRED_CHECKS},
    }

    out_path = wiring_audit_path(paths)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out_path


def check_wiring_audit(
    paths: RepoPaths,
    *,
    feature: str | None = None,
    max_age_hours: int | None = None,
) -> WiringAuditReport:
    active = feature or parse_active_feature(paths)
    attestation = wiring_audit_path(paths)
    rel = attestation.relative_to(paths.root).as_posix()

    if not active:
        return WiringAuditReport(
            ok=False,
            detail="Could not parse active feature from AGENTS.md",
            missing=["active feature in AGENTS.md"],
            attestation_path=rel,
        )

    payload = _load_attestation(attestation)
    if payload is None:
        return WiringAuditReport(
            ok=False,
            feature=active,
            detail=f"Missing wiring audit attestation at {rel} - run: hive_planner wiring-audit record --evidence \"<command>\"",
            missing=[rel],
            attestation_path=rel,
        )

    missing: list[str] = []
    recorded_feature = str(payload.get("feature") or "").strip()
    if recorded_feature != active:
        missing.append(f"attestation feature {recorded_feature!r} != active {active!r}")

    checks = payload.get("checks")
    if not isinstance(checks, dict):
        missing.append("checks object missing")
    else:
        for key in REQUIRED_CHECKS:
            if not checks.get(key):
                missing.append(f"check not confirmed: {key}")

    evidence = str(payload.get("evidence") or "").strip()
    if not evidence:
        missing.append("evidence missing")

    recorded_at = _parse_iso_timestamp(str(payload.get("recorded_at") or ""))
    if recorded_at is None:
        missing.append("recorded_at invalid or missing")
    else:
        age_limit = max_age_hours
        if age_limit is None:
            raw_limit = payload.get("max_age_hours", DEFAULT_MAX_AGE_HOURS)
            try:
                age_limit = int(raw_limit)
            except (TypeError, ValueError):
                age_limit = DEFAULT_MAX_AGE_HOURS
        age = datetime.now(timezone.utc) - recorded_at
        if age.total_seconds() > age_limit * 3600:
            missing.append(f"attestation stale (older than {age_limit}h)")

    tasks_path = handoff_artifact_paths(paths, active).get(f"docs/specs/{active}/tasks.md")
    if tasks_path and tasks_path.is_file():
        unchecked = _unchecked_wiring_items(tasks_path.read_text(encoding="utf-8", errors="replace"))
        if unchecked:
            missing.append(f"tasks.md wiring audit checklist incomplete ({len(unchecked)} unchecked)")

    if missing:
        return WiringAuditReport(
            ok=False,
            feature=active,
            detail="; ".join(missing),
            missing=missing,
            attestation_path=rel,
        )

    return WiringAuditReport(
        ok=True,
        feature=active,
        detail="ok",
        attestation_path=rel,
    )


def require_wiring_audit_for_memory(paths: RepoPaths, *, skip: bool = False) -> WiringAuditReport | None:
    if skip or not wiring_audit_enforced(paths):
        return None
    report = check_wiring_audit(paths)
    if not report.ok:
        raise WiringAuditError(
            f"Blocked: complete Integration wiring audit before memory promotion - {report.detail}"
        )
    return report
