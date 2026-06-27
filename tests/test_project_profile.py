from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.project_profile import (
    infer_bootstrap_profile,
    read_project_profile,
    resolve_project_profile,
    write_project_profile,
)


def test_write_and_read_project_profile(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    write_project_profile(project, profile="full", project_name="Demo App", hive_planner_version="1.2.0")
    meta = read_project_profile(project)
    assert meta is not None
    assert meta.bootstrap_profile == "full"
    assert meta.project_name == "Demo App"
    assert meta.hive_planner_version == "1.2.0"
    payload = json.loads((project / ".hive" / "project.json").read_text(encoding="utf-8"))
    assert payload["bootstrap_profile"] == "full"


def test_infer_full_profile_from_pyproject(tmp_path: Path) -> None:
    project = tmp_path / "legacy-full"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert infer_bootstrap_profile(project) == "full"


def test_infer_minimal_without_pyproject(tmp_path: Path) -> None:
    project = tmp_path / "legacy-minimal"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    assert infer_bootstrap_profile(project) == "minimal"


def test_resolve_returns_none_for_non_hive_dir(tmp_path: Path) -> None:
    assert resolve_project_profile(tmp_path / "empty") is None


def test_write_rejects_unknown_profile(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown bootstrap profile"):
        write_project_profile(tmp_path, profile="enterprise", project_name="X")
