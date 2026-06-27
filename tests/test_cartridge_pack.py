from __future__ import annotations

import json
from pathlib import Path

from hive_planner.cartridge_pack import (
    RULE_SEED_DRAFT_BANNER,
    build_rule_seed_body,
    build_source_map,
    emit_cartridge_pack,
    emit_rules_seed,
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
    assert any(m["layer"] == "cursor_rule_seed" for m in data["mappings"])


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
    assert manifest["targets"]["cursor_rules"] is False


def test_emit_rules_seed_writes_draft_seed(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v2"
    _write_feature_tree(paths, feature)

    status, seed_path, _ = emit_rules_seed(paths, feature)
    assert status == "written"
    assert seed_path is not None
    content = seed_path.read_text(encoding="utf-8")
    assert content.startswith(RULE_SEED_DRAFT_BANNER)
    assert "alwaysApply: false" in content
    assert "In scope only." in content
    assert "pytest" in content


def test_emit_rules_seed_does_not_touch_cursor_rules(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v2"
    _write_feature_tree(paths, feature)
    rules_dir = paths.root / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)
    live_rule = rules_dir / "architecture.mdc"
    live_rule.write_text("# Live rule\n", encoding="utf-8")

    emit_rules_seed(paths, feature)
    assert live_rule.read_text(encoding="utf-8") == "# Live rule\n"
    assert (paths.cartridge / "rules" / f"{feature}.mdc.seed").exists()


def test_rules_seed_skips_manual_banner(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v2"
    _write_feature_tree(paths, feature)
    seed_path = paths.cartridge / "rules" / f"{feature}.mdc.seed"
    seed_path.parent.mkdir(parents=True)
    seed_path.write_text("<!-- MANUAL: reviewed rule -->\n\n# Custom\n", encoding="utf-8")

    status, path, warnings = emit_rules_seed(paths, feature)
    assert status.startswith("skipped")
    assert path is None
    assert seed_path.read_text(encoding="utf-8").startswith("<!-- MANUAL:")
    assert any("Skipped" in w for w in warnings)


def test_rules_seed_updates_on_re_emit(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v2"
    _write_feature_tree(paths, feature)

    emit_rules_seed(paths, feature)
    micro = paths.root / "docs" / "delta" / "20_micro" / f"{feature}.md"
    micro.write_text(micro.read_text(encoding="utf-8").replace("In scope only.", "Expanded scope."), encoding="utf-8")

    status, _, _ = emit_rules_seed(paths, feature)
    seed = (paths.cartridge / "rules" / f"{feature}.mdc.seed").read_text(encoding="utf-8")
    assert status == "updated"
    assert "Expanded scope." in seed


def test_emit_cartridge_with_rules_seeds_manifest(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v2"
    _write_feature_tree(paths, feature)

    outputs, _ = emit_cartridge(paths, feature, force_delta=True, emit_rules_seeds=True)
    manifest = json.loads((paths.cartridge / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["targets"]["cursor_rules"] == "seed"
    assert manifest["stats"]["pack_sync"]["rules_seed"] in {"written", "updated"}
    assert "rules_seed" in outputs
    assert f"cartridge/rules/{feature}.mdc.seed" in manifest["files"]


def test_emit_cartridge_pack_rules_seed_disabled_by_default(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v2"
    _write_feature_tree(paths, feature)

    _, results, _ = emit_cartridge_pack(paths, feature, force=True)
    assert results["rules_seed"] == "disabled"
    assert not (paths.cartridge / "rules" / f"{feature}.mdc.seed").exists()


def test_emit_cartridge_rules_seed_manifest_false_when_missing_micro(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    (paths.root / "AGENTS.md").write_text(
        "# AGENTS\n\n## Durable Workspace Facts\n\n- fact\n",
        encoding="utf-8",
    )

    _, warnings = emit_cartridge(paths, "missing-feature", force_delta=True, emit_rules_seeds=True)
    manifest = json.loads((paths.cartridge / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["targets"]["cursor_rules"] is False
    assert manifest["stats"]["pack_sync"]["rules_seed"] == "missing"


def test_emit_cartridge_avoids_duplicate_micro_warnings(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    (paths.root / "AGENTS.md").write_text(
        "# AGENTS\n\n## Durable Workspace Facts\n\n- fact\n",
        encoding="utf-8",
    )

    _, warnings = emit_cartridge(paths, "missing-feature", force_delta=True, emit_rules_seeds=True)
    assert sum("Missing micro brief" in w for w in warnings) == 1


def test_build_rule_seed_body_quotes_yaml_description(tmp_path: Path) -> None:
    from hive_planner.cartridge_pack import _yaml_double_quoted

    assert _yaml_double_quoted("Feature guardrails for feat:colon (review)") == (
        '"Feature guardrails for feat:colon (review)"'
    )

    paths = RepoPaths(root=tmp_path)
    feature = "cartridge-pack-v2"
    _write_feature_tree(paths, feature)
    body = build_rule_seed_body(paths, feature)
    desc_line = next(line for line in body.splitlines() if line.startswith("description:"))
    assert desc_line.startswith('description: "')
    assert desc_line.endswith('"')


def test_build_rule_seed_body_includes_macro_excerpt(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    feature = "cartridge-pack-v2"
    _write_feature_tree(paths, feature)
    body = build_rule_seed_body(paths, feature)
    assert "## Architecture context" in body
    assert "Arch" in body
    assert feature in body


def test_source_map_skips_manual_without_force(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v2"
    _write_feature_tree(paths, feature)
    map_path = paths.cartridge / "mappings" / "source-map.json"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(
        json.dumps({"schema_version": "source-map.v1", "_manual": True, "mappings": []}, indent=2),
        encoding="utf-8",
    )
    manual = map_path.read_text(encoding="utf-8")

    _, results, warnings = emit_cartridge_pack(paths, feature, force=False)
    assert results["source_map"].startswith("skipped")
    assert map_path.read_text(encoding="utf-8") == manual
    assert any("Skipped cartridge/mappings/source-map.json" in w for w in warnings)


def test_source_map_auto_sync_updates_on_re_emit(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v2"
    _write_feature_tree(paths, feature)
    emit_cartridge_pack(paths, feature, force=True)
    first = json.loads((paths.cartridge / "mappings" / "source-map.json").read_text(encoding="utf-8"))
    assert first.get("_auto_sync") is True

    _, results, _ = emit_cartridge_pack(paths, feature, force=False)
    assert results["source_map"] == "updated"


def test_emit_skips_manual_source_context_without_force(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "cartridge-pack-v2"
    _write_feature_tree(paths, feature)
    (paths.root / "AGENTS.md").write_text(
        "# AGENTS\n\n## Durable Workspace Facts\n\n- fact\n",
        encoding="utf-8",
    )
    context_path = paths.cartridge / "source-context.md"
    context_path.write_text("<!-- MANUAL: curated -->\n\n# Source Context\n", encoding="utf-8")
    manual = context_path.read_text(encoding="utf-8")

    _, warnings = emit_cartridge(paths, feature, force_delta=False)
    assert context_path.read_text(encoding="utf-8") == manual
    assert any("Skipped cartridge/source-context.md" in w for w in warnings)
