from __future__ import annotations

import json
from pathlib import Path

from hive_planner.launcher.service import (
    _loads_workspace_json,
    cl_runtime_status_label,
    read_code_workspace_folders,
    run_cartridge_import_folder,
    run_cartridge_load_sources,
    run_cartridge_translate,
    run_deploy_agent_handoff,
    run_set_cl_runtime,
    run_source4s_upload,
    workspace_primary_folder,
)


def _dead_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "missing"}]}), encoding="utf-8")
    return workspace


def test_bom_workspace_file_uses_its_folder_not_the_parent(tmp_path: Path) -> None:
    parent = tmp_path / "links"
    parent.mkdir()
    project = tmp_path / "app"
    project.mkdir()
    (project / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    workspace = parent / "hive.code-workspace"
    payload = json.dumps({"folders": [{"path": str(project)}]})
    workspace.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))
    assert read_code_workspace_folders(workspace) == [project.resolve()]
    assert workspace_primary_folder(workspace) == project.resolve()


def test_jsonc_workspace_file_uses_its_folder_not_the_parent(tmp_path: Path) -> None:
    parent = tmp_path / "links"
    parent.mkdir()
    project = tmp_path / "app"
    project.mkdir()
    workspace = parent / "hive.code-workspace"
    workspace.write_text(
        "{\n"
        "  // linked project\n"
        "  \"folders\": [\n"
        f"    {{ \"path\": {json.dumps(str(project))}, }},\n"
        "  ],\n"
        "}\n",
        encoding="utf-8",
    )
    assert read_code_workspace_folders(workspace) == [project.resolve()]
    assert workspace_primary_folder(workspace) == project.resolve()
    kept = _loads_workspace_json(
        '{ /* note */ "folders": [ { "path": "keep // still", } ] }'
    )
    assert kept["folders"][0]["path"] == "keep // still"


def test_utf16_workspace_file_lists_its_folder(tmp_path: Path) -> None:
    project = tmp_path / "app"
    project.mkdir()
    workspace = tmp_path / "hive.code-workspace"
    payload = json.dumps({"folders": [{"path": str(project)}]})
    workspace.write_text(payload, encoding="utf-16")
    assert read_code_workspace_folders(workspace) == [project.resolve()]


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
