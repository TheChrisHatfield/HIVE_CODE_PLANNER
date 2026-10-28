"""CLI --root accepts a Cursor .code-workspace file."""

from __future__ import annotations

import json
from pathlib import Path

from hive_planner.cli import main


def test_status_uses_the_folder_inside_a_code_workspace(tmp_path: Path, capsys) -> None:
    project = tmp_path / "app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    workspace = tmp_path / "links" / "app.code-workspace"
    workspace.parent.mkdir()
    workspace.write_text(
        json.dumps({"folders": [{"path": str(project)}]}),
        encoding="utf-8",
    )

    assert main(["--root", str(workspace), "status"]) == 0
    assert f"Root: {project.resolve()}" in capsys.readouterr().out


def test_status_rejects_a_missing_code_workspace_file(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing.code-workspace"
    assert main(["--root", str(missing), "status"]) == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_status_keeps_a_directory_named_like_a_workspace(tmp_path: Path, capsys) -> None:
    project = tmp_path / "app.code-workspace"
    project.mkdir()
    assert main(["--root", str(project), "status"]) == 0
    assert f"Root: {project.resolve()}" in capsys.readouterr().out


def test_status_keeps_a_directory_root(tmp_path: Path, capsys) -> None:
    project = tmp_path / "app"
    project.mkdir()
    assert main(["--root", str(project), "status"]) == 0
    assert f"Root: {project.resolve()}" in capsys.readouterr().out
