from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.agents_memory import AgentsMemoryError, propose_agents_memory
from hive_planner.ci_handoff import run_ci_check
from hive_planner.config import RepoPaths
from hive_planner.spec_drift import (
    ACTIVE_FEATURE_SECTION_RE,
    BOOTSTRAP_DEFAULT_FEATURE,
    check_memory_spec_drift,
    check_spec_handoff,
    classify_bullet,
    parse_active_feature,
    repair_agents_active_feature,
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
        inject_after_header(spec_body, spec_navigation_block(feature)),
        encoding="utf-8",
    )
    (spec_dir / "plan.md").write_text(
        inject_after_header(f"# Plan\n\n", plan_navigation_block(feature)),
        encoding="utf-8",
    )
    (spec_dir / "tasks.md").write_text(
        inject_after_header(f"# Tasks\n\n", tasks_navigation_block(feature)),
        encoding="utf-8",
    )
    micro = paths.root / "docs" / "delta" / "20_micro"
    micro.mkdir(parents=True, exist_ok=True)
    (micro / f"{feature}.md").write_text(
        inject_after_header(f"# Micro\n\n", delta_micro_navigation_block(feature)),
        encoding="utf-8",
    )


def test_classify_operational_bullet() -> None:
    result = classify_bullet("Run `py -3.11 -m hive_planner ci-check` before handoff.")
    assert result.kind == "operational"


def test_classify_behavioral_bullet() -> None:
    result = classify_bullet("API must return 404 when the feature flag is disabled.")
    assert result.kind == "behavioral"


def test_classify_respects_tags() -> None:
    assert classify_bullet("Anything # operational").kind == "operational"
    assert classify_bullet("Anything # behavioral").kind == "behavioral"


def test_classify_mixed_signals_without_tag_is_ambiguous() -> None:
    result = classify_bullet("Run ci-check before handoff; API must return 404 when disabled.")
    assert result.kind == "ambiguous"


def test_classify_strong_behavioral_beats_weak_operational() -> None:
    result = classify_bullet(
        "Run ci-check; API must validate payloads and returns 404 when schema version mismatches."
    )
    assert result.kind == "behavioral"


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


def test_infer_repairable_active_feature_ignores_missing_rosetta_nav(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS",
                "",
                "## Planning Rosetta Stone",
                "",
                "- hook `planning.rosetta`",
                "",
                "## Active feature",
                "",
                "**None** — pending.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    feature = "example-feature"
    spec_dir = paths.root / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (spec_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (spec_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    micro = paths.root / "docs" / "delta" / "20_micro"
    micro.mkdir(parents=True)
    (micro / f"{feature}.md").write_text("# Micro\n", encoding="utf-8")

    from hive_planner.spec_drift import infer_repairable_active_feature

    assert infer_repairable_active_feature(paths) == feature
    handoff = check_spec_handoff(paths, feature)
    assert handoff.ok is False


def test_check_spec_handoff_requires_full_trio(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    report = check_spec_handoff(paths)
    assert not report.ok
    assert any("plan.md" in m for m in report.missing)

    _write_full_handoff(paths, "my-feature")
    report = check_spec_handoff(paths)
    assert report.ok


def test_check_spec_handoff_requires_rosetta_navigation(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    spec_dir = paths.root / "docs" / "specs" / "my-feature"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (spec_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (spec_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    micro = paths.root / "docs" / "delta" / "20_micro"
    micro.mkdir(parents=True)
    (micro / "my-feature.md").write_text("# Micro\n", encoding="utf-8")

    report = check_spec_handoff(paths)

    assert not report.ok
    assert any("Rosetta navigation" in item for item in report.missing)


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


def test_spec_drift_ignores_checkbox_lines_in_candidates(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_full_handoff(paths, "my-feature")
    candidates = paths.root / "candidates.md"
    candidates.write_text(
        "- Run ci-check before handoff.\n- [ ] Traced caller end-to-end\n",
        encoding="utf-8",
    )
    report = check_memory_spec_drift(paths, candidates_path=candidates)
    assert report.ok
    assert any("Run ci-check before handoff." in b for b in report.operational)
    assert not any(b.startswith("[ ]") for b in report.operational + report.behavioral + report.ambiguous)


def test_propose_rejects_ambiguous_candidate(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("my-feature"), encoding="utf-8")
    _write_full_handoff(paths, "my-feature")
    candidates = paths.root / "candidates.md"
    candidates.write_text("- Run ci-check before handoff; API must return 404 when disabled.\n", encoding="utf-8")
    with pytest.raises(AgentsMemoryError, match="All candidate"):
        propose_agents_memory(paths, candidates)


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


def test_repair_agents_active_feature_fixes_legacy_none(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("none"), encoding="utf-8")
    _write_full_handoff(paths, BOOTSTRAP_DEFAULT_FEATURE)
    result = repair_agents_active_feature(paths)
    assert result.repaired is True
    assert result.feature == BOOTSTRAP_DEFAULT_FEATURE
    assert parse_active_feature(paths) == BOOTSTRAP_DEFAULT_FEATURE


def test_repair_agents_active_feature_uses_unified_body(tmp_path: Path) -> None:
    from hive_planner.agent_handoff import apply_agent_handoff_mode, AGENT_HANDOFF_UNIFIED
    from hive_planner.project_profile import write_project_profile

    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("none"), encoding="utf-8")
    _write_full_handoff(paths, BOOTSTRAP_DEFAULT_FEATURE)
    write_project_profile(paths.root, profile="minimal", project_name="demo", agent_handoff_mode=AGENT_HANDOFF_UNIFIED)
    result = repair_agents_active_feature(paths)
    assert result.repaired is True
    body = ACTIVE_FEATURE_SECTION_RE.search((paths.root / "AGENTS.md").read_text(encoding="utf-8")).group(2)
    assert "unified Spec Kit + Continual Learning" in body


def test_repair_agents_active_feature_skips_when_handoff_missing(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_minimal_agents("none"), encoding="utf-8")
    result = repair_agents_active_feature(paths)
    assert result.repaired is False
