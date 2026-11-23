"""Tests for the persistent dirty-override setting (.hive/implementation-loop/settings.json)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.implementation_loop import (
    CoordinatorError,
    _settings_path,
    coordinator_start,
    read_dirty_override,
    set_dirty_override,
)

# Reuse the coordinator test fixture and install helper (same pattern as the coordinator suite).
from test_implementation_loop_coordinator import _install_ready, loop_root  # noqa: F401


def test_default_is_block_when_no_settings_file(tmp_path: Path) -> None:
    assert not _settings_path(tmp_path).exists()
    assert read_dirty_override(tmp_path) == "block"


def test_allow_persists_and_reads_back(tmp_path: Path) -> None:
    assert set_dirty_override(tmp_path, "allow") == "allow"
    assert json.loads(_settings_path(tmp_path).read_text(encoding="utf-8")) == {"dirty_override": "allow"}
    assert read_dirty_override(tmp_path) == "allow"

    assert set_dirty_override(tmp_path, "block") == "block"
    assert read_dirty_override(tmp_path) == "block"


def test_invalid_mode_is_rejected_and_nothing_written(tmp_path: Path) -> None:
    with pytest.raises(CoordinatorError, match="block or allow"):
        set_dirty_override(tmp_path, "maybe")
    assert not _settings_path(tmp_path).exists()
    assert read_dirty_override(tmp_path) == "block"


@pytest.mark.parametrize("content", ["{not json", "[]", '"allow"', '{"dirty_override": "yes"}'])
def test_corrupt_or_unknown_settings_fail_closed_to_block(tmp_path: Path, content: str) -> None:
    path = _settings_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    assert read_dirty_override(tmp_path) == "block"


def test_settings_cli_sets_and_reads(loop_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from hive_planner.cli import main

    _install_ready(loop_root)
    code = main(
        ["--root", str(loop_root), "implementation-loop", "settings", "--dirty-override", "allow"]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["dirty_override"] == "allow"

    code = main(["--root", str(loop_root), "implementation-loop", "settings"])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["dirty_override"] == "allow"


def test_start_blocks_low_confidence_dirt_by_default(loop_root: Path) -> None:
    _install_ready(loop_root)
    (loop_root / ".env").write_text("TOKEN=redacted\n", encoding="utf-8")

    with pytest.raises(CoordinatorError, match="low-confidence dirty") as exc:
        coordinator_start(loop_root, "feature-x")

    assert exc.value.fields["dirty_confidence_tier"] == "low"
    assert ".env" in exc.value.fields["unrelated_dirty"]
    state = json.loads((loop_root / ".hive/implementation-loop/state.json").read_text(encoding="utf-8"))
    assert state["status"] != "running"


def test_start_proceeds_with_allow_setting_and_no_per_run_flag(loop_root: Path) -> None:
    _install_ready(loop_root)
    (loop_root / ".env").write_text("TOKEN=redacted\n", encoding="utf-8")
    set_dirty_override(loop_root, "allow")

    started = coordinator_start(loop_root, "feature-x")

    assert started.ok is True
    assert started.dirty_confidence_tier == "low"
    assert started.dirty_auto_start is False
    assert ".env" in started.unrelated_dirty
    assert ".env" in started.dirty
    state = json.loads((loop_root / ".hive/implementation-loop/state.json").read_text(encoding="utf-8"))
    assert state["status"] == "running"
    assert ".env" in state["baseline_dirty"]


def test_overlap_gate_still_blocks_with_allow_setting(loop_root: Path) -> None:
    from test_implementation_loop_coordinator import _ready_feature

    _install_ready(loop_root)
    (loop_root / "docs/specs/feature-x/plan.md").write_text(
        "# plan\n\n## File targets\n\n| File | Change |\n|------|--------|\n| `src/shared.py` | both |\n",
        encoding="utf-8",
    )
    set_dirty_override(loop_root, "allow")
    (loop_root / ".env").write_text("TOKEN=redacted\n", encoding="utf-8")
    coordinator_start(loop_root, "feature-x")
    before = (loop_root / ".hive/implementation-loop/state.json").read_text(encoding="utf-8")

    _ready_feature(
        loop_root,
        "feature-y",
        "# plan\n\n## File targets\n\n| File | Change |\n|------|--------|\n| src/shared.py | same |\n",
    )
    with pytest.raises(CoordinatorError, match="declared file overlap") as exc:
        coordinator_start(loop_root, "feature-y", force_feature=True)

    assert exc.value.fields.get("overlap") == ["src/shared.py"]
    assert (loop_root / ".hive/implementation-loop/state.json").read_text(encoding="utf-8") == before
