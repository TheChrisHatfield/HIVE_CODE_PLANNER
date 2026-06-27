from __future__ import annotations

from pathlib import Path

from hive_planner.config import RepoPaths
from hive_planner.roadmap_status import ROADMAP_FEATURES, validate_roadmap


def test_validate_roadmap_missing_features(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    report = validate_roadmap(paths)
    assert not report.ok
    assert len(report.missing) == len(ROADMAP_FEATURES)


def test_validate_roadmap_complete(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    for feature in ROADMAP_FEATURES:
        spec_dir = paths.root / "docs" / "specs" / feature
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
        (spec_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        micro_dir = paths.root / "docs" / "delta" / "20_micro"
        micro_dir.mkdir(parents=True, exist_ok=True)
        (micro_dir / f"{feature}.md").write_text("# Micro\n", encoding="utf-8")

    report = validate_roadmap(paths)
    assert report.ok
    assert not report.missing
