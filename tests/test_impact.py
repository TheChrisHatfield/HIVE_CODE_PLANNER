from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.impact import ImpactError, build_impact_packet, impact_warnings, load_latest_impact_packet, write_impact_packet
from hive_planner.pipeline import ingest


def _setup_feature_spec(paths: RepoPaths, feature: str) -> None:
    spec_dir = paths.root / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")


def _setup_test_map(paths: RepoPaths) -> None:
    ci = paths.root / "docs" / "change-impact"
    ci.mkdir(parents=True, exist_ok=True)
    (ci / "test-map.md").write_text(
        "| Source module | Tests |\n|---------------|-------|\n"
        "| `src/hive_planner/emitter.py` | `tests/test_formats.py` |\n",
        encoding="utf-8",
    )


def test_unknown_feature_errors_without_packet(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    with pytest.raises(ImpactError, match="Unknown feature"):
        build_impact_packet(paths, "missing-feature", [tmp_path / "x.py"])


def test_impact_lists_tests_for_src_target(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "cartridge-compiler-v2")
    _setup_test_map(paths)
    src = paths.root / "src" / "hive_planner" / "emitter.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# stub\n", encoding="utf-8")

    packet = build_impact_packet(paths, "cartridge-compiler-v2", [src])
    secondary_paths = [t.path for t in packet.secondary]
    assert "tests/test_formats.py" in secondary_paths


def test_delta_edit_flagged_tertiary(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "change-impact-v1")
    delta = paths.root / "docs" / "delta" / "10_macro.md"
    delta.parent.mkdir(parents=True, exist_ok=True)
    delta.write_text("# macro\n", encoding="utf-8")

    packet = build_impact_packet(paths, "change-impact-v1", [delta])
    assert packet.tertiary
    assert packet.tertiary[0].path.startswith("docs/delta/")


def test_invalid_packet_load_warns_not_blocks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    paths = RepoPaths(root=tmp_path)
    packet_dir = paths.root / "docs" / "change-impact" / "impact-packets"
    packet_dir.mkdir(parents=True)
    (packet_dir / "chg_bad.json").write_text("{not json", encoding="utf-8")

    warnings = impact_warnings(paths)
    assert any("Invalid impact packet" in w for w in warnings)

    report = ingest(paths)
    assert report.processed == 0 or isinstance(report.processed, int)


def test_load_latest_skips_corrupt_and_loads_valid(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    packet_dir = paths.root / "docs" / "change-impact" / "impact-packets"
    packet_dir.mkdir(parents=True)
    bad = packet_dir / "chg_bad.json"
    good = packet_dir / "chg_20260101_000000_feature.json"
    bad.write_text("{not json", encoding="utf-8")
    good.write_text(
        json.dumps(
            {
                "packet_id": "chg_20260101_000000_feature",
                "feature": "cartridge-compiler-v2",
                "hook_ids": ["change.impact"],
                "primary": [],
                "secondary": [],
                "tertiary": [],
            }
        ),
        encoding="utf-8",
    )
    good.touch()
    import os
    import time

    time.sleep(0.01)
    os.utime(bad, (time.time(), time.time() + 10))

    loaded, err = load_latest_impact_packet(paths, "cartridge-compiler-v2")
    assert err is None
    assert loaded is not None
    assert loaded.feature == "cartridge-compiler-v2"


def test_impact_dedupes_mapped_tests(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "cartridge-compiler-v2")
    ci = paths.root / "docs" / "change-impact"
    ci.mkdir(parents=True, exist_ok=True)
    (ci / "test-map.md").write_text(
        "| Source module | Tests |\n|---------------|-------|\n"
        "| `src/hive_planner/emitter.py` | `tests/test_formats.py` |\n"
        "| `src/hive_planner/normalizer.py` | `tests/test_formats.py` |\n",
        encoding="utf-8",
    )
    src1 = paths.root / "src" / "hive_planner" / "emitter.py"
    src2 = paths.root / "src" / "hive_planner" / "normalizer.py"
    src1.parent.mkdir(parents=True, exist_ok=True)
    src1.write_text("a\n", encoding="utf-8")
    src2.write_text("b\n", encoding="utf-8")

    packet = build_impact_packet(paths, "cartridge-compiler-v2", [src1, src2])
    secondary_paths = [t.path for t in packet.secondary]
    assert secondary_paths.count("tests/test_formats.py") == 1


def test_impact_dedupes_duplicate_file_args(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "cartridge-compiler-v2")
    src = paths.root / "src" / "hive_planner" / "emitter.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("x = 1\n", encoding="utf-8")

    packet = build_impact_packet(paths, "cartridge-compiler-v2", [src, src])
    assert len(packet.primary) == 1


def test_test_map_prefix_does_not_false_match_sibling_module(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "cartridge-compiler-v2")
    ci = paths.root / "docs" / "change-impact"
    ci.mkdir(parents=True, exist_ok=True)
    (ci / "test-map.md").write_text(
        "| Source module | Tests |\n|---------------|-------|\n"
        "| `src/hive_planner/normalizer.py` | `tests/test_compiler.py` |\n",
        encoding="utf-8",
    )
    src = paths.root / "src" / "hive_planner" / "normalizers" / "html.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# html\n", encoding="utf-8")

    packet = build_impact_packet(paths, "cartridge-compiler-v2", [src])
    secondary_paths = [t.path for t in packet.secondary]
    assert "tests/test_compiler.py" not in secondary_paths


def test_translator_hooks_for_feature(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "cartridge-translator-v1")
    src = paths.root / "src" / "hive_planner" / "translator.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# translator\n", encoding="utf-8")

    packet = build_impact_packet(paths, "cartridge-translator-v1", [src])
    assert "context.cartridge" in packet.hook_ids
    assert "context.cartridge_schema" in packet.hook_ids


def test_embedding_hooks_for_feature(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "embedding-retrieval-v1")
    src = paths.root / "src" / "hive_planner" / "embeddings.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# embeddings\n", encoding="utf-8")

    packet = build_impact_packet(paths, "embedding-retrieval-v1", [src])
    assert "compiler.pipeline" in packet.hook_ids
    assert "context.library" in packet.hook_ids


def test_delta_emit_hooks_for_feature(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "cartridge-delta-emit-v1")
    src = paths.root / "src" / "hive_planner" / "delta_emit.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# delta emit\n", encoding="utf-8")

    packet = build_impact_packet(paths, "cartridge-delta-emit-v1", [src])
    assert "context.cartridge" in packet.hook_ids
    assert "context.delta" in packet.hook_ids


def test_map_sync_hooks_for_feature(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "change-impact-v2")
    src = paths.root / "src" / "hive_planner" / "map_sync.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# map sync\n", encoding="utf-8")

    packet = build_impact_packet(paths, "change-impact-v2", [src])
    assert "change.impact" in packet.hook_ids
    assert "next.files" in packet.hook_ids


def test_git_handoff_hooks_for_feature(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "git-handoff-ci-v1")
    src = paths.root / "src" / "hive_planner" / "ci_handoff.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# ci handoff\n", encoding="utf-8")

    packet = build_impact_packet(paths, "git-handoff-ci-v1", [src])
    assert "workflow.git_handoff" in packet.hook_ids
    assert "automation.ci_memory" in packet.hook_ids


def test_roadmap_complete_hooks_for_feature(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "roadmap-complete-v1")
    src = paths.root / "src" / "hive_planner" / "roadmap_status.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# roadmap\n", encoding="utf-8")

    packet = build_impact_packet(paths, "roadmap-complete-v1", [src])
    assert "workflow.tools" in packet.hook_ids


def test_impact_cli_writes_packet(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    _setup_feature_spec(paths, "cartridge-compiler-v2")
    _setup_test_map(paths)
    src = paths.root / "src" / "hive_planner" / "emitter.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("x = 1\n", encoding="utf-8")

    packet = build_impact_packet(paths, "cartridge-compiler-v2", [src])
    out = write_impact_packet(paths, packet)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["feature"] == "cartridge-compiler-v2"
    assert "change.impact" in data["hook_ids"]

    loaded, err = load_latest_impact_packet(paths, "cartridge-compiler-v2")
    assert err is None
    assert loaded is not None
    assert loaded.feature == "cartridge-compiler-v2"
