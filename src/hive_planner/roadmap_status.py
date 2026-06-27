from __future__ import annotations

from dataclasses import dataclass, field

from hive_planner.config import RepoPaths

ROADMAP_FEATURES: tuple[str, ...] = (
    "cartridge-compiler-v1",
    "cartridge-compiler-v2",
    "change-impact-v1",
    "cartridge-compiler-v3",
    "cartridge-translator-v1",
    "agents-memory-ci-v1",
    "embedding-retrieval-v1",
    "cartridge-delta-emit-v1",
    "change-impact-v2",
    "git-handoff-ci-v1",
    "cartridge-pack-v1",
    "roadmap-complete-v1",
    "cl-spec-integration-v1",
    "agents-memory-ci-v2",
    "cartridge-pack-v2",
    "change-impact-v3",
    "project-bootstrap-v1",
    "roadmap-complete-v2",
)


@dataclass
class RoadmapReport:
    ok: bool
    complete: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "complete": self.complete,
            "missing": self.missing,
            "total": len(ROADMAP_FEATURES),
        }


def validate_roadmap(paths: RepoPaths) -> RoadmapReport:
    complete: list[str] = []
    missing: list[str] = []
    for feature in ROADMAP_FEATURES:
        spec = paths.root / "docs" / "specs" / feature / "spec.md"
        micro = paths.root / "docs" / "delta" / "20_micro" / f"{feature}.md"
        tasks = paths.root / "docs" / "specs" / feature / "tasks.md"
        if spec.exists() and micro.exists() and tasks.exists():
            complete.append(feature)
        else:
            missing.append(feature)
    return RoadmapReport(ok=not missing, complete=complete, missing=missing)
