from __future__ import annotations

from pathlib import Path

from hive_planner.launcher.config import LauncherConfig
from hive_planner.launcher.user_guide import load_user_guide


def test_load_user_guide_reads_a_utf16_readme(tmp_path: Path) -> None:
    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    guide = scripts / "README.md"
    guide.write_text("# Legacy guide\n\nNo vendor section yet.\n", encoding="utf-16")
    cfg = LauncherConfig(hive_planner_root=str(hive))

    text = load_user_guide(cfg)

    assert text.startswith("# Legacy guide")
    assert "Hive Planner — quick help" not in text
    assert "## Unified vendor path" in text
    assert "mcp-serve" in text


def test_load_user_guide_strips_a_utf8_bom(tmp_path: Path) -> None:
    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    guide = scripts / "README.md"
    guide.write_text("\ufeff# Guide\n\n## Implementation loop\n\nAlready documented.\n", encoding="utf-8")
    cfg = LauncherConfig(hive_planner_root=str(hive))

    text = load_user_guide(cfg)

    assert text.startswith("# Guide")
    assert text.count("## Implementation loop") == 1
