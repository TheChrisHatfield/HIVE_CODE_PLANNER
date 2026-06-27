from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.agents_memory import AgentsMemoryError, propose_agents_memory
from hive_planner.ci_handoff import run_ci_check
from hive_planner.config import RepoPaths
from hive_planner.spec_drift import (
    check_memory_spec_drift,
    check_spec_handoff,
    classify_bullet,
    parse_active_feature,
)


def _minimal_agents(feature: str = "feature-x") -> str:
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

- Run `py -3.11 -m hive_planner ci-check` before handoff.
"""


def _write_full_handoff(paths: RepoPaths, feature: str, spec_body: str = "# Spec\n") -> None:
    spec_dir = paths.root / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec.md").write_text(spec_body, encoding="utf-8")
    (spec_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (spec_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    micro = paths.root / "docs" / "delta" / "20_micro"
    micro.mkdir(parents=True, exist_ok=True)
    (micro / f"{feature}.md").write_text("# Micro\n", encoding="utf-8")


def test_classify_operational_bullet() -> None:
    result = classify_bullet("Run `py -3.11 -m hive_planner ci-check` before handoff.")
    assert result.kind == "operational"


def test_classify_behavioral_bullet() -> None:
    result = classify_bullet("API must return 404 when the feature flag is disabled.")
    assert result.kind == "behavioral"


def test_classify_respects_tags() -> None:
    assert classify_bullet("Anything # operational").kind == "operational"
    assert classify_bullet("Anything # behavioral").kind == "behavioral"


def test_classify_ignores_tag_words_in_prose() -> None:
    result = classify_bullet("See planning.rosetta docs; not a # behavioral tag in prose here")
    assert result.kind == "operational"


def test_spec_drift_missing_candidates_file(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_full_handoff(paths, "my-feature")
    report = check_memory_spec_drift(paths, candidates_path=Path("missing.md"))
    assert not report.ok
    assert any("not found" in a for a in report.spec_actions)


def test_propose_accepts_operational_rejects_behavioral_mixed(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_full_handoff(paths, "my-feature")
    candidates = paths.root / "candidates.md"
    candidates.write_text(
        "- Run ci-check before handoff.\n- API must return 404 when flag disabled.\n",
        encoding="utf-8",
    )
    out = propose_agents_memory(paths, candidates)
    proposal = out.read_text(encoding="utf-8")
    assert "Run ci-check" in proposal
    assert "Rejected candidates" in proposal
    assert "Spec Kit actions required" in proposal


def test_check_spec_handoff_requires_full_trio(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    report = check_spec_handoff(paths)
    assert not report.ok
    assert any("plan.md" in m for m in report.missing)

    _write_full_handoff(paths, "my-feature")
    report = check_spec_handoff(paths)
    assert report.ok


def test_spec_drift_flags_behavioral_not_in_spec(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_full_handoff(paths, "my-feature", spec_body="# Spec\n\nOperational only.\n")

    agents_text = _minimal_agents("my-feature")
    agents_text = agents_text.replace(
        "- Run `py -3.11 -m hive_planner ci-check` before handoff.",
        "- API must return 404 when feature flag disabled.",
    )
    (paths.root / "AGENTS.md").write_text(agents_text, encoding="utf-8")

    report = check_memory_spec_drift(paths)
    assert not report.ok
    assert report.drift_items


def test_ci_check_includes_spec_drift_step(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_full_handoff(paths, "my-feature")
    report = run_ci_check(paths, skip_pytest=True, check_map_drift=False, check_roadmap=False)
    names = [s.name for s in report.steps]
    assert "spec-drift" in names
    drift = next(s for s in report.steps if s.name == "spec-drift")
    assert drift.ok


def test_propose_rejects_behavioral_candidate(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_full_handoff(paths, "my-feature")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- API must validate manifest schema version.\n", encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="All candidate"):
        propose_agents_memory(paths, candidates)


def test_spec_drift_dedupes_agents_and_candidates(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_full_handoff(paths, "my-feature", spec_body="# Spec\n\nOperational only.\n")
    agents_text = _minimal_agents("my-feature").replace(
        "- Run `py -3.11 -m hive_planner ci-check` before handoff.",
        "- API must return 404 when feature flag disabled.",
    )
    (paths.root / "AGENTS.md").write_text(agents_text, encoding="utf-8")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- API must return 404 when feature flag disabled.\n", encoding="utf-8")
    report = check_memory_spec_drift(paths, candidates_path=candidates)
    assert len(report.drift_items) == 1


def test_spec_drift_agents_facts_use_active_feature_spec(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("feat-a"), encoding="utf-8")
    _write_full_handoff(paths, "feat-a", spec_body="# Spec\n\nNo behavioral match here.\n")
    _write_full_handoff(paths, "feat-b", spec_body="# Spec\n\nAPI must return 404 when disabled.\n")
    agents_text = _minimal_agents("feat-a").replace(
        "- Run `py -3.11 -m hive_planner ci-check` before handoff.",
        "- API must return 404 when disabled.",
    )
    (paths.root / "AGENTS.md").write_text(agents_text, encoding="utf-8")
    report = check_memory_spec_drift(paths, feature="feat-b", include_agents_facts=True)
    assert not report.ok
    assert report.drift_items


def test_spec_drift_dedupes_report_lists(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_full_handoff(paths, "my-feature", spec_body="# Spec\n\nOperational only.\n")
    agents_text = _minimal_agents("my-feature").replace(
        "- Run `py -3.11 -m hive_planner ci-check` before handoff.",
        "- API must return 404 when feature flag disabled.",
    )
    (paths.root / "AGENTS.md").write_text(agents_text, encoding="utf-8")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- API must return 404 when feature flag disabled.\n", encoding="utf-8")
    report = check_memory_spec_drift(paths, candidates_path=candidates)
    assert len(report.drift_items) == 1
    assert len(report.behavioral) == 1


def test_parse_active_feature(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("git-handoff-ci-v1"), encoding="utf-8")
    assert parse_active_feature(paths) == "git-handoff-ci-v1"


def test_parse_active_feature_rejects_placeholder_none(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("none"), encoding="utf-8")
    assert parse_active_feature(paths) is None
