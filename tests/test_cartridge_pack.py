from __future__ import annotations

import json
from pathlib import Path

from hive_planner.cartridge_pack import (
    build_source_map,
    emit_cartridge_pack,
    validate_pack_completeness,
)
from hive_planner.delta_emit import AUTO_SYNC_PREFIX
from hive_planner.config import RepoPaths
from hive_planner.emitter import emit_cartridge


def _write_feature_tree(paths: RepoPaths, feature: str) -> None:
    delta = paths.root / "docs" / "delta"
    delta.mkdir(parents=True, exist_ok=True)
    (delta / "00_holistic.md").write_text("# Holistic\n\nMission\n", encoding="utf-8")
    (delta / "10_macro.md").write_text("# Macro\n\nArch\n", encoding="utf-8")
    micro_dir = delta / "20_micro"
    micro_dir.mkdir(parents=True, exist_ok=True)
    (micro_dir / f"{feature}.md").write_text(
        "\n".join(
            [
                f"# {feature}",
                "",
                "## Holistic Link",
                "",
                "Test holistic link.",
                "",
                "## Scope",
                "",
                "In scope only.",
                "",
                "## Validation",
                "",
                "pytest",
                "",
            ]
        ),
        encoding="utf-8",
    )
    spec_dir = paths.root / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec.md").write_text("# Spec\n\n## What\n\nPack test feature.\n", encoding="utf-8")
    (paths.root / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS",
                "",
                "## Durable Workspace Facts",
                "",
                "- Use Python 3.11 for tests.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_build_source_map_includes_feature() -> None:
    data = build_source_map("cartridge-pack-v1")
    assert data["feature"] == "cartridge-pack-v1"
    assert any(m["layer"] == "micro" for m in data["mappings"])


def test_emit_cartridge_pack_writes_files(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v1"
    _write_feature_tree(paths, feature)

    _, results, _ = emit_cartridge_pack(paths, feature, force=True)
    assert (paths.cartridge / "research-summary.md").exists()
    assert (paths.cartridge / "memory.md").exists()
    assert (paths.cartridge / "mappings" / "source-map.json").exists()
    assert (paths.cartridge / "specs" / f"{feature}.specseed.md").exists()
    assert results["research_summary"] in {"written", "updated"}


def test_research_summary_updates_on_re_emit(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v1"
    _write_feature_tree(paths, feature)

    emit_cartridge_pack(paths, feature)
    first = (paths.cartridge / "research-summary.md").read_text(encoding="utf-8")
    assert first.startswith(AUTO_SYNC_PREFIX)

    micro = paths.root / "docs" / "delta" / "20_micro" / f"{feature}.md"
    micro.write_text(micro.read_text(encoding="utf-8").replace("Test holistic link.", "Updated finding."), encoding="utf-8")

    _, results, _ = emit_cartridge_pack(paths, feature)
    second = (paths.cartridge / "research-summary.md").read_text(encoding="utf-8")
    assert results["research_summary"] == "updated"
    assert "Updated finding." in second


def test_specseed_auto_sync_updates_without_force(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v1"
    _write_feature_tree(paths, feature)

    emit_cartridge_pack(paths, feature)
    specseed = paths.cartridge / "specs" / f"{feature}.specseed.md"
    assert specseed.read_text(encoding="utf-8").startswith(AUTO_SYNC_PREFIX)

    spec = paths.root / "docs" / "specs" / feature / "spec.md"
    spec.write_text("# Spec\n\n## What\n\nRevised pack feature.\n", encoding="utf-8")

    _, results, _ = emit_cartridge_pack(paths, feature)
    assert results["specseed"] == "updated"
    assert "Revised pack feature." in specseed.read_text(encoding="utf-8")


def test_validate_pack_completeness_reports_missing(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    assert validate_pack_completeness(paths) == [
        "cartridge/manifest.json",
        "cartridge/research-summary.md",
        "cartridge/holistic.md",
        "cartridge/macro.md",
        "cartridge/memory.md",
        "cartridge/source-context.md",
        "cartridge/mappings/source-map.json",
    ]


def test_emit_cartridge_manifest_lists_files(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v1"
    _write_feature_tree(paths, feature)

    outputs, _ = emit_cartridge(paths, feature, force_delta=True)
    assert "manifest" in outputs
    manifest = json.loads((paths.cartridge / "manifest.json").read_text(encoding="utf-8"))
    assert "files" in manifest
    assert "cartridge/research-summary.md" in manifest["files"]
    assert "pack_sync" in manifest["stats"]
