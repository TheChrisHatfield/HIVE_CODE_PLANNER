from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.project_profile import (
    infer_bootstrap_profile,
    infer_spec_kit_enabled,
    read_project_profile,
    resolve_project_integrations,
    resolve_project_profile,
    write_project_profile,
)


def test_write_and_read_project_profile(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    write_project_profile(
        project,
        profile="full",
        project_name="Demo App",
        hive_planner_version="1.2.0",
        agent_handoff_mode="unified",
    )
    meta = read_project_profile(project)
    assert meta is not None
    assert meta.bootstrap_profile == "full"
    assert meta.project_name == "Demo App"
    assert meta.hive_planner_version == "1.2.0"
    assert meta.agent_handoff_mode == "unified"
    assert meta.spec_kit_enabled is True
    assert meta.continual_learning_enabled is True
    payload = json.loads((project / ".hive" / "project.json").read_text(encoding="utf-8"))
    assert payload["bootstrap_profile"] == "full"


def test_write_project_profile_preserves_created_at_on_update(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    write_project_profile(project, profile="minimal", project_name="Demo", agent_handoff_mode="off")
    created_at = json.loads((project / ".hive" / "project.json").read_text(encoding="utf-8"))["created_at"]
    write_project_profile(project, profile="minimal", project_name="Demo", agent_handoff_mode="unified")
    payload = json.loads((project / ".hive" / "project.json").read_text(encoding="utf-8"))
    assert payload["created_at"] == created_at
    assert payload["agent_handoff_mode"] == "unified"


def test_resolve_project_integrations_defaults_without_specs(tmp_path: Path) -> None:
    project = tmp_path / "plain"
    project.mkdir()
    write_project_profile(project, profile="minimal", project_name="plain", agent_handoff_mode="off")
    integrations = resolve_project_integrations(project)
    assert integrations.spec_kit_enabled is False
    assert integrations.continual_learning_enabled is False
    assert integrations.agent_handoff_mode == "off"


def test_infer_spec_kit_enabled_from_specs_dir(tmp_path: Path) -> None:
    project = tmp_path / "legacy"
    spec_dir = project / "docs" / "specs" / "my-feature"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    assert infer_spec_kit_enabled(project) is True
    assert resolve_project_integrations(project).spec_kit_enabled is True


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


def test_read_tolerates_invalid_schema_version(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    meta = project / ".hive"
    meta.mkdir(parents=True)
    (meta / "project.json").write_text(
        '{"bootstrap_profile":"minimal","project_name":"Demo","schema_version":"bad"}\n',
        encoding="utf-8",
    )
    profile = read_project_profile(project)
    assert profile is not None
    assert profile.bootstrap_profile == "minimal"
    assert profile.schema_version == 3


def test_write_rejects_unknown_profile(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown bootstrap profile"):
        write_project_profile(tmp_path, profile="enterprise", project_name="X")
