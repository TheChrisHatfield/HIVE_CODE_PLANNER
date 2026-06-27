from __future__ import annotations

from pathlib import Path

from hive_planner.config import RepoPaths
from hive_planner.rosetta_nav import (
    ensure_handoff_rosetta_navigation,
    has_rosetta_navigation,
    inject_agents_rosetta_section,
    spec_navigation_block,
)
from hive_planner.spec_drift import repair_agents_rosetta_section


def test_spec_navigation_block_includes_hook_map() -> None:
    block = spec_navigation_block("hive-dev-v1")
    assert "planning.rosetta" in block
    assert "context.delta" in block
    assert "spec.flow" in block
    assert "hive-dev-v1.md" in block


def test_ensure_handoff_rosetta_navigation_patches_existing_spec(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    feature = "hive-dev-v1"
    spec_dir = root / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True)
    spec_path = spec_dir / "spec.md"
    spec_path.write_text(
        "\n".join(
            [
                "# Spec: hive-dev-v1",
                "",
                "**Hook:** `spec.flow`",
                "",
                "## Requirements",
                "",
                "- GPU memory limit applies",
                "",
            ]
        ),
        encoding="utf-8",
    )

    patched = ensure_handoff_rosetta_navigation(RepoPaths(root=root), feature)

    text = spec_path.read_text(encoding="utf-8")
    assert has_rosetta_navigation(text)
    assert "planning.rosetta" in text
    assert spec_path.relative_to(root).as_posix() in patched


def test_repair_agents_rosetta_section_inserts_anchor(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    agents = root / "AGENTS.md"
    agents.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## Repository root",
                "",
                "`/tmp/proj`",
                "",
                "## Active feature",
                "",
                "**hive-dev-v1**",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = repair_agents_rosetta_section(RepoPaths(root=root))

    assert result.repaired is True
    updated = agents.read_text(encoding="utf-8")
    assert "Planning Rosetta Stone" in updated
    assert "planning.rosetta" in updated


def test_inject_agents_rosetta_section_idempotent() -> None:
    base = inject_agents_rosetta_section("# AGENTS\n\n## Active feature\n")
    again = inject_agents_rosetta_section(base)
    assert base == again
