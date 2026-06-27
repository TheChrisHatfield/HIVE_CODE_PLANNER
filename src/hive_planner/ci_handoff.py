from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field

from hive_planner.agents_memory import lint_agents_md
from hive_planner.config import RepoPaths
from hive_planner.map_sync import sync_impact_maps
from hive_planner.roadmap_status import validate_roadmap
from hive_planner.spec_drift import check_memory_spec_drift, check_spec_handoff


@dataclass
class CiStepResult:
    name: str
    ok: bool
    detail: str


@dataclass
class CiCheckReport:
    steps: list[CiStepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(step.ok for step in self.steps)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "steps": [{"name": s.name, "ok": s.ok, "detail": s.detail} for s in self.steps],
        }


def run_ci_check(
    paths: RepoPaths,
    *,
    skip_pytest: bool = False,
    check_map_drift: bool = True,
    check_roadmap: bool = True,
) -> CiCheckReport:
    report = CiCheckReport()

    lint = lint_agents_md(paths)
    lint_detail = "ok" if lint.ok else f"{sum(1 for i in lint.issues if i.severity == 'error')} error(s)"
    report.steps.append(CiStepResult("agents-lint", lint.ok, lint_detail))

    handoff = check_spec_handoff(paths)
    if handoff.feature:
        detail = handoff.feature if handoff.ok else f"missing: {', '.join(handoff.missing)}"
        report.steps.append(CiStepResult("handoff-artifacts", handoff.ok, detail))
    else:
        report.steps.append(CiStepResult("handoff-artifacts", False, "Could not parse active feature from AGENTS.md"))

    drift = check_memory_spec_drift(paths, include_agents_facts=True)
    if drift.drift_items:
        detail = f"{len(drift.drift_items)} behavioral bullet(s) not reflected in spec"
        report.steps.append(CiStepResult("spec-drift", False, detail))
    elif not drift.handoff or not drift.handoff.ok:
        report.steps.append(CiStepResult("spec-drift", False, "incomplete spec handoff"))
    else:
        report.steps.append(CiStepResult("spec-drift", True, "ok"))

    if check_map_drift:
        map_report = sync_impact_maps(paths, dry_run=True)
        drift = bool(map_report.project_added or map_report.test_added)
        detail = "maps current" if not drift else (
            f"drift: +{len(map_report.project_added)} project, +{len(map_report.test_added)} test rows"
        )
        report.steps.append(CiStepResult("impact-map-drift", not drift, detail))

    if check_roadmap:
        roadmap = validate_roadmap(paths)
        report.steps.append(
            CiStepResult(
                "roadmap-artifacts",
                roadmap.ok,
                f"{len(roadmap.complete)}/{len(roadmap.complete) + len(roadmap.missing)} features"
                if roadmap.ok
                else f"missing: {', '.join(roadmap.missing)}",
            )
        )

    if not skip_pytest:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=paths.root,
            capture_output=True,
            text=True,
        )
        detail = (proc.stdout or proc.stderr or "").strip()[-400:]
        report.steps.append(CiStepResult("pytest", proc.returncode == 0, detail or f"exit {proc.returncode}"))

    return report
