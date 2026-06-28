from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field

from hive_planner.agents_memory import lint_agents_md
from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, validate_unified_handoff
from hive_planner.config import RepoPaths
from hive_planner.map_sync import sync_impact_maps
from hive_planner.project_profile import resolve_project_integrations
from hive_planner.roadmap_status import validate_roadmap
from hive_planner.spec_drift import check_memory_spec_drift, check_spec_handoff


def _is_hive_planner_source(paths: RepoPaths) -> bool:
    pyproject = paths.root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        return 'name = "hive-planner"' in pyproject.read_text(encoding="utf-8")
    except OSError:
        return False


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
    check_spec_kit: bool | None = None,
) -> CiCheckReport:
    report = CiCheckReport()
    integrations = resolve_project_integrations(paths.root)
    spec_kit = integrations.spec_kit_enabled if check_spec_kit is None else check_spec_kit

    lint = lint_agents_md(paths)
    lint_detail = "ok" if lint.ok else f"{sum(1 for i in lint.issues if i.severity == 'error')} error(s)"
    report.steps.append(CiStepResult("agents-lint", lint.ok, lint_detail))

    if not spec_kit:
        report.steps.append(CiStepResult("handoff-artifacts", True, "skipped (agent handoff off)"))
        report.steps.append(CiStepResult("spec-drift", True, "skipped (agent handoff off)"))
        report.steps.append(CiStepResult("agent-handoff-profile", True, "skipped (agent handoff off)"))
    else:
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

        profile = validate_unified_handoff(paths.root)
        if profile.mode == AGENT_HANDOFF_UNIFIED:
            detail = "unified (Spec Kit + Continual Learning)" if profile.complete else f"missing: {', '.join(profile.missing)}"
            report.steps.append(CiStepResult("agent-handoff-profile", profile.complete, detail))
        else:
            report.steps.append(CiStepResult("agent-handoff-profile", True, "legacy spec kit only"))

    from hive_planner.vendor_sync import ci_unified_vendor_step

    hive_source = _is_hive_planner_source(paths)
    require_pins = not hive_source and integrations.agent_handoff_mode == AGENT_HANDOFF_UNIFIED
    if hive_source or integrations.agent_handoff_mode == AGENT_HANDOFF_UNIFIED:
        vendor_ok, vendor_detail = ci_unified_vendor_step(
            paths,
            hive_source=hive_source,
            require_pins=require_pins,
        )
        report.steps.append(CiStepResult("unified-vendor", vendor_ok, vendor_detail))
    else:
        report.steps.append(CiStepResult("unified-vendor", True, "skipped (not unified / not hive source)"))

    if check_map_drift:
        map_report = sync_impact_maps(paths, dry_run=True)
        drift = bool(
            map_report.project_added
            or map_report.test_added
            or map_report.project_updated
            or map_report.test_updated
        )
        detail = "maps current" if not drift else (
            f"drift: +{len(map_report.project_added)} project, "
            f"+{len(map_report.test_added)} test rows, "
            f"~{len(map_report.project_updated)} project updates, "
            f"~{len(map_report.test_updated)} test updates"
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
