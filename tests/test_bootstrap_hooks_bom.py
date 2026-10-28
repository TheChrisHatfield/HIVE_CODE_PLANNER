"""A UTF-8 BOM on .cursor/hooks.json must not block the workspaceOpen merge."""

from __future__ import annotations

import json
from pathlib import Path

from hive_planner.bootstrap import _ensure_workspace_open_hooks_json


def test_bom_hooks_json_still_gains_workspace_open(tmp_path: Path) -> None:
    dest = tmp_path / ".cursor" / "hooks.json"
    dest.parent.mkdir(parents=True)
    original = {
        "version": 1,
        "hooks": {"sessionStart": [{"command": "echo keep-me"}]},
    }
    dest.write_bytes(b"\xef\xbb\xbf" + json.dumps(original).encode("utf-8"))
    written: list[str] = []
    warnings: list[str] = []

    _ensure_workspace_open_hooks_json(tmp_path, force=False, written=written, warnings=warnings)

    data = json.loads(dest.read_text(encoding="utf-8-sig"))
    assert warnings == []
    assert data["hooks"]["sessionStart"][0]["command"] == "echo keep-me"
    assert "hive_workspace_open.py" in json.dumps(data["hooks"]["workspaceOpen"])
    assert ".cursor/hooks.json" in written
