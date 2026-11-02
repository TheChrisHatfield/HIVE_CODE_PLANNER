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


def test_json_false_default_agent_handoff_loads_as_off(tmp_path: Path, monkeypatch) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setattr("hive_planner.launcher.config.default_config_dir", lambda: cfg_dir)
    (cfg_dir / "config.json").write_text(
        json.dumps({"default_agent_handoff": False, "onboarding_complete": True}),
        encoding="utf-8",
    )

    loaded = load_config()

    assert loaded.default_agent_handoff == "off"
