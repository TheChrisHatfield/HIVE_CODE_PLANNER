from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.cartridge_promote import promote_cartridge_drafts
from hive_planner.config import RepoPaths
from hive_planner.translator import DRAFT_BANNER


def _unified_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")
    (root / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")
    (root / "docs" / "cl-spec-integration.md").write_text("# CL + Spec\n", encoding="utf-8")
    hive = root / ".hive"
    hive.mkdir(exist_ok=True)
    (hive / "project.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "bootstrap_profile": "minimal",
                "project_name": "test",
                "agent_handoff_mode": "unified",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## Active feature",
                "",
                "**None** — set when Spec Kit work begins.",
                "",
                "## Durable Workspace Facts",
                "",
            ]
        ),
        encoding="utf-8",
    )
    RepoPaths(root=root).ensure_dirs()
    return root


def test_promote_micro_and_spec_scaffold_from_draft(tmp_path: Path) -> None:
    project = _unified_project(tmp_path / "proj")
    feature = "my-feature"
    paths = RepoPaths(root=project)
    micro = paths.cartridge / "micro" / f"{feature}.md"
    micro.parent.mkdir(parents=True, exist_ok=True)
    micro.write_text(
        f"{DRAFT_BANNER}\n\n# Micro Brief: {feature}\n\n- Acceptance criteria: emit works.\n",
        encoding="utf-8",
    )

    result = promote_cartridge_drafts(paths, feature)

    assert result.promotions["micro"] == "written"
    assert (project / "docs" / "delta" / "20_micro" / f"{feature}.md").is_file()
    assert (project / "docs" / "specs" / feature / "spec.md").is_file()
    assert (project / "docs" / "specs" / feature / "plan.md").is_file()
    assert (project / "docs" / "specs" / feature / "tasks.md").is_file()
    assert result.handoff is not None
    assert result.handoff["ok"] is True


def test_promote_memory_writes_classified_candidates(tmp_path: Path) -> None:
    project = _unified_project(tmp_path / "proj")
    feature = "mem-feature"
    paths = RepoPaths(root=project)
    memory = paths.cartridge / "memory.md"
    memory.write_text(
        "\n".join(
            [
                DRAFT_BANNER,
                "",
                "# Memory Candidates (draft)",
                "",
                "- Run ci-check before handoff.",
                "- API must return 404 when disabled.",
            ]
        ),
        encoding="utf-8",
    )

    result = promote_cartridge_drafts(paths, feature)

    assert result.candidates_path is not None
    text = (project / result.candidates_path).read_text(encoding="utf-8")
    assert "# operational" in text
    assert "ci-check" in text
    assert "# behavioral" in text
    assert "404" in text


def test_promote_skips_when_spec_kit_disabled(tmp_path: Path) -> None:
    project = tmp_path / "plain"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    paths = RepoPaths(root=project)
    paths.ensure_dirs()
    (paths.cartridge / "micro" / "x.md").parent.mkdir(parents=True, exist_ok=True)
    (paths.cartridge / "micro" / "x.md").write_text(f"{DRAFT_BANNER}\n\n# x\n", encoding="utf-8")

    result = promote_cartridge_drafts(paths, "x-feature")

    assert "Spec Kit disabled" in result.warnings[0]
    assert not (project / "docs" / "delta" / "20_micro" / "x-feature.md").exists()


def test_promote_skips_non_draft_cartridge(tmp_path: Path) -> None:
    project = _unified_project(tmp_path / "proj")
    feature = "locked"
    paths = RepoPaths(root=project)
    target = project / "docs" / "delta" / "20_micro" / f"{feature}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Existing truth\n", encoding="utf-8")
    micro = paths.cartridge / "micro" / f"{feature}.md"
    micro.parent.mkdir(parents=True, exist_ok=True)
    micro.write_text("# Not a draft\n\n- keep\n", encoding="utf-8")

    result = promote_cartridge_drafts(paths, feature)

    assert result.promotions["micro"] == "skipped (not draft)"
    assert target.read_text(encoding="utf-8") == "# Existing truth\n"
