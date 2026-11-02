from __future__ import annotations

from pathlib import Path

from hive_planner.bug_hunt import install_bug_hunt


def test_install_keeps_a_utf16_le_repo_overlay_without_a_bom(tmp_path: Path) -> None:
    overlay = tmp_path / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_bytes(
        "## This repo\n\nRun coco_bug_hunt_audit.py after each fix.\n".encode("utf-16-le")
    )
    before = overlay.read_bytes()

    install_bug_hunt(tmp_path, iterations=8)

    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "coco_bug_hunt_audit.py" in command
    assert "\x00" not in command
    assert overlay.read_bytes() == before
