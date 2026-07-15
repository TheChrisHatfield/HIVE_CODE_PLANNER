from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.agents_memory import EDITABLE_SECTION, _match_section, _section_bullets, parse_sections
from hive_planner.config import RepoPaths, validate_feature_id

FEATURE_RE = re.compile(r"\*\*([a-z0-9][a-z0-9-]*)\*\*")

PLACEHOLDER_FEATURES = frozenset({"none", "tbd", "placeholder"})

BOOTSTRAP_DEFAULT_FEATURE = "example-feature"

ACTIVE_FEATURE_SECTION_RE = re.compile(
    r"(^## Active feature[^\n]*\n)(.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)

BEHAVIORAL_PATTERNS = (
    re.compile(r"\bmust\b", re.IGNORECASE),
    re.compile(r"\bshould always\b", re.IGNORECASE),
    re.compile(r"\bacceptance\b", re.IGNORECASE),
    re.compile(r"\bAPI\b"),
    re.compile(r"\bbehavior\b", re.IGNORECASE),
    re.compile(r"\breturns?\b", re.IGNORECASE),
    re.compile(r"\b(?:must|shall|required to)\s+validate\b", re.IGNORECASE),
    re.compile(r"\bvalidates?\s+(?:all|each|request|payload|schema|input|token)\b", re.IGNORECASE),
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
    re.compile(r"docs/specs/", re.IGNORECASE),
    re.compile(r"docs/delta/", re.IGNORECASE),
    re.compile(r"\.hive/", re.IGNORECASE),
    re.compile(r"wiring-audit", re.IGNORECASE),
    re.compile(r"agents-propose", re.IGNORECASE),
    re.compile(r"before handoff", re.IGNORECASE),
)

CLASSIFICATION_MARGIN = 2
AMBIGUOUS_TAG_HINT = "append `# operational` or `# behavioral` tag"

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
    ambiguous: list[str] = field(default_factory=list)
    drift_items: list[str] = field(default_factory=list)
    spec_actions: list[str] = field(default_factory=list)
    handoff: SpecHandoffReport | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "feature": self.feature,
            "operational": self.operational,
            "behavioral": self.behavioral,
            "ambiguous": self.ambiguous,
            "drift_items": self.drift_items,
            "spec_actions": self.spec_actions,
            "handoff": self.handoff.to_dict() if self.handoff else None,
        }


def parse_feature_from_active_body(active_body: str) -> str | None:
    match = FEATURE_RE.search(active_body)
    if not match:
        return None
    feature = match.group(1)
    if feature.lower() in PLACEHOLDER_FEATURES:
        return None
    return feature


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
    return parse_feature_from_active_body(active_body)


@dataclass
class AgentsRepairResult:
    repaired: bool
    feature: str | None = None
    detail: str = ""


def bootstrap_active_feature_body(feature: str = BOOTSTRAP_DEFAULT_FEATURE, *, unified: bool = False) -> str:
    if unified:
        return (
            f"**{feature}** — unified Spec Kit + Continual Learning scaffold; "
            "replace when real work begins."
        )
    return f"**{feature}** — starter scaffold from bootstrap; replace when you begin real work."


def handoff_artifact_paths(paths: RepoPaths, feature: str) -> dict[str, Path]:
    return {
        f"docs/specs/{feature}/spec.md": paths.root / "docs" / "specs" / feature / "spec.md",
        f"docs/specs/{feature}/plan.md": paths.root / "docs" / "specs" / feature / "plan.md",
        f"docs/specs/{feature}/tasks.md": paths.root / "docs" / "specs" / feature / "tasks.md",
        f"docs/delta/20_micro/{feature}.md": paths.root / "docs" / "delta" / "20_micro" / f"{feature}.md",
    }


def handoff_artifacts_present(paths: RepoPaths, feature: str) -> bool:
    try:
        validate_feature_id(feature)
    except ValueError:
        return False
    return all(path.is_file() for path in handoff_artifact_paths(paths, feature).values())


def infer_repairable_active_feature(paths: RepoPaths) -> str | None:
    from hive_planner.project_profile import resolve_project_integrations

    if not resolve_project_integrations(paths.root).spec_kit_enabled:
        return None
    if parse_active_feature(paths):
        return None
    if handoff_artifacts_present(paths, BOOTSTRAP_DEFAULT_FEATURE):
        return BOOTSTRAP_DEFAULT_FEATURE
    return None


def repair_agents_active_feature(paths: RepoPaths, feature: str | None = None) -> AgentsRepairResult:
    current = parse_active_feature(paths)
    if feature:
        # Same feature id already present — preserve custom Active feature notes.
        if current == feature:
            return AgentsRepairResult(False, feature=current, detail="already set")
        target = feature
    else:
        target = infer_repairable_active_feature(paths)
        if not target:
            return AgentsRepairResult(False, detail="no repair needed")
    agents_path = paths.root / "AGENTS.md"
    if not agents_path.is_file():
        return AgentsRepairResult(False, detail="AGENTS.md missing")
    text = agents_path.read_text(encoding="utf-8", errors="replace")
    match = ACTIVE_FEATURE_SECTION_RE.search(text)
    if not match:
        return AgentsRepairResult(False, detail="Active feature section not found")
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, resolve_agent_handoff_mode

    unified = resolve_agent_handoff_mode(paths.root) == AGENT_HANDOFF_UNIFIED
    new_body = bootstrap_active_feature_body(target, unified=unified)
    if match.group(2).strip() == new_body:
        return AgentsRepairResult(False, feature=target, detail="already correct")
    updated = text[: match.start(2)] + f"\n{new_body}\n" + text[match.end(2) :]
    try:
        agents_path.write_text(updated, encoding="utf-8", newline="\n")
    except OSError as exc:
        return AgentsRepairResult(False, feature=target, detail=str(exc))
    return AgentsRepairResult(True, feature=target, detail=f"set Active feature to {target}")


def repair_agents_rosetta_section(paths: RepoPaths) -> AgentsRepairResult:
    from hive_planner.rosetta_nav import agents_missing_rosetta_section, inject_agents_rosetta_section

    agents_path = paths.root / "AGENTS.md"
    if not agents_path.is_file():
        return AgentsRepairResult(False, detail="AGENTS.md missing")
    text = agents_path.read_text(encoding="utf-8", errors="replace")
    if not agents_missing_rosetta_section(text):
        return AgentsRepairResult(False, detail="Rosetta section already present")
    updated = inject_agents_rosetta_section(text)
    if updated == text:
        return AgentsRepairResult(False, detail="no Rosetta section change")
    try:
        agents_path.write_text(updated, encoding="utf-8", newline="\n")
    except OSError as exc:
        return AgentsRepairResult(False, detail=str(exc))
    return AgentsRepairResult(True, detail="added Planning Rosetta Stone section to AGENTS.md")


def repair_handoff_rosetta_navigation(paths: RepoPaths) -> dict:
    """Patch AGENTS + handoff files with Rosetta navigation when artifacts already exist."""
    from hive_planner.rosetta_nav import DEPLOY_HANDOFF_NAV_LAYERS, ensure_handoff_rosetta_navigation

    details: list[str] = []
    agents = repair_agents_rosetta_section(paths)
    if agents.repaired:
        details.append(agents.detail)
    feature = parse_active_feature(paths)
    if not feature and handoff_artifacts_present(paths, BOOTSTRAP_DEFAULT_FEATURE):
        feature = BOOTSTRAP_DEFAULT_FEATURE
    patched: list[str] = []
    if feature and handoff_artifacts_present(paths, feature):
        patched = ensure_handoff_rosetta_navigation(
            paths,
            feature,
            promoted_layers=set(DEPLOY_HANDOFF_NAV_LAYERS),
        )
        if patched:
            details.append(f"patched navigation in {len(patched)} handoff file(s)")
    if not details and not patched:
        return {}
    return {"detail": "; ".join(details), "patched": patched}


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
    if behavioral_hits and operational_hits:
        margin = behavioral_hits - operational_hits
        mixed = f"mixed signals ({behavioral_hits} behavioral, {operational_hits} operational)"
        if abs(margin) >= CLASSIFICATION_MARGIN:
            kind = "behavioral" if margin > 0 else "operational"
            return ClassifiedBullet(stripped, kind, mixed)
        return ClassifiedBullet(stripped, "ambiguous", f"{mixed} — {AMBIGUOUS_TAG_HINT}")
    return ClassifiedBullet(stripped, "operational", "default operational")


def check_spec_handoff(paths: RepoPaths, feature: str | None = None) -> SpecHandoffReport:
    from hive_planner.rosetta_nav import agents_missing_rosetta_section, missing_handoff_rosetta_navigation

    active = feature or parse_active_feature(paths)
    if not active:
        return SpecHandoffReport(feature=None, ok=False, missing=["active feature in AGENTS.md"])
    try:
        validate_feature_id(active)
    except ValueError:
        return SpecHandoffReport(feature=active, ok=False, missing=[f"invalid feature id: {active}"])

    required = handoff_artifact_paths(paths, active)
    agents_path = paths.root / "AGENTS.md"
    missing = [label for label, path in required.items() if not path.exists()]
    if not missing:
        missing.extend(missing_handoff_rosetta_navigation(paths, active))
        if agents_path.is_file():
            agents_text = agents_path.read_text(encoding="utf-8", errors="replace")
            if agents_missing_rosetta_section(agents_text):
                missing.append("AGENTS.md missing Planning Rosetta Stone section")
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
    from hive_planner.agents_memory import _parse_candidates

    return _parse_candidates(text)


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
            try:
                rel = candidate_file.relative_to(paths.root)
                spec_actions.append(f"Candidates file not found: {rel.as_posix()}")
            except ValueError:
                spec_actions.append(f"Candidates file not found: {candidate_file}")
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
    ambiguous: list[str] = []
    drift_items: list[str] = []
    seen_drift: set[str] = set()
    seen_operational: set[str] = set()
    seen_behavioral: set[str] = set()
    seen_ambiguous: set[str] = set()

    def _check_bullet(bullet: str, *, from_agents: bool) -> None:
        classified = classify_bullet(bullet)
        if classified.kind == "ambiguous":
            key = _normalize_for_match(bullet)
            if key not in seen_ambiguous:
                seen_ambiguous.add(key)
                ambiguous.append(bullet)
                spec_actions.append(f"Classification ambiguous — {AMBIGUOUS_TAG_HINT}: {bullet[:80]}")
            return
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

    ok = (
        not drift_items
        and not ambiguous
        and handoff.ok
        and not any("Candidates file not found" in a for a in spec_actions)
    )
    return SpecDriftReport(
        ok=ok,
        feature=active,
        operational=operational,
        behavioral=behavioral,
        ambiguous=ambiguous,
        drift_items=drift_items,
        spec_actions=spec_actions,
        handoff=handoff,
    )
