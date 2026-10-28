from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.launcher.service import run_project_map_sync


def _minimal_hive_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")
    RepoPaths(root=root).ensure_dirs()
    return root


def test_run_project_map_sync_uses_workspace_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = _minimal_hive_project(tmp_path / "app")
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "app"}]}), encoding="utf-8")
    seen: list[Path] = []

    def _fake_sync(paths, *, dry_run: bool = False):
        seen.append(paths.root)
        return type(
            "R",
            (),
            {
                "project_added": set(),
                "test_added": set(),
                "project_updated": set(),
                "test_updated": set(),
            },
        )()

    monkeypatch.setattr("hive_planner.launcher.service.sync_impact_maps", _fake_sync)
    result = run_project_map_sync(workspace)
    assert result["ok"] is True
    assert seen == [folder.resolve()]


def test_run_project_map_sync_rejects_workspace_file_as_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "missing"}]}), encoding="utf-8")
    result = run_project_map_sync(workspace)
    assert result["ok"] is False
    assert "folder" in str(result.get("error") or "").lower()
