from __future__ import annotations

import json
from pathlib import Path

from hive_planner.launcher.config import load_config


def test_utf16_le_config_without_a_bom_is_not_replaced(tmp_path: Path, monkeypatch) -> None:
    kept = tmp_path / "kept"
    kept.mkdir()
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    payload = {
        "active_project": str(kept),
        "recent_projects": [str(kept)],
        "onboarding_complete": True,
    }
    path = cfg_dir / "config.json"
    path.write_bytes(json.dumps(payload).encode("utf-16-le"))

    loaded = load_config()

    assert loaded.active_project == str(kept.resolve())
    assert b"\x00" in path.read_bytes()
    assert "kept" in path.read_bytes().decode("utf-16-le")
