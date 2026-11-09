from __future__ import annotations

from pathlib import Path

from hive_planner.config import RepoPaths
from hive_planner.rosetta_nav import (
    delta_micro_navigation_block,
    inject_after_header,
    plan_navigation_block,
    spec_navigation_block,
    tasks_navigation_block,
)
from hive_planner.spec_drift import (
    SPEC_CREATION_SPEC_TAIL,
    SPEC_CREATION_TASKS_TAIL,
    check_memory_spec_drift,
)

FEATURE = "feat"
SPEC_BODY = "# Spec\n\nAPI must return 404 when the feature flag is disabled.\n"


def _agents(feature: str = FEATURE) -> str:
    return (
        "# AGENTS.md\n\n"
        "## Planning Rosetta Stone\n\n- hook `planning.rosetta`\n\n"
        f"## Active feature\n\n**{feature}**\n\n"
        "## Durable Workspace Facts\n\n- Run `py -3.11 -m hive_planner ci-check` before handoff.\n"
    )


def _write_handoff(paths: RepoPaths, spec_body: str) -> None:
    spec_dir = paths.root / "docs" / "specs" / FEATURE
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec.md").write_text(
        inject_after_header(spec_body, spec_navigation_block(FEATURE)) + SPEC_CREATION_SPEC_TAIL,
        encoding="utf-8",
    )
    (spec_dir / "plan.md").write_text(
        inject_after_header("# Plan\n\n", plan_navigation_block(FEATURE)),
        encoding="utf-8",
    )
    (spec_dir / "tasks.md").write_text(
        inject_after_header("# Tasks\n\n", tasks_navigation_block(FEATURE)) + SPEC_CREATION_TASKS_TAIL,
        encoding="utf-8",
    )
    micro = paths.root / "docs" / "delta" / "20_micro"
    micro.mkdir(parents=True, exist_ok=True)
    (micro / f"{FEATURE}.md").write_text(
        inject_after_header("# Micro\n\n", delta_micro_navigation_block(FEATURE)),
        encoding="utf-8",
    )


def _write_specseed(paths: RepoPaths, spec_text: str) -> None:
    """Mirror the full spec.md the way emit does: AUTO-SYNC comment, seed title, then the spec."""
    seed_dir = paths.root / "cartridge" / "specs"
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / f"{FEATURE}.specseed.md").write_text(
        "<!-- AUTO-SYNC: from docs/specs/feat/spec.md -->\n\n"
        f"# Spec seed: {FEATURE}\n\n{spec_text}",
        encoding="utf-8",
    )


def _spec_file_text(paths: RepoPaths) -> str:
    return (paths.root / "docs" / "specs" / FEATURE / "spec.md").read_text(encoding="utf-8")


def _project(tmp_path: Path) -> RepoPaths:
    paths = RepoPaths(root=tmp_path)
    (paths.root / "AGENTS.md").write_text(_agents(), encoding="utf-8")
    _write_handoff(paths, SPEC_BODY)
    return paths


def test_specseed_divergence_from_spec_is_drift(tmp_path: Path) -> None:
    """Red before T019: check_memory_spec_drift never read the specseed, so divergence passed."""
    paths = _project(tmp_path)
    _write_specseed(paths, _spec_file_text(paths).replace("404", "200"))

    report = check_memory_spec_drift(paths, feature=FEATURE, include_agents_facts=False)

    assert report.ok is False
    assert any("specseed" in action.lower() for action in report.spec_actions)


def test_matching_specseed_is_not_drift(tmp_path: Path) -> None:
    paths = _project(tmp_path)
    _write_specseed(paths, _spec_file_text(paths))

    report = check_memory_spec_drift(paths, feature=FEATURE, include_agents_facts=False)

    assert report.ok is True
    assert not any("specseed" in action.lower() for action in report.spec_actions)


def test_missing_specseed_is_skipped_not_failed(tmp_path: Path) -> None:
    paths = _project(tmp_path)

    report = check_memory_spec_drift(paths, feature=FEATURE, include_agents_facts=False)

    assert report.ok is True
    assert not any("specseed" in action.lower() for action in report.spec_actions)
