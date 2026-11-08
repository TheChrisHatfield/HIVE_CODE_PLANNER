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


def test_stale_readme_codespec_help_includes_check_pack(tmp_path: Path) -> None:
    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "README.md").write_text("# Guide\n\nNo loop section.\n", encoding="utf-8")
    cfg = LauncherConfig(hive_planner_root=str(hive))

    text = load_user_guide(cfg)

    assert "**Check pack**" in text
    assert "**Handoff**" in text
    assert text.count("## Implementation loop") == 1


def test_fenced_implementation_loop_heading_still_gets_codespec_help(tmp_path: Path) -> None:
    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "README.md").write_text(
        "# Guide\n\n```\n## Implementation loop\n```\n\nNo real section.\n",
        encoding="utf-8",
    )
    cfg = LauncherConfig(hive_planner_root=str(hive))

    text = load_user_guide(cfg)

    assert "**Check pack**" in text
    assert "**Handoff**" in text


def test_indented_fence_line_does_not_hide_the_codespec_section(tmp_path: Path) -> None:
    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "README.md").write_text(
        "# Guide\n\n```\nexample\n    ```\nstill\n```\n\n## Implementation loop\n\nAlready documented.\n",
        encoding="utf-8",
    )
    cfg = LauncherConfig(hive_planner_root=str(hive))

    text = load_user_guide(cfg)

    assert text.count("## Implementation loop") == 1
    assert "Already documented." in text


def test_load_user_guide_uses_builtin_help_when_the_readme_is_not_utf8(tmp_path: Path) -> None:
    hive = tmp_path / "hive"
    scripts = hive / "scripts"
    scripts.mkdir(parents=True)
    guide = scripts / "README.md"
    raw = bytearray(b"Cafe guide line\n")
    raw[1] = 0xE9
    guide.write_bytes(bytes(raw))
    cfg = LauncherConfig(hive_planner_root=str(hive))

    text = load_user_guide(cfg)

    assert text.startswith("Hive Planner — quick help")
    assert "Home → CodeSpec" in text


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
