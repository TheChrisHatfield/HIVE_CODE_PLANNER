from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hive_planner.agents_memory import AgentsMemoryError, run_agents_memory
from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
from hive_planner.ci_handoff import run_ci_check
from hive_planner.config import RepoPaths
from hive_planner.project_profile import write_project_profile
from hive_planner.wiring_audit import (
    TASKS_WIRING_AUDIT_HEADING,
    WiringAuditError,
    check_wiring_audit,
    record_wiring_audit,
    wiring_audit_enforced,
)


def _minimal_agents(feature: str = "my-feature") -> str:
    return f"""# AGENTS.md

## Repository root

`root`

## Planning Rosetta Stone

- hook `planning.rosetta`

## Startup read order

1. rosetta

## Delta model

- Holistic / Macro / Micro

## Active feature

**{feature}**

## Durable Workspace Facts

- Run ci-check before handoff.
"""


def _write_handoff(paths: RepoPaths, feature: str, *, wiring_checked: bool = True) -> None:
    from hive_planner.rosetta_nav import (
        delta_micro_navigation_block,
        inject_after_header,
        plan_navigation_block,
        spec_navigation_block,
        tasks_navigation_block,
    )

    spec_dir = paths.root / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec.md").write_text(
        inject_after_header("# Spec\n\n", spec_navigation_block(feature)),
        encoding="utf-8",
    )
    (spec_dir / "plan.md").write_text(
        inject_after_header("# Plan\n\n", plan_navigation_block(feature)),
        encoding="utf-8",
    )
    wiring_block = "\n".join(
        [
            TASKS_WIRING_AUDIT_HEADING,
            "",
            "- [x] Traced caller → handler → core (no layer break)",
            "- [x] No false success when a sub-step failed or was skipped",
            "- [x] Integration-level validation evidence attached",
            "- [x] See `.cursor/rules/integration-wiring-audit.mdc`",
            "",
        ]
    )
    tasks_body = "# Tasks\n\n"
    if wiring_checked:
        tasks_body += wiring_block
    (spec_dir / "tasks.md").write_text(
        inject_after_header(tasks_body, tasks_navigation_block(feature)),
        encoding="utf-8",
    )
    micro = paths.root / "docs" / "delta" / "20_micro"
    micro.mkdir(parents=True, exist_ok=True)
    (micro / f"{feature}.md").write_text(
        inject_after_header("# Micro\n\n", delta_micro_navigation_block(feature)),
        encoding="utf-8",
    )


def _enable_unified(paths: RepoPaths) -> None:
    write_project_profile(
        paths.root,
        profile="minimal",
        project_name="demo",
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED,
    )


def test_record_and_check_wiring_audit(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_handoff(paths, "my-feature")

    out = record_wiring_audit(paths, evidence="pytest tests/test_wiring_audit.py -q")
    assert out.is_file()

    report = check_wiring_audit(paths)
    assert report.ok
    assert report.feature == "my-feature"


def test_check_fails_without_attestation(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_handoff(paths, "my-feature")

    report = check_wiring_audit(paths)
    assert not report.ok
    assert "Missing wiring audit attestation" in report.detail


def test_check_fails_on_feature_mismatch(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("feat-a"), encoding="utf-8")
    _write_handoff(paths, "feat-a")
    _write_handoff(paths, "feat-b")
    record_wiring_audit(paths, feature="feat-b", evidence="pytest -q")

    report = check_wiring_audit(paths, feature="feat-a")
    assert not report.ok
    assert any("attestation feature" in item for item in report.missing)


def test_check_fails_on_unchecked_tasks_checklist(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_handoff(paths, "my-feature", wiring_checked=True)
    record_wiring_audit(paths, evidence="pytest -q")

    tasks_path = paths.root / "docs" / "specs" / "my-feature" / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace("- [x]", "- [ ]", 1),
        encoding="utf-8",
    )

    report = check_wiring_audit(paths)
    assert not report.ok
    assert any("checklist incomplete" in item for item in report.missing)


def test_check_fails_on_unchecked_alternate_wiring_heading(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_handoff(paths, "my-feature", wiring_checked=True)
    record_wiring_audit(paths, evidence="pytest -q")
    tasks_path = paths.root / "docs" / "specs" / "my-feature" / "tasks.md"
    tasks_path.write_text(
        "# Tasks\n\n## Integration wiring audit\n\n- [ ] Traced caller end-to-end\n",
        encoding="utf-8",
    )

    report = check_wiring_audit(paths)
    assert not report.ok
    assert any("checklist incomplete" in item for item in report.missing)


def test_record_and_check_fail_when_checklist_section_is_missing(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_handoff(paths, "my-feature", wiring_checked=False)

    with pytest.raises(WiringAuditError, match="missing Integration wiring audit checklist"):
        record_wiring_audit(paths, evidence="pytest -q")
    assert not (paths.root / ".hive" / "wiring-audit.json").exists()

    _write_handoff(paths, "my-feature", wiring_checked=True)
    record_wiring_audit(paths, evidence="pytest -q")
    tasks_path = paths.root / "docs" / "specs" / "my-feature" / "tasks.md"
    tasks_path.write_text("# Tasks\n\n- [x] T001 done\n", encoding="utf-8")
    report = check_wiring_audit(paths)
    assert not report.ok
    assert any("missing Integration wiring audit checklist" in item for item in report.missing)


def test_agents_propose_blocked_without_wiring_audit(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_handoff(paths, "my-feature")
    _enable_unified(paths)

    candidates = paths.root / "candidates.md"
    candidates.write_text("- New durable operational fact.\n", encoding="utf-8")

    with pytest.raises(AgentsMemoryError, match="wiring audit"):
        run_agents_memory(paths, candidates)


def test_agents_propose_passes_with_attestation(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_handoff(paths, "my-feature")
    _enable_unified(paths)
    record_wiring_audit(paths, evidence="pytest -q")

    candidates = paths.root / "candidates.md"
    candidates.write_text("- New durable operational fact.\n", encoding="utf-8")

    result = run_agents_memory(paths, candidates, skip_wiring_audit=False)
    assert result.proposal_path.is_file()


def test_wiring_audit_enforced_for_unified_profile(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _enable_unified(paths)
    assert wiring_audit_enforced(paths)


def test_record_requires_evidence(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    with pytest.raises(WiringAuditError, match="evidence"):
        record_wiring_audit(paths, evidence="  ")


def test_ci_check_includes_wiring_audit_step(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_handoff(paths, "my-feature")
    _enable_unified(paths)
    record_wiring_audit(paths, evidence="pytest -q")

    report = run_ci_check(paths, skip_pytest=True, check_map_drift=False, check_roadmap=False)
    wiring = next(s for s in report.steps if s.name == "wiring-audit")
    assert wiring.ok


def test_stale_attestation_fails(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_handoff(paths, "my-feature")
    record_wiring_audit(paths, evidence="pytest -q", max_age_hours=1)

    audit_path = paths.root / ".hive" / "wiring-audit.json"
    import json

    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["recorded_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    audit_path.write_text(json.dumps(payload), encoding="utf-8")

    report = check_wiring_audit(paths)
    assert not report.ok
    assert any("stale" in item for item in report.missing)
