from __future__ import annotations

from pathlib import Path

from hive_planner.cartridge_adapt import (
    adapt_cartridge_for_promote,
    infer_feature_id,
    slugify_feature_id,
)
from hive_planner.config import RepoPaths
from hive_planner.launcher.service import cartridge_load_needs_feature, run_cartridge_import_folder


def _unified_project(tmp_path: Path) -> Path:
    project = tmp_path
    project.mkdir(parents=True, exist_ok=True)
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "AGENTS.md").write_text(
        "# AGENTS\n\n<!-- HIVE:BEGIN -->Active feature: old<!-- HIVE:END -->\n",
        encoding="utf-8",
    )
    hive = project / ".hive" / "project.json"
    hive.parent.mkdir(parents=True)
    hive.write_text(
        '{"schema_version":"1","bootstrap_profile":"full","project_name":"Proj",'
        '"agent_handoff_mode":"unified","spec_kit_enabled":true,"continual_learning_enabled":true}\n',
        encoding="utf-8",
    )
    return project


def test_slugify_feature_id_from_custom_filename() -> None:
    assert slugify_feature_id("HIVE_DEV_V1") == "hive-dev-v1"
    assert slugify_feature_id("MLP_DECIMACON_DEV_1") == "mlp-decimacon-dev-1"


def test_filename_layer_hint_avoids_dev_false_positive() -> None:
    from hive_planner.cartridge_adapt import _filename_layer_hint

    assert _filename_layer_hint("device-settings.md") is None
    assert _filename_layer_hint("HIVE_DEV_V1.md") == "micro"


def test_infer_feature_id_from_dev_filename() -> None:
    feature = infer_feature_id(
        requested="example-feature",
        imported_rels=["HIVE_DEV_V1.md", "HIVE_PLANNING_V1.md"],
    )
    assert feature == "hive-dev-v1"


def test_adapt_custom_import_names_to_standard_layers(tmp_path: Path) -> None:
    project = _unified_project(tmp_path / "proj")
    paths = RepoPaths(root=project)
    cart = paths.cartridge
    cart.mkdir(parents=True, exist_ok=True)
    (cart / "HIVE_DEV_V1.md").write_text("# Dev scope\n\n- acceptance criteria for hive dev\n", encoding="utf-8")
    (cart / "HIVE_PLANNING_V1.md").write_text("# Planning\n\n- subsystem workflow\n", encoding="utf-8")
    (cart / "MLP_DECIMACON_DEV_1.md").write_text("# MLP\n\n- edge case handling\n", encoding="utf-8")

    result = adapt_cartridge_for_promote(
        paths,
        "hive-dev-v1",
        source_rels=["HIVE_DEV_V1.md", "HIVE_PLANNING_V1.md", "MLP_DECIMACON_DEV_1.md"],
    )

    assert (cart / "macro.md").is_file()
    assert (cart / "micro" / "hive-dev-v1.md").is_file()
    assert result.mappings["HIVE_PLANNING_V1.md"] == "macro.md"
    micro_text = (cart / "micro" / "hive-dev-v1.md").read_text(encoding="utf-8")
    assert "DRAFT" in micro_text


def test_import_folder_adapts_and_promotes_custom_names(tmp_path: Path) -> None:
    project = _unified_project(tmp_path / "proj")
    external = tmp_path / "bundle"
    external.mkdir()
    (external / "HIVE_DEV_V1.md").write_text("# Dev\n\n- must validate cartridge import\n", encoding="utf-8")
    (external / "HIVE_PLANNING_V1.md").write_text("# Plan\n\n- architecture overview\n", encoding="utf-8")

    result = run_cartridge_import_folder(
        project,
        external,
        feature="example-feature",
        promote=True,
    )

    assert result["ok"] is True
    assert result["feature"] == "hive-dev-v1"
    assert result["adapt"]["adapted"]
    assert (project / "docs" / "delta" / "10_macro.md").is_file()
    assert (project / "docs" / "delta" / "20_micro" / "hive-dev-v1.md").is_file()
    assert result["promote"]["promotions"]["macro"] in {"written", "updated"}
    assert result["promote"]["promotions"]["micro"] in {"written", "updated"}


def test_manifest_layer_map_overrides_classification(tmp_path: Path) -> None:
    project = _unified_project(tmp_path / "proj")
    paths = RepoPaths(root=project)
    cart = paths.cartridge
    cart.mkdir(parents=True, exist_ok=True)
    (cart / "notes.md").write_text("# Notes\n\n- architecture diagram\n", encoding="utf-8")
    (cart / "manifest.json").write_text(
        '{"features":["custom-x"],"layer_map":{"notes.md":"holistic"}}\n',
        encoding="utf-8",
    )

    result = adapt_cartridge_for_promote(paths, "custom-x", source_rels=["notes.md"])

    assert result.mappings["notes.md"] == "holistic.md"
    assert (cart / "holistic.md").is_file()


def test_cartridge_load_needs_feature_import_promote_optional() -> None:
    assert cartridge_load_needs_feature("import", will_promote=True) is False
    assert cartridge_load_needs_feature("sources", will_promote=False) is True
