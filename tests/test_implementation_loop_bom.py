"""UTF-8 BOM on loop files must not hide the first task or reject state.json."""

from __future__ import annotations

import json
from pathlib import Path

from hive_planner.implementation_loop import (
    _first_open_task,
    _has_open_task,
    _load_state,
    _read_feature_tasks,
    read_installed_pack,
)


def _write_bom(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))


def test_bom_tasks_file_keeps_the_first_heading_and_task(tmp_path: Path) -> None:
    feature = "feat"
    tasks = tmp_path / "docs" / "specs" / feature / "tasks.md"
    _write_bom(
        tasks,
        "## Phase\n\n- [ ] T001 first\n\n## Next\n\n- [ ] T002 later\n",
    )

    task_id, heading, _body = _first_open_task(_read_feature_tasks(tmp_path, feature, "start"))

    assert task_id == "T001"
    assert heading == "Phase"
    assert _has_open_task(tasks)


def test_bom_tasks_file_does_not_skip_a_leading_checkbox(tmp_path: Path) -> None:
    feature = "feat"
    tasks = tmp_path / "docs" / "specs" / feature / "tasks.md"
    _write_bom(tasks, "- [ ] T001 first\n- [ ] T002 second\n")

    task_id, _heading, _body = _first_open_task(_read_feature_tasks(tmp_path, feature, "start"))

    assert task_id == "T001"


def test_bom_state_json_loads_the_installed_pack(tmp_path: Path) -> None:
    _write_bom(
        tmp_path / ".hive" / "implementation-loop" / "state.json",
        json.dumps({"pack": "4-pack", "feature": "feat", "status": "running"}),
    )

    assert read_installed_pack(tmp_path) == "4-pack"
    assert _load_state(tmp_path).pack == "4-pack"


def test_utf16_tasks_file_is_not_treated_as_finished(tmp_path: Path) -> None:
    feature = "feat"
    tasks = tmp_path / "docs" / "specs" / feature / "tasks.md"
    tasks.parent.mkdir(parents=True)
    tasks.write_text("## Phase\n\n- [ ] T001 first\n", encoding="utf-16")

    task_id, heading, _body = _first_open_task(_read_feature_tasks(tmp_path, feature, "start"))

    assert task_id == "T001"
    assert heading == "Phase"
    assert _has_open_task(tasks)


def test_utf16_state_json_loads_the_installed_pack(tmp_path: Path) -> None:
    path = tmp_path / ".hive" / "implementation-loop" / "state.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"pack": "4-pack", "feature": "feat", "status": "running"}),
        encoding="utf-16",
    )

    assert read_installed_pack(tmp_path) == "4-pack"
    assert _load_state(tmp_path).pack == "4-pack"
