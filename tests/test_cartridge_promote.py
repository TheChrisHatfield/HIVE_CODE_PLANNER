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
                "## Planning Rosetta Stone (required anchor)",
                "",
                "- **Hook ID:** `planning.rosetta`",
                "- **File:** `docs/planning-rosetta-stone.md`",
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
    tasks_text = (project / "docs" / "specs" / feature / "tasks.md").read_text(encoding="utf-8")
    assert "Integration wiring audit" in tasks_text
    spec_text = (project / "docs" / "specs" / feature / "spec.md").read_text(encoding="utf-8")
    assert "Agent navigation (Rosetta Stone)" in spec_text
    assert "planning.rosetta" in spec_text
    assert result.handoff is not None
    assert result.handoff["ok"] is True


def test_promote_appends_wiring_audit_to_existing_tasks(tmp_path: Path) -> None:
    project = _unified_project(tmp_path / "proj")
    feature = "legacy-feature"
    paths = RepoPaths(root=project)
    spec_dir = project / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "tasks.md").write_text(
        "# Tasks: legacy-feature\n\n- [ ] Old task without audit\n",
        encoding="utf-8",
    )
    micro = paths.cartridge / "micro" / f"{feature}.md"
    micro.parent.mkdir(parents=True, exist_ok=True)
    micro.write_text(
        f"{DRAFT_BANNER}\n\n# Micro Brief: {feature}\n\n- Acceptance criteria: emit works.\n",
        encoding="utf-8",
    )

    result = promote_cartridge_drafts(paths, feature)

    tasks_text = (spec_dir / "tasks.md").read_text(encoding="utf-8")
    assert "Integration wiring audit" in tasks_text
    assert result.promotions.get("tasks") == "updated (wiring audit)"


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
    assert "(none classified)" not in text


def test_promote_memory_skips_empty_candidate_sections(tmp_path: Path) -> None:
    project = _unified_project(tmp_path / "proj")
    feature = "empty-mem"
    paths = RepoPaths(root=project)
    (paths.cartridge / "memory.md").write_text(
        f"{DRAFT_BANNER}\n\n# Memory\n\n",
        encoding="utf-8",
    )

    result = promote_cartridge_drafts(paths, feature)

    assert result.promotions["memory_candidates"] == "skipped (no bullets)"
    assert result.candidates_path is None


def test_promote_memory_stages_ambiguous_bullets_separately(tmp_path: Path) -> None:
    project = _unified_project(tmp_path / "proj")
    feature = "mixed-mem"
    paths = RepoPaths(root=project)
    (paths.cartridge / "memory.md").write_text(
        "\n".join(
            [
                DRAFT_BANNER,
                "",
                "# Memory Candidates (draft)",
                "",
                "- Run ci-check before handoff; API must return 404 when disabled.",
            ]
        ),
        encoding="utf-8",
    )

    result = promote_cartridge_drafts(paths, feature)

    assert result.candidates_path is not None
    text = (project / result.candidates_path).read_text(encoding="utf-8")
    assert "# ambiguous" in text
    assert "404 when disabled" in text
    assert "# operational" in text


def test_promote_skips_when_spec_kit_disabled(tmp_path: Path) -> None:
    project = tmp_path / "plain"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    paths = RepoPaths(root=project)
    paths.ensure_dirs()
    (paths.cartridge / "micro" / "x.md").parent.mkdir(parents=True, exist_ok=True)
    (paths.cartridge / "micro" / "x.md").write_text(f"{DRAFT_BANNER}\n\n# x\n", encoding="utf-8")

    result = promote_cartridge_drafts(paths, "x-feature")

    assert "Agent handoff off" in result.warnings[0]
    assert result.ok is False
    assert result.promotions.get("status") == "skipped (agent handoff off)"
    assert not (project / "docs" / "delta" / "20_micro" / "x-feature.md").exists()


def test_promote_patches_existing_spec_with_rosetta_navigation(tmp_path: Path) -> None:
    project = _unified_project(tmp_path / "proj")
    feature = "hive-dev-v1"
    paths = RepoPaths(root=project)
    spec_dir = project / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text(
        "\n".join(
            [
                "# Spec: hive-dev-v1",
                "",
                "**Hook:** `spec.flow`",
                "",
                "## Requirements",
                "",
                "- GPU limit",
                "",
            ]
        ),
        encoding="utf-8",
    )
    micro = paths.cartridge / "micro" / f"{feature}.md"
    micro.parent.mkdir(parents=True, exist_ok=True)
    micro.write_text(f"{DRAFT_BANNER}\n\n# Micro\n\n- acceptance\n", encoding="utf-8")

    result = promote_cartridge_drafts(paths, feature)

    spec_text = (spec_dir / "spec.md").read_text(encoding="utf-8")
    assert "Agent navigation (Rosetta Stone)" in spec_text
    assert result.rosetta_repair is not None
    assert "patched navigation" in result.rosetta_repair["detail"] or "Planning Rosetta Stone" in (
        result.rosetta_repair.get("detail") or ""
    )


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
    assert result.rosetta_repair is None


def test_promote_nothing_written_guidance_for_import_style_cartridge(tmp_path: Path) -> None:
    from hive_planner.cartridge_promote import promote_nothing_written_guidance

    project = _unified_project(tmp_path / "proj")
    paths = RepoPaths(root=project)
    (paths.cartridge / "HIVE_DEV_V1.md").write_text("# Imported content\n", encoding="utf-8")

    result = promote_cartridge_drafts(paths, "example-feature")
    guidance = promote_nothing_written_guidance(result)

    assert guidance is not None
    assert "example-feature" in guidance
    assert "DRAFT" in guidance
    assert "Import with Promote adapts" in guidance


def test_mark_cartridge_layers_draft_prepends_banner(tmp_path: Path) -> None:
    from hive_planner.cartridge_promote import mark_cartridge_layers_draft
    from hive_planner.delta_emit import AUTO_SYNC_PREFIX

    project = _unified_project(tmp_path / "proj")
    feature = "example-feature"
    paths = RepoPaths(root=project)
    holistic = paths.cartridge / "holistic.md"
    holistic.parent.mkdir(parents=True, exist_ok=True)
    holistic.write_text(f"{AUTO_SYNC_PREFIX} from docs/delta -->\n\n# Holistic\n", encoding="utf-8")

    results = mark_cartridge_layers_draft(paths, feature)

    assert results["holistic"] == "marked draft"
    assert holistic.read_text(encoding="utf-8").startswith(DRAFT_BANNER)
    assert results["macro"] == "skipped (missing)"


def test_mark_cartridge_layers_draft_skips_already_draft(tmp_path: Path) -> None:
    from hive_planner.cartridge_promote import mark_cartridge_layers_draft

    project = _unified_project(tmp_path / "proj")
    feature = "example-feature"
    paths = RepoPaths(root=project)
    micro = paths.cartridge / "micro" / f"{feature}.md"
    micro.parent.mkdir(parents=True, exist_ok=True)
    micro.write_text(f"{DRAFT_BANNER}\n\n# Micro\n", encoding="utf-8")

    results = mark_cartridge_layers_draft(paths, feature)

    assert results["micro"] == "already draft"


def test_promote_does_not_warn_for_autosync_cartridge_layers(tmp_path: Path) -> None:
    from hive_planner.delta_emit import AUTO_SYNC_PREFIX

    project = _unified_project(tmp_path / "proj")
    feature = "emit-feature"
    paths = RepoPaths(root=project)
    for rel in ("holistic.md", "macro.md", f"micro/{feature}.md"):
        path = paths.cartridge / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{AUTO_SYNC_PREFIX} from docs/delta -->\n\n# Layer\n", encoding="utf-8")

    result = promote_cartridge_drafts(paths, feature, run_spec_drift=False)

    assert result.promotions["holistic"] == "skipped (not draft)"
    assert not any("holistic:" in w for w in result.warnings)
    assert not any("macro:" in w for w in result.warnings)


def test_promote_cli_exit_code_handoff_off_is_success(tmp_path: Path) -> None:
    from hive_planner.cartridge_promote import promote_cli_exit_code

    project = tmp_path / "plain"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    result = promote_cartridge_drafts(RepoPaths(root=project), "my-feature")

    assert promote_cli_exit_code(result) == 0
    assert promote_cli_exit_code(result.to_dict()) == 0


def test_promote_cli_exit_code_spec_drift_failure(tmp_path: Path) -> None:
    from hive_planner.cartridge_promote import promote_cli_exit_code

    payload = {"ok": False, "promotions": {"micro": "written"}}
    assert promote_cli_exit_code(payload) == 1
