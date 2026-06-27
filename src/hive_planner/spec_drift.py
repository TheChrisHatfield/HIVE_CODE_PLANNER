from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.agents_memory import EDITABLE_SECTION, _match_section, _section_bullets, parse_sections
from hive_planner.config import RepoPaths

FEATURE_RE = re.compile(r"\*\*([a-z0-9][a-z0-9-]*)\*\*")

BEHAVIORAL_PATTERNS = (
    re.compile(r"\bmust\b", re.IGNORECASE),
    re.compile(r"\bshould always\b", re.IGNORECASE),
    re.compile(r"\bacceptance\b", re.IGNORECASE),
    re.compile(r"\bAPI\b"),
    re.compile(r"\bbehavior\b", re.IGNORECASE),
    re.compile(r"\breturns?\b", re.IGNORECASE),
    re.compile(r"\bvalidates?\b", re.IGNORECASE),
    re.compile(r"\brequired to\b", re.IGNORECASE),
    re.compile(r"\bshall\b", re.IGNORECASE),
    re.compile(r"\brequirement\b", re.IGNORECASE),
    re.compile(r"\bwhen .+ then\b", re.IGNORECASE),
    re.compile(r"\bnon-negotiable\b", re.IGNORECASE),
)

OPERATIONAL_PATTERNS = (
    re.compile(r"hive_planner", re.IGNORECASE),
    re.compile(r"py -3\.11", re.IGNORECASE),
    re.compile(r"START_HERE", re.IGNORECASE),
    re.compile(r"planning\.rosetta", re.IGNORECASE),
    re.compile(r"\.cursor/rules", re.IGNORECASE),
    re.compile(r"read order", re.IGNORECASE),
    re.compile(r"repo root", re.IGNORECASE),
    re.compile(r"pytest", re.IGNORECASE),
    re.compile(r"ci-check", re.IGNORECASE),
    re.compile(r"roadmap-status", re.IGNORECASE),
)

TAG_BEHAVIORAL = re.compile(r"(?:^|\s)#\s*behavioral\s*$", re.IGNORECASE)
TAG_OPERATIONAL = re.compile(r"(?:^|\s)#\s*operational\s*$", re.IGNORECASE)


@dataclass
class ClassifiedBullet:
    text: str
    kind: str
    reason: str


@dataclass
class SpecHandoffReport:
    feature: str | None
    ok: bool
    missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "feature": self.feature,
            "ok": self.ok,
            "missing": self.missing,
        }


@dataclass
class SpecDriftReport:
    ok: bool
    feature: str | None
    operational: list[str] = field(default_factory=list)
    behavioral: list[str] = field(default_factory=list)
    drift_items: list[str] = field(default_factory=list)
    spec_actions: list[str] = field(default_factory=list)
    handoff: SpecHandoffReport | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "feature": self.feature,
            "operational": self.operational,
            "behavioral": self.behavioral,
            "drift_items": self.drift_items,
            "spec_actions": self.spec_actions,
            "handoff": self.handoff.to_dict() if self.handoff else None,
        }


def parse_active_feature(paths: RepoPaths) -> str | None:
    agents_path = paths.root / "AGENTS.md"
    if not agents_path.exists():
        return None
    sections = parse_sections(agents_path.read_text(encoding="utf-8", errors="replace"))
    active_body = sections.get("Active feature", "")
    if not active_body:
        for title, body in sections.items():
            if title.startswith("Active feature"):
                active_body = body
                break
    match = FEATURE_RE.search(active_body)
    return match.group(1) if match else None


def _normalize_for_match(text: str) -> str:
    cleaned = re.sub(r"^[-*]\s+", "", text.strip())
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def classify_bullet(text: str) -> ClassifiedBullet:
    stripped = text.strip()
    if TAG_BEHAVIORAL.search(stripped):
        return ClassifiedBullet(stripped, "behavioral", "tagged # behavioral")
    if TAG_OPERATIONAL.search(stripped):
        return ClassifiedBullet(stripped, "operational", "tagged # operational")

    operational_hits = sum(1 for p in OPERATIONAL_PATTERNS if p.search(stripped))
    behavioral_hits = sum(1 for p in BEHAVIORAL_PATTERNS if p.search(stripped))

    if behavioral_hits and operational_hits == 0:
        return ClassifiedBullet(stripped, "behavioral", "behavioral keyword match")
    if operational_hits and behavioral_hits == 0:
        return ClassifiedBullet(stripped, "operational", "operational keyword match")
    if behavioral_hits > operational_hits:
        return ClassifiedBullet(stripped, "behavioral", "behavioral keyword match")
    return ClassifiedBullet(stripped, "operational", "default operational")


def check_spec_handoff(paths: RepoPaths, feature: str | None = None) -> SpecHandoffReport:
    active = feature or parse_active_feature(paths)
    if not active:
        return SpecHandoffReport(feature=None, ok=False, missing=["active feature in AGENTS.md"])

    required = {
        f"docs/specs/{active}/spec.md": paths.root / "docs" / "specs" / active / "spec.md",
        f"docs/specs/{active}/plan.md": paths.root / "docs" / "specs" / active / "plan.md",
        f"docs/specs/{active}/tasks.md": paths.root / "docs" / "specs" / active / "tasks.md",
        f"docs/delta/20_micro/{active}.md": paths.root / "docs" / "delta" / "20_micro" / f"{active}.md",
    }
    missing = [label for label, path in required.items() if not path.exists()]
    return SpecHandoffReport(feature=active, ok=not missing, missing=missing)


def _read_spec_text(paths: RepoPaths, feature: str) -> str:
    spec_path = paths.root / "docs" / "specs" / feature / "spec.md"
    if not spec_path.exists():
        return ""
    return spec_path.read_text(encoding="utf-8", errors="replace").lower()


def _bullet_reflected_in_spec(bullet: str, spec_text: str) -> bool:
    if not spec_text:
        return False
    normalized = _normalize_for_match(bullet)
    if len(normalized) < 12:
        return normalized in spec_text
    words = [w for w in re.findall(r"[a-z0-9]{4,}", normalized) if w not in {"must", "should", "always", "when"}]
    if not words:
        return normalized in spec_text
    hits = sum(1 for w in words[:8] if w in spec_text)
    return hits >= max(2, len(words[:8]) // 2)


def _collect_bullets_from_candidates(text: str) -> list[str]:
    bullets: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
        else:
            bullets.append(stripped)
    return [b for b in bullets if b]


def _collect_agents_facts(paths: RepoPaths) -> list[str]:
    agents_path = paths.root / "AGENTS.md"
    if not agents_path.exists():
        return []
    sections = parse_sections(agents_path.read_text(encoding="utf-8", errors="replace"))
    key = _match_section(sections, EDITABLE_SECTION)
    if key is None:
        return []
    return [b for _, b in _section_bullets(sections[key])]


def _dedupe_bullets(bullets: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for bullet in bullets:
        key = _normalize_for_match(bullet)
        if key in seen:
            continue
        seen.add(key)
        unique.append(bullet)
    return unique


def check_memory_spec_drift(
    paths: RepoPaths,
    *,
    feature: str | None = None,
    candidates_path: Path | None = None,
    include_agents_facts: bool = True,
) -> SpecDriftReport:
    active = feature or parse_active_feature(paths)
    handoff = check_spec_handoff(paths, active)

    spec_actions: list[str] = []
    candidate_bullets: list[str] = []
    if candidates_path is not None:
        candidate_file = candidates_path if candidates_path.is_absolute() else paths.root / candidates_path
        if not candidate_file.exists():
            spec_actions.append(f"Candidates file not found: {candidate_file.relative_to(paths.root)}")
        else:
            candidate_bullets = _collect_bullets_from_candidates(
                candidate_file.read_text(encoding="utf-8", errors="replace")
            )
    agent_bullets = _collect_agents_facts(paths) if include_agents_facts else []

    agents_feature = parse_active_feature(paths)
    spec_text = _read_spec_text(paths, active) if active else ""
    agents_spec_text = _read_spec_text(paths, agents_feature) if agents_feature else ""

    operational: list[str] = []
    behavioral: list[str] = []
    drift_items: list[str] = []
    seen_drift: set[str] = set()
    seen_operational: set[str] = set()
    seen_behavioral: set[str] = set()

    def _check_bullet(bullet: str, *, from_agents: bool) -> None:
        classified = classify_bullet(bullet)
        if classified.kind == "operational":
            key = _normalize_for_match(bullet)
            if key not in seen_operational:
                seen_operational.add(key)
                operational.append(bullet)
            return
        key = _normalize_for_match(bullet)
        if key not in seen_behavioral:
            seen_behavioral.add(key)
            behavioral.append(bullet)
        compare_feature = agents_feature if from_agents else active
        compare_spec = agents_spec_text if from_agents else spec_text
        if not compare_feature or _bullet_reflected_in_spec(bullet, compare_spec):
            return
        key = _normalize_for_match(bullet)
        if key in seen_drift:
            return
        seen_drift.add(key)
        drift_items.append(bullet)
        spec_actions.append(
            f"Update docs/specs/{compare_feature}/spec.md before promoting: {bullet[:80]}"
        )

    for bullet in _dedupe_bullets(candidate_bullets):
        _check_bullet(bullet, from_agents=False)
    for bullet in _dedupe_bullets(agent_bullets):
        _check_bullet(bullet, from_agents=True)

    ok = not drift_items and handoff.ok and not any("Candidates file not found" in a for a in spec_actions)
    return SpecDriftReport(
        ok=ok,
        feature=active,
        operational=operational,
        behavioral=behavioral,
        drift_items=drift_items,
        spec_actions=spec_actions,
        handoff=handoff,
    )
