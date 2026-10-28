from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from hive_planner.config import RepoPaths, resolve_repo_agents_path

EDITABLE_SECTION = "Durable Workspace Facts"
MAX_BULLET_CHARS = 240
APPLY_VERSION = "v2"

REQUIRED_SECTIONS = (
    "Repository root",
    "Planning Rosetta Stone",
    "Startup read order",
    "Delta model",
    "Active feature",
)

LOW_SIGNAL_PATTERNS = (
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bWIP\b", re.IGNORECASE),
    re.compile(r"\bFIXME\b", re.IGNORECASE),
    re.compile(r"\bsession[_ -]?id\b", re.IGNORECASE),
    re.compile(r"\bfeature/[A-Za-z0-9_/-]+\b"),
    re.compile(r"\bchg_[0-9]{8}_[0-9]{6}_"),
)

TAG_BEHAVIORAL = re.compile(r"(?:^|\s)#\s*behavioral\s*$", re.IGNORECASE)
TAG_OPERATIONAL = re.compile(r"(?:^|\s)#\s*operational\s*$", re.IGNORECASE)
TAG_AMBIGUOUS = re.compile(r"(?:^|\s)#\s*ambiguous\s*$", re.IGNORECASE)

TRANSCRIPT_NOISE = (
    re.compile(r"^user:\s*", re.IGNORECASE),
    re.compile(r"^assistant:\s*", re.IGNORECASE),
    re.compile(r"^\[\d{4}-\d{2}-\d{2}", re.IGNORECASE),
)

CHECKBOX_BULLET_RE = re.compile(r"^\[[ xX]\]\s*")


class AgentsMemoryError(Exception):
    """AGENTS.md lint or proposal failed."""

    def __init__(
        self,
        message: str,
        *,
        proposal_path: str | None = None,
        rejected: list[dict[str, str]] | None = None,
        spec_actions: list[str] | None = None,
        current_facts: str | None = None,
        accepted: list[str] | None = None,
        after_section: str | None = None,
    ) -> None:
        super().__init__(message)
        self.proposal_path = proposal_path
        self.rejected = rejected or []
        self.spec_actions = spec_actions or []
        self.current_facts = current_facts or ""
        self.accepted = accepted or []
        self.after_section = after_section or ""


def agents_memory_error_detail(exc: AgentsMemoryError) -> dict:
    """Structured CLI/launcher detail for a failed memory promotion."""
    detail: dict = {"error": str(exc)}
    if exc.proposal_path:
        detail["proposal_path"] = exc.proposal_path
    if exc.accepted:
        detail["accepted"] = exc.accepted
    if exc.rejected:
        detail["rejected"] = exc.rejected
    if exc.spec_actions:
        detail["spec_actions"] = exc.spec_actions
    if exc.current_facts:
        detail["current_facts"] = exc.current_facts
    if exc.after_section:
        detail["after_section"] = exc.after_section
    return detail


@dataclass
class LintIssue:
    severity: str
    message: str
    line: int | None = None


@dataclass
class AgentsLintReport:
    path: str
    issues: list[LintIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "ok": self.ok,
            "issues": [{"severity": i.severity, "message": i.message, "line": i.line} for i in self.issues],
        }


@dataclass
class AgentsMemoryResult:
    proposal_path: Path
    applied: bool
    accepted: list[str] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)
    current_facts: str = ""
    after_section: str = ""
    spec_actions: list[str] = field(default_factory=list)
    routing: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = {
            "proposal_path": str(self.proposal_path),
            "applied": self.applied,
            "accepted": self.accepted,
            "rejected": [{"candidate": c, "reason": r} for c, r in self.rejected],
            "current_facts": self.current_facts,
            "after_section": self.after_section,
            "spec_actions": self.spec_actions,
        }
        if self.routing:
            payload["routing"] = self.routing
        return payload


def _normalize_bullet(text: str) -> str:
    cleaned = re.sub(r"^[-*]\s+", "", text.strip())
    cleaned = TAG_BEHAVIORAL.sub("", cleaned).strip()
    cleaned = TAG_OPERATIONAL.sub("", cleaned).strip()
    cleaned = TAG_AMBIGUOUS.sub("", cleaned).strip()
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_title = ""
    current_lines: list[str] = []
    in_fence = False

    def flush() -> None:
        nonlocal current_lines
        if current_title:
            body = "\n".join(current_lines).strip()
            if current_title in sections:
                existing = sections[current_title]
                if existing and body:
                    sections[current_title] = f"{existing}\n\n{body}"
                elif body:
                    sections[current_title] = body
            else:
                sections[current_title] = body
        current_lines = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            if current_title:
                current_lines.append(line)
            continue
        if not in_fence and line.startswith("## "):
            flush()
            current_title = line[3:].strip()
            continue
        if current_title:
            current_lines.append(line)

    flush()
    return sections


def _section_bullets(section_body: str) -> list[tuple[int, str]]:
    bullets: list[tuple[int, str]] = []
    for idx, line in enumerate(section_body.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append((idx, stripped[2:].strip()))
    return bullets


def _resolve_agents_path(paths: RepoPaths, agents_path: Path | None) -> Path:
    try:
        return resolve_repo_agents_path(paths, agents_path)
    except ValueError as exc:
        raise AgentsMemoryError(str(exc)) from exc
    except FileNotFoundError as exc:
        raise AgentsMemoryError(str(exc)) from exc


def _match_section(sections: dict[str, str], required: str) -> str | None:
    if required in sections:
        return required
    for title in sections:
        if title.startswith(required):
            return title
    return None


def _existing_durable_bullets(sections: dict[str, str]) -> set[str]:
    key = _match_section(sections, EDITABLE_SECTION)
    body = sections.get(key, "") if key else ""
    return {_normalize_bullet(b) for _, b in _section_bullets(body)}


def _parse_active_feature_from_sections(sections: dict[str, str]) -> str | None:
    from hive_planner.spec_drift import parse_feature_from_active_body

    active_body = sections.get("Active feature", "")
    if not active_body:
        for title, body in sections.items():
            if title.startswith("Active feature"):
                active_body = body
                break
    return parse_feature_from_active_body(active_body)


def _iter_section_bullets(text: str) -> list[tuple[str, int, str]]:
    current_section: str | None = None
    bullets: list[tuple[str, int, str]] = []
    in_fence = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue
        if current_section and stripped.startswith("- "):
            bullets.append((current_section, line_no, stripped[2:].strip()))
    return bullets


def lint_agents_md(paths: RepoPaths, agents_path: Path | None = None) -> AgentsLintReport:
    target = _resolve_agents_path(paths, agents_path)
    text = target.read_text(encoding="utf-8", errors="replace")
    sections = parse_sections(text)
    report = AgentsLintReport(path=str(target.relative_to(paths.root)).replace("\\", "/"))

    for required in REQUIRED_SECTIONS:
        matched = _match_section(sections, required)
        if matched is None:
            report.issues.append(LintIssue("error", f"Missing required section: ## {required}"))
        elif not sections[matched].strip():
            report.issues.append(LintIssue("error", f"Empty required section: ## {matched}"))

    if _match_section(sections, EDITABLE_SECTION) is None:
        report.issues.append(
            LintIssue(
                "warning",
                f"Missing editable subsection: ## {EDITABLE_SECTION} (proposals target this section)",
            )
        )

    seen_bullets: dict[str, int] = {}
    for title, line_no, bullet in _iter_section_bullets(text):
        normalized = _normalize_bullet(bullet)
        if normalized in seen_bullets:
            report.issues.append(
                LintIssue(
                    "warning",
                    f"Duplicate bullet in ## {title}: {bullet[:80]}",
                    line=line_no,
                )
            )
        else:
            seen_bullets[normalized] = line_no

        if len(bullet) > MAX_BULLET_CHARS:
            report.issues.append(
                LintIssue(
                    "warning",
                    f"Bullet exceeds {MAX_BULLET_CHARS} chars in ## {title}",
                    line=line_no,
                )
            )

        for pattern in LOW_SIGNAL_PATTERNS:
            if pattern.search(bullet):
                report.issues.append(
                    LintIssue(
                        "warning",
                        f"Low-signal bullet pattern in ## {title}: {pattern.pattern}",
                        line=line_no,
                    )
                )
                break

        if title.startswith(EDITABLE_SECTION) or title == EDITABLE_SECTION:
            from hive_planner.spec_drift import classify_bullet

            classified = classify_bullet(bullet)
            if classified.kind == "ambiguous":
                report.issues.append(
                    LintIssue(
                        "error",
                        f"Ambiguous bullet classification — append `# operational` or `# behavioral`: {bullet[:80]}",
                        line=line_no,
                    )
                )
            elif classified.kind == "behavioral":
                report.issues.append(
                    LintIssue(
                        "error",
                        f"Behavioral bullet in ## {EDITABLE_SECTION} — move to active spec.md: {bullet[:80]}",
                        line=line_no,
                    )
                )

    return report


def _parse_section_header(stripped: str) -> str | None:
    lowered = stripped.lower()
    if lowered == "# operational":
        return "# operational"
    if lowered == "# behavioral":
        return "# behavioral"
    if lowered == "# ambiguous":
        return "# ambiguous"
    return None


def _apply_section_tag(bullet: str, section_tag: str | None) -> str:
    if (
        not section_tag
        or TAG_BEHAVIORAL.search(bullet)
        or TAG_OPERATIONAL.search(bullet)
        or TAG_AMBIGUOUS.search(bullet)
    ):
        return bullet
    if section_tag == "# behavioral":
        return f"{bullet} # behavioral"
    if section_tag == "# operational":
        return f"{bullet} # operational"
    if section_tag == "# ambiguous":
        return f"{bullet} # ambiguous"
    return bullet


def _active_section_tag(text: str) -> str | None:
    tag: str | None = None
    for line in text.splitlines():
        section = _parse_section_header(line.strip())
        if section:
            tag = section
    return tag


def _parse_candidates_lines(
    text: str,
    *,
    respect_fences: bool = True,
    initial_tag: str | None = None,
) -> list[str]:
    candidates: list[str] = []
    current_tag: str | None = initial_tag
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if respect_fences and stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if respect_fences and in_fence:
            continue
        section_tag = _parse_section_header(stripped)
        if section_tag:
            current_tag = section_tag
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            bullet = stripped[2:].strip()
            if CHECKBOX_BULLET_RE.match(bullet):
                continue
            candidates.append(_apply_section_tag(bullet, current_tag))
        elif stripped.startswith("* "):
            bullet = stripped[2:].strip()
            if CHECKBOX_BULLET_RE.match(bullet):
                continue
            candidates.append(_apply_section_tag(bullet, current_tag))
        elif stripped.startswith("• "):
            bullet = stripped[2:].strip()
            if CHECKBOX_BULLET_RE.match(bullet):
                continue
            candidates.append(_apply_section_tag(bullet, current_tag))
    return [c for c in candidates if c]


def _parse_candidates(text: str) -> list[str]:
    lines = text.splitlines()
    fence_lines = [idx for idx, line in enumerate(lines) if line.strip().startswith("```")]
    if len(fence_lines) % 2 == 1:
        split_at = fence_lines[-1]
        before = "\n".join(lines[:split_at])
        after = "\n".join(lines[split_at + 1 :])
        after_tag = _active_section_tag(before)
        merged: list[str] = []
        seen: set[str] = set()
        for item in _parse_candidates_lines(before, respect_fences=True) + _parse_candidates_lines(
            after,
            respect_fences=False,
            initial_tag=after_tag,
        ):
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
        return merged
    return _parse_candidates_lines(text, respect_fences=True)


def _substantive_candidate_text(bullet: str) -> str:
    cleaned = TAG_BEHAVIORAL.sub("", bullet.strip()).strip()
    cleaned = TAG_OPERATIONAL.sub("", cleaned).strip()
    cleaned = TAG_AMBIGUOUS.sub("", cleaned).strip()
    return cleaned


def _validate_candidate(bullet: str, existing: set[str]) -> str | None:
    if len(bullet) > MAX_BULLET_CHARS:
        return f"Candidate exceeds {MAX_BULLET_CHARS} characters"
    normalized = _normalize_bullet(bullet)
    if normalized in existing:
        return "Candidate duplicates an existing AGENTS.md bullet"
    for pattern in LOW_SIGNAL_PATTERNS:
        if pattern.search(bullet):
            return f"Candidate matches low-signal pattern: {pattern.pattern}"
    return None


def _append_spec_action(spec_actions: list[str], action: str | None) -> None:
    if action and action not in spec_actions:
        spec_actions.append(action)


def _try_accept_operational(
    candidate: str,
    *,
    accepted: list[str],
    rejected: list[tuple[str, str]],
    routing: list[dict],
    existing: set[str],
    stats,
    max_chars: int = MAX_BULLET_CHARS,
) -> None:
    from hive_planner.memory_routing import ARM_ACCEPT, ARM_SPLIT, route_oversized_operational

    known = existing | {_normalize_bullet(c) for c in accepted}
    err = _validate_candidate(candidate, known)
    if err is None:
        accepted.append(candidate)
        existing.add(_normalize_bullet(candidate))
        return
    if not err.startswith("Candidate exceeds"):
        rejected.append((candidate, err))
        return

    decision = route_oversized_operational(candidate, max_chars=max_chars, stats=stats)
    routing.append(decision.to_dict())
    if decision.arm == ARM_SPLIT and decision.remediations:
        added = 0
        for piece in decision.remediations:
            piece_err = _validate_candidate(piece, existing | {_normalize_bullet(c) for c in accepted})
            if piece_err:
                rejected.append((piece, f"Auto-split piece failed: {piece_err}"))
            else:
                accepted.append(piece)
                existing.add(_normalize_bullet(piece))
                added += 1
        if stats is not None:
            stats.record(ARM_SPLIT, success=added > 0)
        rejected.append(
            (
                candidate,
                f"Remediated: {decision.reason}" + (f" ({added} accepted)" if added else ""),
            )
        )
        return
    if decision.arm == ARM_ACCEPT and decision.remediations:
        normalized = decision.remediations[0]
        piece_err = _validate_candidate(normalized, existing | {_normalize_bullet(c) for c in accepted})
        if piece_err is None:
            accepted.append(normalized)
            existing.add(_normalize_bullet(normalized))
            return
    rejected.append((candidate, f"{err} — {decision.reason}"))


def _evaluate_candidates(
    sections: dict[str, str],
    raw_candidates: list[str],
    *,
    paths: RepoPaths | None = None,
    auto_route: bool = True,
) -> tuple[list[str], list[tuple[str, str]], list[str], list[dict]]:
    from hive_planner.memory_routing import (
        ARM_OPERATIONALIZE,
        ARM_ROUTE_SPEC,
        RoutingStats,
        load_routing_stats,
        route_ambiguous_candidate,
        route_behavioral_candidate,
        save_routing_stats,
    )
    from hive_planner.spec_drift import classify_bullet

    existing = _existing_durable_bullets(sections)
    accepted: list[str] = []
    rejected: list[tuple[str, str]] = []
    spec_actions: list[str] = []
    routing: list[dict] = []
    feature = _parse_active_feature_from_sections(sections)
    stats = load_routing_stats(paths) if paths is not None else RoutingStats()

    for candidate in raw_candidates:
        if not _substantive_candidate_text(candidate):
            rejected.append(
                (candidate, "Candidate is a section tag only — add substantive bullet text")
            )
            continue
        if TAG_AMBIGUOUS.search(candidate):
            rejected.append(
                (
                    candidate,
                    "Classification ambiguous — append `# operational` or `# behavioral` tag (tagged # ambiguous)",
                )
            )
            continue
        classified = classify_bullet(candidate)
        if classified.kind == "ambiguous":
            if auto_route:
                decision = route_ambiguous_candidate(candidate, feature=feature, stats=stats)
                routing.append(decision.to_dict())
                if decision.arm == ARM_OPERATIONALIZE and decision.remediations:
                    before = len(accepted)
                    for piece in decision.remediations:
                        _try_accept_operational(
                            piece,
                            accepted=accepted,
                            rejected=rejected,
                            routing=routing,
                            existing=existing,
                            stats=stats,
                        )
                    stats.record(ARM_OPERATIONALIZE, success=len(accepted) > before)
                    continue
                if decision.arm == ARM_ROUTE_SPEC:
                    _append_spec_action(spec_actions, decision.spec_action)
                    rejected.append((candidate, decision.reason))
                    stats.record(ARM_ROUTE_SPEC, success=False)
                    continue
                rejected.append((candidate, decision.reason))
                stats.record(decision.arm, success=False)
                continue
            rejected.append(
                (
                    candidate,
                    f"Classification ambiguous — append `# operational` or `# behavioral` tag ({classified.reason})",
                )
            )
            continue
        if classified.kind == "behavioral":
            if auto_route and paths is not None:
                decision = route_behavioral_candidate(
                    candidate, paths=paths, feature=feature, stats=stats
                )
                routing.append(decision.to_dict())
                _append_spec_action(spec_actions, decision.spec_action)
                rejected.append((candidate, decision.reason))
            else:
                spec_path = f"docs/specs/{feature}/spec.md" if feature else "docs/specs/<feature>/spec.md"
                reason = f"Behavioral content belongs in Spec Kit ({spec_path}), not AGENTS.md"
                rejected.append((candidate, reason))
                _append_spec_action(
                    spec_actions,
                    f"Update {spec_path} before promoting behavioral bullet: {candidate[:80]}",
                )
            continue
        if auto_route:
            _try_accept_operational(
                candidate,
                accepted=accepted,
                rejected=rejected,
                routing=routing,
                existing=existing,
                stats=stats,
            )
        else:
            err = _validate_candidate(candidate, existing | {_normalize_bullet(c) for c in accepted})
            if err:
                rejected.append((candidate, err))
            else:
                accepted.append(candidate)
                existing.add(_normalize_bullet(candidate))

    if paths is not None and routing:
        save_routing_stats(paths, stats)
    return accepted, rejected, spec_actions, routing


def _section_render_order(sections: dict[str, str], *, insert_key: str | None = None) -> list[str]:
    order = list(sections.keys())
    if insert_key is None or insert_key in order:
        return order
    insert_at = len(order)
    for idx, title in enumerate(order):
        if title.startswith("Active feature"):
            insert_at = idx + 1
            break
    order.insert(insert_at, insert_key)
    return order


def _preamble_lines(text: str) -> list[str]:
    preamble: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            break
        preamble.append(line)
    return preamble


def _apply_accepted_bullets(agents_text: str, accepted: list[str]) -> str:
    preamble = _preamble_lines(agents_text)
    sections = parse_sections(agents_text)
    matched_key = _match_section(sections, EDITABLE_SECTION)
    key = matched_key or EDITABLE_SECTION
    current = sections.get(key, "").strip()
    new_bullets = "\n".join(f"- {c}" for c in accepted)
    sections[key] = f"{current}\n{new_bullets}".strip() if current else new_bullets

    out = list(preamble)
    if out and out[-1].strip():
        out.append("")
    for heading in _section_render_order(sections, insert_key=None if matched_key else key):
        body = sections[heading]
        out.append(f"## {heading}")
        out.append("")
        if body:
            out.append(body)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _write_proposal(
    paths: RepoPaths,
    *,
    target: Path,
    current_facts: str,
    after_section: str,
    proposed_bullets: str,
    accepted: list[str],
    rejected: list[tuple[str, str]],
    spec_actions: list[str],
    applied: bool,
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    proposals_dir = paths.root / "docs" / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    out_path = proposals_dir / f"agents-memory-{timestamp}.md"

    lines = [
        "# AGENTS.md Memory Proposal",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Target:** `{target.relative_to(paths.root).as_posix()}`",
        f"**Section:** `{EDITABLE_SECTION}`",
        f"**Applied:** {applied}",
        "",
        "## Accepted candidates",
        "",
        proposed_bullets,
        "",
        "## Before",
        "",
        "```markdown",
        current_facts or "(section missing or empty)",
        "```",
        "",
        "## After (proposed)",
        "",
        "```markdown",
        after_section,
        "```",
        "",
    ]

    if rejected:
        lines.extend(["## Rejected candidates", ""])
        for candidate, reason in rejected:
            lines.append(f"- `{candidate}` — {reason}")
        lines.append("")

    if spec_actions:
        lines.extend(["## Spec Kit actions required", ""])
        for action in spec_actions:
            lines.append(f"- {action}")
        lines.append("")

    if applied:
        lines.extend(
            [
                "## Apply status",
                "",
                f"Accepted bullets were merged into `## {EDITABLE_SECTION}` ({APPLY_VERSION} guarded apply).",
                "",
                "Autonomous memory routing (split / route_spec / Thompson) may have remapped candidates;",
                "see `.hive/memory-routing.json` for arm reward stats.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Manual merge steps",
                "",
                "1. Review accepted bullets for durable, cross-session value.",
                f"2. Add or update `## {EDITABLE_SECTION}` in AGENTS.md.",
                f"3. Or run `hive_planner agents-apply --candidates <file>` for guarded {APPLY_VERSION} apply.",
                "",
            ]
        )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def propose_agents_memory(
    paths: RepoPaths,
    candidates_path: Path,
    *,
    agents_path: Path | None = None,
    apply: bool = False,
    auto_route: bool = True,
) -> Path:
    result = run_agents_memory(
        paths,
        candidates_path,
        agents_path=agents_path,
        apply=apply,
        auto_route=auto_route,
    )
    return result.proposal_path


def run_agents_memory(
    paths: RepoPaths,
    candidates_path: Path,
    *,
    agents_path: Path | None = None,
    apply: bool = False,
    skip_wiring_audit: bool = False,
    auto_route: bool = True,
) -> AgentsMemoryResult:
    from hive_planner.wiring_audit import WiringAuditError, require_wiring_audit_for_memory

    try:
        require_wiring_audit_for_memory(paths, skip=skip_wiring_audit)
    except WiringAuditError as exc:
        raise AgentsMemoryError(str(exc)) from exc

    target = _resolve_agents_path(paths, agents_path)
    candidate_file = candidates_path if candidates_path.is_absolute() else paths.root / candidates_path
    if not candidate_file.exists():
        raise AgentsMemoryError(f"Candidates file not found: {candidates_path}")
    try:
        candidate_file.resolve().relative_to(paths.root.resolve())
    except ValueError as exc:
        raise AgentsMemoryError(
            f"Candidates file must be inside project root: {paths.root}"
        ) from exc
    if candidate_file.name.startswith("agents-memory-") and candidate_file.suffix.lower() == ".md":
        raise AgentsMemoryError(
            "Select a candidates file, not a generated agents-memory proposal.",
        )

    agents_text = target.read_text(encoding="utf-8", errors="replace")
    sections = parse_sections(agents_text)
    raw_candidates = _parse_candidates(candidate_file.read_text(encoding="utf-8", errors="replace"))
    if not raw_candidates:
        raise AgentsMemoryError("No candidate bullets found in candidates file")

    accepted, rejected, spec_actions, routing = _evaluate_candidates(
        sections,
        raw_candidates,
        paths=paths,
        auto_route=auto_route,
    )

    current_key = _match_section(sections, EDITABLE_SECTION)
    current_facts = sections.get(current_key, "").strip() if current_key else ""

    if not accepted:
        reject_proposal = _write_proposal(
            paths,
            target=target,
            current_facts=current_facts,
            after_section=current_facts,
            proposed_bullets="",
            accepted=[],
            rejected=rejected,
            spec_actions=spec_actions,
            applied=False,
        )
        rel = reject_proposal.relative_to(paths.root).as_posix()
        raise AgentsMemoryError(
            f"All candidate bullets were rejected by validation — see {rel} for per-bullet reasons",
            proposal_path=rel,
            rejected=[{"candidate": c, "reason": r} for c, r in rejected],
            spec_actions=spec_actions,
            current_facts=current_facts,
            after_section=current_facts,
        )

    proposed_bullets = "\n".join(f"- {c}" for c in accepted)
    after_section = f"{current_facts}\n{proposed_bullets}".strip() if current_facts else proposed_bullets

    applied = False
    apply_bullets = accepted
    if apply:
        pending = [c for c in accepted if _normalize_bullet(c) not in _existing_durable_bullets(sections)]
        apply_bullets = pending
        if pending:
            updated = _apply_accepted_bullets(agents_text, pending)
            target.write_text(updated, encoding="utf-8")
            lint = lint_agents_md(paths, agents_path=target)
            if not lint.ok:
                target.write_text(agents_text, encoding="utf-8")
                errors = [i.message for i in lint.issues if i.severity == "error"]
                rollback_proposal = _write_proposal(
                    paths,
                    target=target,
                    current_facts=current_facts,
                    after_section=after_section,
                    proposed_bullets=proposed_bullets,
                    accepted=pending,
                    rejected=rejected,
                    spec_actions=spec_actions,
                    applied=False,
                )
                rel = rollback_proposal.relative_to(paths.root).as_posix()
                raise AgentsMemoryError(
                    f"Apply rolled back — AGENTS.md lint failed: {'; '.join(errors)}",
                    proposal_path=rel,
                    rejected=[{"candidate": c, "reason": r} for c, r in rejected],
                    spec_actions=spec_actions,
                    current_facts=current_facts,
                    accepted=pending,
                    after_section=after_section,
                )
            applied = True
            proposed_bullets = "\n".join(f"- {c}" for c in pending)
            after_section = (
                f"{current_facts}\n{proposed_bullets}".strip() if current_facts else proposed_bullets
            )

    out_path = _write_proposal(
        paths,
        target=target,
        current_facts=current_facts,
        after_section=after_section,
        proposed_bullets=proposed_bullets,
        accepted=apply_bullets if apply else accepted,
        rejected=rejected,
        spec_actions=spec_actions,
        applied=applied,
    )
    return AgentsMemoryResult(
        proposal_path=out_path,
        applied=applied,
        accepted=apply_bullets if apply else accepted,
        rejected=rejected,
        current_facts=current_facts,
        after_section=after_section,
        spec_actions=spec_actions,
        routing=routing,
    )


def _resolve_reuse_proposal_path(paths: RepoPaths, proposal_path: Path | str | None) -> Path | None:
    if not proposal_path:
        return None
    rel = Path(proposal_path)
    candidate = rel if rel.is_absolute() else paths.root / rel
    return candidate if candidate.is_file() else None


def apply_agents_memory_accepted(
    paths: RepoPaths,
    *,
    accepted: list[str],
    rejected: list[tuple[str, str]] | None = None,
    spec_actions: list[str] | None = None,
    routing: list[dict] | None = None,
    current_facts: str | None = None,
    after_section: str | None = None,
    agents_path: Path | None = None,
    proposal_path: Path | str | None = None,
    skip_wiring_audit: bool = False,
) -> AgentsMemoryResult:
    """Apply a prior propose result without re-evaluating candidates (Thompson-safe)."""
    from hive_planner.wiring_audit import WiringAuditError, require_wiring_audit_for_memory

    if not accepted:
        raise AgentsMemoryError("No accepted bullets to apply")

    try:
        require_wiring_audit_for_memory(paths, skip=skip_wiring_audit)
    except WiringAuditError as exc:
        raise AgentsMemoryError(str(exc)) from exc

    target = _resolve_agents_path(paths, agents_path)
    agents_text = target.read_text(encoding="utf-8", errors="replace")
    sections = parse_sections(agents_text)
    current_key = _match_section(sections, EDITABLE_SECTION)
    facts = sections.get(current_key, "").strip() if current_key else ""
    rejections = list(rejected or [])
    actions = list(spec_actions or [])
    routes = list(routing or [])

    existing = _existing_durable_bullets(sections)
    pending = [c for c in accepted if _normalize_bullet(c) not in existing]
    if not pending:
        reuse = _resolve_reuse_proposal_path(paths, proposal_path)
        if reuse is None:
            reuse = _write_proposal(
                paths,
                target=target,
                current_facts=facts,
                after_section=facts,
                proposed_bullets="",
                accepted=[],
                rejected=rejections
                + [("(prior accepted)", "All accepted bullets already present in AGENTS.md")],
                spec_actions=actions,
                applied=False,
            )
        return AgentsMemoryResult(
            proposal_path=reuse,
            applied=False,
            accepted=[],
            rejected=rejections,
            current_facts=facts,
            after_section=facts,
            spec_actions=actions,
            routing=routes,
        )

    proposed_bullets = "\n".join(f"- {c}" for c in pending)
    after = f"{facts}\n{proposed_bullets}".strip() if facts else proposed_bullets

    updated = _apply_accepted_bullets(agents_text, pending)
    target.write_text(updated, encoding="utf-8")
    lint = lint_agents_md(paths, agents_path=target)
    if not lint.ok:
        target.write_text(agents_text, encoding="utf-8")
        errors = [i.message for i in lint.issues if i.severity == "error"]
        rollback_proposal = _write_proposal(
            paths,
            target=target,
            current_facts=facts,
            after_section=after,
            proposed_bullets=proposed_bullets,
            accepted=pending,
            rejected=rejections,
            spec_actions=actions,
            applied=False,
        )
        rel = rollback_proposal.relative_to(paths.root).as_posix()
        raise AgentsMemoryError(
            f"Apply rolled back — AGENTS.md lint failed: {'; '.join(errors)}",
            proposal_path=rel,
            rejected=[{"candidate": c, "reason": r} for c, r in rejections],
            spec_actions=actions,
            current_facts=facts,
            accepted=pending,
            after_section=after,
        )

    out_path = _write_proposal(
        paths,
        target=target,
        current_facts=facts,
        after_section=after,
        proposed_bullets=proposed_bullets,
        accepted=pending,
        rejected=rejections,
        spec_actions=actions,
        applied=True,
    )
    return AgentsMemoryResult(
        proposal_path=out_path,
        applied=True,
        accepted=pending,
        rejected=rejections,
        current_facts=facts,
        after_section=after,
        spec_actions=actions,
        routing=routes,
    )


def _append_tagged_section(lines_out: list[str], tag: str) -> None:
    if lines_out and lines_out[-1] == tag:
        return
    if lines_out and not lines_out[-1].startswith("#"):
        lines_out.append("")
    lines_out.append(tag)


def _strip_inline_tag(bullet: str) -> tuple[str, str | None]:
    if TAG_BEHAVIORAL.search(bullet):
        cleaned = TAG_BEHAVIORAL.sub("", bullet).strip()
        return cleaned, "# behavioral"
    if TAG_OPERATIONAL.search(bullet):
        cleaned = TAG_OPERATIONAL.sub("", bullet).strip()
        return cleaned, "# operational"
    return bullet, None


def normalize_candidates_text(text: str) -> str:
    lines = text.splitlines()
    fence_lines = [idx for idx, line in enumerate(lines) if line.strip().startswith("```")]
    if len(fence_lines) % 2 == 1:
        split_at = fence_lines[-1]
        before = "\n".join(lines[:split_at])
        after = "\n".join(lines[split_at + 1 :])
        before_out = _normalize_candidates_body(before, respect_fences=True)
        after_out = _normalize_candidates_body(
            after,
            respect_fences=False,
            initial_tag=_active_section_tag(before) or "# operational",
        )
        lines_out = before_out
        if before_out and after_out:
            lines_out = before_out + [""] + after_out
        elif after_out:
            lines_out = after_out
        if not lines_out:
            raise AgentsMemoryError("No candidate bullets found after normalization")
        return "\n".join(lines_out).strip() + "\n"
    lines_out = _normalize_candidates_body(text, respect_fences=True)
    if not lines_out:
        raise AgentsMemoryError("No candidate bullets found after normalization")
    return "\n".join(lines_out).strip() + "\n"


def _normalize_candidates_body(
    text: str,
    *,
    respect_fences: bool = True,
    initial_tag: str = "# operational",
) -> list[str]:
    lines_out: list[str] = []
    current_tag = initial_tag
    in_fence = False

    for line in text.splitlines():
        stripped = line.strip()
        if respect_fences and stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if respect_fences and in_fence:
            continue
        if not stripped:
            continue
        section_tag = _parse_section_header(stripped)
        if section_tag:
            current_tag = section_tag
            if lines_out and lines_out[-1] != "":
                lines_out.append("")
            lines_out.append(current_tag)
            continue
        if stripped.startswith("#"):
            continue
        if any(p.search(stripped) for p in TRANSCRIPT_NOISE):
            continue
        if stripped.startswith(("- ", "* ")):
            bullet = stripped[2:].strip()
        elif stripped.startswith("• "):
            bullet = stripped[2:].strip()
        else:
            bullet = stripped
        if not bullet:
            continue
        if CHECKBOX_BULLET_RE.match(bullet):
            continue
        bullet, inline_tag = _strip_inline_tag(bullet)
        if not bullet:
            continue
        if inline_tag:
            current_tag = inline_tag
        else:
            from hive_planner.spec_drift import classify_bullet

            classified = classify_bullet(bullet)
            if classified.kind == "behavioral":
                current_tag = "# behavioral"
            elif classified.kind == "ambiguous":
                current_tag = "# ambiguous"
            else:
                current_tag = "# operational"
        _append_tagged_section(lines_out, current_tag)
        lines_out.append(f"- {bullet}")

    return lines_out


def ingest_agents_candidates(
    paths: RepoPaths,
    source_path: Path,
    *,
    output_path: Path | None = None,
) -> Path:
    source = source_path if source_path.is_absolute() else paths.root / source_path
    if not source.exists():
        raise AgentsMemoryError(f"Source file not found: {source_path}")

    normalized = normalize_candidates_text(source.read_text(encoding="utf-8", errors="replace"))
    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = paths.root / "docs" / "proposals" / f"candidates-normalized-{timestamp}.md"
    else:
        out = output_path if output_path.is_absolute() else paths.root / output_path

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(normalized, encoding="utf-8")
    return out
