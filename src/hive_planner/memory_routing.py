"""Autonomous memory candidate routing — split, route, Thompson-sample arms."""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.config import RepoPaths

ROUTING_STATS_FILE = ".hive/memory-routing.json"
SCHEMA_VERSION = 1

ARM_SPLIT = "split"
ARM_ACCEPT = "accept"
ARM_ROUTE_SPEC = "route_spec"
ARM_REJECT = "reject"
ARM_OPERATIONALIZE = "operationalize"

DEFAULT_ARMS = (ARM_SPLIT, ARM_ACCEPT, ARM_ROUTE_SPEC, ARM_REJECT, ARM_OPERATIONALIZE)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!;:])\s+|(?<=\))\s+(?=[A-Z])|\s+[—–-]\s+|\s*;\s*")
_CLAUSE_SPLIT = re.compile(r",\s+(?=and |or |then |which |with |for |when )", re.IGNORECASE)
_TAG_TRAILING = re.compile(r"(?:\s+#\s*(?:operational|behavioral|ambiguous)\s*)$", re.IGNORECASE)


@dataclass
class ArmStats:
    successes: float = 1.0
    failures: float = 1.0

    def sample(self, rng: random.Random) -> float:
        # Thompson sampling via Beta(successes, failures)
        return rng.betavariate(max(self.successes, 0.5), max(self.failures, 0.5))

    def record(self, *, success: bool) -> None:
        if success:
            self.successes += 1.0
        else:
            self.failures += 1.0

    def to_dict(self) -> dict:
        return {"successes": self.successes, "failures": self.failures}

    @classmethod
    def from_dict(cls, data: dict | None) -> ArmStats:
        if not data:
            return cls()
        return cls(
            successes=float(data.get("successes", 1.0)),
            failures=float(data.get("failures", 1.0)),
        )


@dataclass
class RoutingDecision:
    arm: str
    original: str
    remediations: list[str] = field(default_factory=list)
    reason: str = ""
    spec_action: str | None = None

    def to_dict(self) -> dict:
        return {
            "arm": self.arm,
            "original": self.original,
            "remediations": list(self.remediations),
            "reason": self.reason,
            "spec_action": self.spec_action,
        }


@dataclass
class RoutingStats:
    arms: dict[str, ArmStats] = field(default_factory=dict)

    def arm(self, name: str) -> ArmStats:
        if name not in self.arms:
            self.arms[name] = ArmStats()
        return self.arms[name]

    def thompson_pick(self, candidates: list[str], *, rng: random.Random | None = None) -> str:
        if not candidates:
            return ARM_REJECT
        if len(candidates) == 1:
            return candidates[0]
        r = rng or random.Random()
        scored = [(name, self.arm(name).sample(r)) for name in candidates]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[0][0]

    def record(self, arm: str, *, success: bool) -> None:
        self.arm(arm).record(success=success)

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "arms": {name: stats.to_dict() for name, stats in sorted(self.arms.items())},
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> RoutingStats:
        stats = cls()
        if not data:
            return stats
        arms = data.get("arms") or {}
        for name, payload in arms.items():
            stats.arms[str(name)] = ArmStats.from_dict(payload)
        return stats


def routing_stats_path(paths: RepoPaths) -> Path:
    return paths.root / ROUTING_STATS_FILE


def load_routing_stats(paths: RepoPaths) -> RoutingStats:
    path = routing_stats_path(paths)
    if not path.is_file():
        return RoutingStats()
    try:
        return RoutingStats.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return RoutingStats()


def save_routing_stats(paths: RepoPaths, stats: RoutingStats) -> Path:
    path = routing_stats_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats.to_dict(), indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def _strip_tag(bullet: str) -> tuple[str, str | None]:
    match = _TAG_TRAILING.search(bullet.strip())
    if not match:
        return bullet.strip(), None
    tag = match.group(0).strip().lower()
    body = _TAG_TRAILING.sub("", bullet.strip()).strip()
    return body, tag


def _reattach_tag(body: str, tag: str | None) -> str:
    cleaned = body.strip()
    if not cleaned:
        return cleaned
    if tag:
        return f"{cleaned} {tag}"
    return cleaned


def split_long_bullet(bullet: str, *, max_chars: int) -> list[str]:
    """Split an oversized operational bullet into <= max_chars pieces."""
    body, tag = _strip_tag(bullet)
    if len(_reattach_tag(body, tag)) <= max_chars:
        return [bullet.strip()]

    chunks: list[str] = []
    remaining = body
    while remaining and len(_reattach_tag(remaining, tag)) > max_chars:
        window = remaining[: max_chars - (len(tag) + 1 if tag else 0)]
        cut = -1
        for pattern in (_SENTENCE_SPLIT, _CLAUSE_SPLIT):
            matches = list(pattern.finditer(window))
            if matches:
                cut = matches[-1].end()
                break
        if cut <= 0:
            space = window.rfind(" ")
            cut = space if space > 24 else len(window)
        piece = remaining[:cut].strip(" ,;—–-")
        remaining = remaining[cut:].strip(" ,;—–-")
        if piece:
            chunks.append(_reattach_tag(piece, tag))
    if remaining:
        chunks.append(_reattach_tag(remaining, tag))

    # Drop empty / still-too-long leftovers (keep original pieces that fit)
    usable = [c for c in chunks if c and len(c) <= max_chars]
    if usable:
        return usable
    # Hard wrap fallback
    hard: list[str] = []
    text = body
    limit = max(40, max_chars - (len(tag) + 1 if tag else 0))
    while text:
        hard.append(_reattach_tag(text[:limit].strip(), tag))
        text = text[limit:].strip()
    return [c for c in hard if c and len(c) <= max_chars]


_TAG_BEHAVIORAL = re.compile(r"(?:^|\s)#\s*behavioral\s*$", re.IGNORECASE)
_TAG_OPERATIONAL = re.compile(r"(?:^|\s)#\s*operational\s*$", re.IGNORECASE)
_TAG_AMBIGUOUS = re.compile(r"(?:^|\s)#\s*ambiguous\s*$", re.IGNORECASE)


def _normalize_bullet_text(text: str) -> str:
    cleaned = re.sub(r"^[-*]\s+", "", text.strip())
    cleaned = _TAG_BEHAVIORAL.sub("", cleaned).strip()
    cleaned = _TAG_OPERATIONAL.sub("", cleaned).strip()
    cleaned = _TAG_AMBIGUOUS.sub("", cleaned).strip()
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _bullet_line_in_markdown(bullet: str, content: str) -> bool:
    target = _normalize_bullet_text(bullet)
    for line in content.splitlines():
        text = line.strip()
        if text.startswith("- "):
            if _normalize_bullet_text(text[2:]) == target:
                return True
    return False


def _append_behavioral_candidate(paths: RepoPaths, feature: str | None, bullet: str) -> tuple[Path, bool]:
    proposals = paths.root / "docs" / "proposals"
    proposals.mkdir(parents=True, exist_ok=True)
    out = proposals / "cl-candidates.md"
    feature_label = feature or "<feature>"
    block = [
        "",
        f"# behavioral  <!-- routed by memory_routing → docs/specs/{feature_label}/spec.md -->",
        f"- {bullet.strip()}",
        "",
    ]
    if out.is_file():
        existing = out.read_text(encoding="utf-8", errors="replace")
        if _bullet_line_in_markdown(bullet, existing):
            return out, False
        out.write_text(existing.rstrip() + "\n" + "\n".join(block), encoding="utf-8", newline="\n")
    else:
        header = [
            "# Continual Learning candidates (auto-routed)",
            "",
            "Behavioral bullets landed here for Spec Kit review. Do not merge into AGENTS.md.",
            "",
        ]
        out.write_text("\n".join(header + block), encoding="utf-8", newline="\n")
    return out, True


def route_oversized_operational(
    bullet: str,
    *,
    max_chars: int,
    stats: RoutingStats | None = None,
    rng: random.Random | None = None,
) -> RoutingDecision:
    pieces = split_long_bullet(bullet, max_chars=max_chars)
    if len(pieces) == 1 and len(pieces[0]) <= max_chars and pieces[0] == bullet.strip():
        return RoutingDecision(arm=ARM_ACCEPT, original=bullet, remediations=[bullet.strip()], reason="fits limit")
    if pieces and all(len(p) <= max_chars for p in pieces):
        return RoutingDecision(
            arm=ARM_SPLIT,
            original=bullet,
            remediations=pieces,
            reason=f"Auto-split into {len(pieces)} bullet(s) ≤ {max_chars} chars",
        )
    if stats is not None:
        stats.record(ARM_SPLIT, success=False)
    return RoutingDecision(
        arm=ARM_REJECT,
        original=bullet,
        remediations=[],
        reason="Could not auto-split under character limit — reject or shorten manually",
    )


def route_ambiguous_candidate(
    bullet: str,
    *,
    feature: str | None,
    stats: RoutingStats,
    rng: random.Random | None = None,
) -> RoutingDecision:
    arm = stats.thompson_pick([ARM_OPERATIONALIZE, ARM_ROUTE_SPEC, ARM_REJECT], rng=rng)
    if arm == ARM_OPERATIONALIZE:
        body, _tag = _strip_tag(bullet)
        remediated = f"{body} # operational"
        return RoutingDecision(
            arm=arm,
            original=bullet,
            remediations=[remediated],
            reason="Thompson: treat as operational (tagged # operational)",
        )
    if arm == ARM_ROUTE_SPEC:
        spec_path = f"docs/specs/{feature}/spec.md" if feature else "docs/specs/<feature>/spec.md"
        return RoutingDecision(
            arm=arm,
            original=bullet,
            remediations=[],
            reason=f"Thompson: route to Spec Kit ({spec_path})",
            spec_action=f"Update {spec_path} before promoting behavioral bullet: {bullet[:80]}",
        )
    return RoutingDecision(
        arm=ARM_REJECT,
        original=bullet,
        remediations=[],
        reason="Thompson: reject ambiguous candidate",
    )


def route_behavioral_candidate(
    bullet: str,
    *,
    paths: RepoPaths,
    feature: str | None,
    stats: RoutingStats | None = None,
) -> RoutingDecision:
    out, wrote = _append_behavioral_candidate(paths, feature, bullet)
    rel = out.relative_to(paths.root).as_posix()
    spec_path = f"docs/specs/{feature}/spec.md" if feature else "docs/specs/<feature>/spec.md"
    if stats is not None:
        stats.record(ARM_ROUTE_SPEC, success=wrote)
    reason = (
        f"Auto-routed behavioral bullet to {rel}"
        if wrote
        else f"Behavioral bullet already present in {rel}"
    )
    return RoutingDecision(
        arm=ARM_ROUTE_SPEC,
        original=bullet,
        remediations=[],
        reason=reason,
        spec_action=f"Update {spec_path} from {rel}: {bullet[:80]}" if wrote else None,
    )
