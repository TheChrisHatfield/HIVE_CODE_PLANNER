from __future__ import annotations

import json
from pathlib import Path

from hive_planner.launcher.service import (
    cl_runtime_status_label,
    run_cartridge_import_folder,
    run_cartridge_load_sources,
    run_cartridge_translate,
    run_deploy_agent_handoff,
    run_set_cl_runtime,
    run_source4s_upload,
)


def _dead_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "missing"}]}), encoding="utf-8")
    return workspace


def test_home_project_actions_resolve_workspace_folder(tmp_path: Path) -> None:
    workspace = _dead_workspace(tmp_path)
    hive_root = tmp_path / "hive"
    hive_root.mkdir()
    results = [
        run_deploy_agent_handoff(workspace, hive_planner_root=hive_root),
        run_cartridge_load_sources(workspace, [tmp_path / "a.txt"], "feat"),
        run_cartridge_translate(workspace, tmp_path / "a.md", "feat"),
        run_cartridge_import_folder(workspace, tmp_path / "cart"),
        run_source4s_upload(workspace, [tmp_path / "a.txt"], "feat"),
        run_set_cl_runtime(workspace, "cursor"),
    ]
    for result in results:
        assert result["ok"] is False
        assert "folder" in str(result.get("error") or "").lower()
    assert cl_runtime_status_label(workspace) == "\u2014"
