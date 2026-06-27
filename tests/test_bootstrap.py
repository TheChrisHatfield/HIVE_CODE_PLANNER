from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hive_planner.bootstrap import BootstrapError, init_project
from hive_planner.config import RepoPaths, is_repo_root


def _hive_source(tmp_path: Path) -> RepoPaths:
    root = tmp_path / "hive-planner"
    kit = root / "starter-kit"
    rules = root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# Architecture\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# Task Execution\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# Validation\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")
    return RepoPaths(root=root)


def test_init_creates_detectable_repo_root(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "new-project"

    result = init_project(source, target, name="Demo Project")

    assert is_repo_root(target)
    assert (target / "START_HERE.md").exists()
    assert (target / "docs" / "planning-rosetta-stone.md").exists()
    assert (target / "AGENTS.md").read_text(encoding="utf-8").find("Demo Project") != -1
    assert (target / ".cursor" / "rules" / "architecture.mdc").exists()
    assert result.project_name == "Demo Project"
    assert "START_HERE.md" in result.files_written


def test_init_rejects_non_empty_target(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "occupied"
    target.mkdir()
    (target / "existing.txt").write_text("x", encoding="utf-8")

    with pytest.raises(BootstrapError, match="not empty"):
        init_project(source, target)


def test_init_rejects_already_initialized(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "already"
    init_project(source, target)

    with pytest.raises(BootstrapError, match="already initialized"):
        init_project(source, target)


def test_init_rejects_file_target(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "not-a-dir"
    target.write_text("x", encoding="utf-8")

    with pytest.raises(BootstrapError, match="must be a directory"):
        init_project(source, target)


def test_init_rejects_hive_source_root(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)

    with pytest.raises(BootstrapError, match="cannot be the Hive source"):
        init_project(source, source.root, force=True)


def test_init_rejects_subdirectory_of_hive_source(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    nested = source.root / "scratch" / "nested"
    nested.mkdir(parents=True)

    with pytest.raises(BootstrapError, match="inside the Hive source"):
        init_project(source, nested, force=True)


def test_init_wraps_write_failures_as_bootstrap_error(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "blocked"
    target.mkdir()
    (target / "docs").write_text("not a directory", encoding="utf-8")

    with pytest.raises(BootstrapError, match="Failed to write bootstrap files"):
        init_project(source, target, force=True)


def test_init_force_rewrites_scaffold(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "forced"
    init_project(source, target, name="First")
    init_project(source, target, name="Second", force=True)
    assert "Second" in (target / "AGENTS.md").read_text(encoding="utf-8")


def test_init_minimal_profile_skips_pyproject(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "minimal-app"

    result = init_project(source, target, profile="minimal")

    assert result.profile == "minimal"
    assert not (target / "pyproject.toml").exists()
    assert not (target / ".github" / "workflows" / "ci.yml").exists()


def test_init_full_profile_writes_dev_scaffold(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "my_app"

    result = init_project(source, target, name="My App", profile="full")

    assert result.profile == "full"
    assert (target / "pyproject.toml").exists()
    assert (target / ".gitignore").exists()
    assert (target / "src" / "my_app" / "__init__.py").exists()
    assert (target / "tests" / "test_placeholder.py").exists()
    assert (target / ".github" / "workflows" / "ci.yml").exists()
    assert "my_app" in (target / "pyproject.toml").read_text(encoding="utf-8")
    assert "pyproject.toml" in result.files_written


def test_init_full_profile_generates_valid_python_and_toml(tmp_path: Path) -> None:
    import tomllib

    source = _hive_source(tmp_path)
    target = tmp_path / "valid_app"
    init_project(source, target, name="Valid App", profile="full")

    init_src = (target / "src" / "valid_app" / "__init__.py").read_text(encoding="utf-8")
    test_src = (target / "tests" / "test_placeholder.py").read_text(encoding="utf-8")
    compile(init_src, "init", "exec")
    compile(test_src, "test", "exec")
    tomllib.loads((target / "pyproject.toml").read_text(encoding="utf-8"))


def test_init_unknown_profile_errors(tmp_path: Path) -> None:
    source = _hive_source(tmp_path)
    target = tmp_path / "bad-profile"

    with pytest.raises(BootstrapError, match="Unknown bootstrap profile"):
        init_project(source, target, profile="enterprise")


def test_init_git_init_creates_repo(tmp_path: Path) -> None:
    import shutil

    if shutil.which("git") is None:
        pytest.skip("git not on PATH")

    source = _hive_source(tmp_path)
    target = tmp_path / "git-app"
    result = init_project(source, target, profile="full", git_init=True)

    assert result.git_initialized is True
    assert (target / ".git").exists()


def test_init_git_init_skips_existing_repo(tmp_path: Path) -> None:
    import shutil

    if shutil.which("git") is None:
        pytest.skip("git not on PATH")

    source = _hive_source(tmp_path)
    target = tmp_path / "existing-git"
    target.mkdir()
    subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)

    result = init_project(source, target, profile="full", git_init=True, force=True)

    assert result.git_initialized is False
    assert any("already exists" in w for w in result.warnings)
