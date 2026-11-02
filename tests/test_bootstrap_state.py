from __future__ import annotations

from pathlib import Path

from hive_planner.launcher.bootstrap_state import summarize_bootstrap_state


def test_rosetta_only_folder_counts_as_existing_hive_files(tmp_path: Path) -> None:
    target = tmp_path / "notes"
    (target / "docs").mkdir(parents=True)
    (target / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")

    state = summarize_bootstrap_state(target)

    assert state.has_existing_hive_files is True
    assert state.allows_add_missing is True
    assert state.is_empty is False


def test_empty_folder_has_no_existing_hive_files(tmp_path: Path) -> None:
    target = tmp_path / "empty"
    target.mkdir()

    state = summarize_bootstrap_state(target)

    assert state.has_existing_hive_files is False
    assert state.allows_add_missing is False
