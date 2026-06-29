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

TRANSCRIPT_NOISE = (
    re.compile(r"^user:\s*", re.IGNORECASE),
    re.compile(r"^assistant:\s*", re.IGNORECASE),
    re.compile(r"^\[\d{4}-\d{2}-\d{2}", re.IGNORECASE),
)

CHECKBOX_BULLET_RE = re.compile(r"^\[[ xX]\]\s*")


class AgentsMemoryError(Exception):
    """AGENTS.md lint or proposal failed."""


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

    def to_dict(self) -> dict:
        return {
            "proposal_path": str(self.proposal_path),
            "applied": self.applied,
            "accepted": self.accepted,
            "rejected": [{"candidate": c, "reason": r} for c, r in self.rejected],
        }


def _normalize_bullet(text: str) -> str:
    cleaned = re.sub(r"^[-*]\s+", "", text.strip())
    cleaned = TAG_BEHAVIORAL.sub("", cleaned).strip()
    cleaned = TAG_OPERATIONAL.sub("", cleaned).strip()
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_title = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines
        if current_title:
            sections[current_title] = "\n".join(current_lines).strip()
        current_lines = []

    for line in text.splitlines():
        if line.startswith("## "):
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


def _parse_active_feature_from_sections(sections: dict[str, str]) -> str | None:
    from hive_planner.spec_drift import parse_feature_from_active_body

    active_body = ""
    for title, body in sections.items():
        if title.startswith("Active feature"):
            active_body = body
            break
    if not active_body:
        active_body = sections.get("Active feature", "")
    return parse_feature_from_active_body(active_body)


def _iter_section_bullets(text: str) -> list[tuple[str, int, str]]:
    current_section: str | None = None
    bullets: list[tuple[str, int, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue
        if current_section and line.strip().startswith("- "):
            bullets.append((current_section, line_no, line.strip()[2:].strip()))
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


def _parse_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            bullet = stripped[2:].strip()
            if CHECKBOX_BULLET_RE.match(bullet):
                continue
            candidates.append(bullet)
        elif stripped.startswith("* "):
            bullet = stripped[2:].strip()
            if CHECKBOX_BULLET_RE.match(bullet):
                continue
            candidates.append(bullet)
        elif stripped.startswith("• "):
            bullet = stripped[2:].strip()
            if CHECKBOX_BULLET_RE.match(bullet):
                continue
            candidates.append(bullet)
    return [c for c in candidates if c]


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


def _evaluate_candidates(
    sections: dict[str, str],
    raw_candidates: list[str],
) -> tuple[list[str], list[tuple[str, str]], list[str]]:
    from hive_planner.spec_drift import classify_bullet

    existing = {
        _normalize_bullet(b)
        for body in sections.values()
        for _, b in _section_bullets(body)
    }
    accepted: list[str] = []
    rejected: list[tuple[str, str]] = []
    spec_actions: list[str] = []
    feature = _parse_active_feature_from_sections(sections)

    for candidate in raw_candidates:
        classified = classify_bullet(candidate)
        if classified.kind == "ambiguous":
            rejected.append(
                (
                    candidate,
                    f"Classification ambiguous — append `# operational` or `# behavioral` tag ({classified.reason})",
                )
            )
            continue
        if classified.kind == "behavioral":
            spec_path = f"docs/specs/{feature}/spec.md" if feature else "docs/specs/<feature>/spec.md"
            reason = f"Behavioral content belongs in Spec Kit ({spec_path}), not AGENTS.md"
            rejected.append((candidate, reason))
            spec_actions.append(f"Update {spec_path} before promoting behavioral bullet: {candidate[:80]}")
            continue
        err = _validate_candidate(candidate, existing | {_normalize_bullet(c) for c in accepted})
        if err:
            rejected.append((candidate, err))
        else:
            accepted.append(candidate)

    return accepted, rejected, spec_actions


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
) -> Path:
    result = run_agents_memory(paths, candidates_path, agents_path=agents_path, apply=apply)
    return result.proposal_path


def run_agents_memory(
    paths: RepoPaths,
    candidates_path: Path,
    *,
    agents_path: Path | None = None,
    apply: bool = False,
    skip_wiring_audit: bool = False,
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

    agents_text = target.read_text(encoding="utf-8", errors="replace")
    sections = parse_sections(agents_text)
    raw_candidates = _parse_candidates(candidate_file.read_text(encoding="utf-8", errors="replace"))
    if not raw_candidates:
        raise AgentsMemoryError("No candidate bullets found in candidates file")

    accepted, rejected, spec_actions = _evaluate_candidates(sections, raw_candidates)
    if not accepted:
        raise AgentsMemoryError("All candidate bullets were rejected by validation")

    current_key = _match_section(sections, EDITABLE_SECTION)
    current_facts = sections.get(current_key, "").strip() if current_key else ""
    proposed_bullets = "\n".join(f"- {c}" for c in accepted)
    after_section = f"{current_facts}\n{proposed_bullets}".strip() if current_facts else proposed_bullets

    applied = False
    if apply:
        updated = _apply_accepted_bullets(agents_text, accepted)
        target.write_text(updated, encoding="utf-8")
        lint = lint_agents_md(paths, agents_path=target)
        if not lint.ok:
            target.write_text(agents_text, encoding="utf-8")
            errors = [i.message for i in lint.issues if i.severity == "error"]
            raise AgentsMemoryError(f"Apply rolled back — AGENTS.md lint failed: {'; '.join(errors)}")
        applied = True

    out_path = _write_proposal(
        paths,
        target=target,
        current_facts=current_facts,
        after_section=after_section,
        proposed_bullets=proposed_bullets,
        accepted=accepted,
        rejected=rejected,
        spec_actions=spec_actions,
        applied=applied,
    )
    return AgentsMemoryResult(
        proposal_path=out_path,
        applied=applied,
        accepted=accepted,
        rejected=rejected,
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
    lines_out: list[str] = []
    current_tag = "# operational"

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# operational") or stripped.lower() == "# operational":
            current_tag = "# operational"
            if lines_out and lines_out[-1] != "":
                lines_out.append("")
            lines_out.append(current_tag)
            continue
        if stripped.startswith("# behavioral") or stripped.lower() == "# behavioral":
            current_tag = "# behavioral"
            if lines_out and lines_out[-1] != "":
                lines_out.append("")
            lines_out.append(current_tag)
            continue
        if stripped.startswith("# ambiguous") or stripped.lower() == "# ambiguous":
            current_tag = "# ambiguous"
            if lines_out and lines_out[-1] != "":
                lines_out.append("")
            lines_out.append(current_tag)
            continue
        if any(p.search(stripped) for p in TRANSCRIPT_NOISE):
            continue
        if stripped.startswith(("- ", "* ")):
            bullet = stripped[2:].strip()
        elif stripped.startswith("• "):
            bullet = stripped[2:].strip()
        else:
            bullet = stripped
        if not bullet or bullet.startswith("```"):
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

    if not lines_out:
        raise AgentsMemoryError("No candidate bullets found after normalization")
    return "\n".join(lines_out).strip() + "\n"


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
