from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.translator import (
    DRAFT_BANNER,
    TranslatorError,
    classify_segment,
    compress_segment,
    segment_text,
    translate_document,
    write_translator_status,
)


def test_segment_text_splits_headings_and_paragraphs() -> None:
    text = "# Title\n\nFirst paragraph.\n\n## Section\n\nSecond paragraph."
    segments = segment_text(text)
    assert len(segments) >= 2
    assert any("First paragraph" in s for s in segments)
    assert any("Second paragraph" in s for s in segments)


def test_segment_text_ignores_headings_in_code_fences() -> None:
    text = "# Real\n\n```markdown\n# not a heading\nbody\n```\n\nDone."
    segments = segment_text(text)
    joined = "\n".join(segments)
    assert "Real" in joined
    assert "Done" in joined
    assert not any(seg.startswith("not a heading") for seg in segments)


def test_classify_holistic_segment() -> None:
    assert classify_segment("Our mission is to reduce coding drift.") == "holistic"


def test_classify_macro_segment() -> None:
    assert classify_segment("Architecture\n\nThe compiler pipeline has four subsystems.") == "macro"


def test_classify_micro_segment() -> None:
    assert classify_segment("Acceptance criteria for this feature include tests.") == "micro"


def test_classify_memory_segment() -> None:
    assert classify_segment("Durable guardrail: never promote transient chat to AGENTS.md.") == "memory"


def test_classify_reject_noise_segment() -> None:
    assert classify_segment("Hello world random chatter.") == "reject"
    assert classify_segment("The latest update was deployed.") == "reject"


def test_classify_rejects_markdown_table_rows() -> None:
    table = "Scope\n\n| In scope | Out of scope |\n| --- | --- |\n| HTML | Embeddings |"
    assert classify_segment(table) == "reject"


def test_compress_segment_truncates_and_bullets() -> None:
    long_text = "word " * 100
    compressed = compress_segment(long_text)
    assert compressed.startswith("- ")
    assert len(compressed) <= 243


def test_translate_writes_only_under_cartridge(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (repo / "docs" / "planning-rosetta-stone.md").parent.mkdir(parents=True)
    (repo / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")

    input_md = repo / "research.md"
    input_md.write_text(
        "\n".join(
            [
                "# Research",
                "",
                "Mission: keep agents aligned with structured context.",
                "",
                "Architecture: compiler pipeline ingests sources.",
                "",
                "Feature task: add translate CLI with acceptance tests.",
                "",
                "Durable rule: always run pytest before merge.",
                "",
                "Random noise with no keywords.",
            ]
        ),
        encoding="utf-8",
    )

    paths = RepoPaths(root=repo)
    result = translate_document(paths, input_md, "cartridge-translator-v1")
    status_path = write_translator_status(paths, result)

    assert result.status == "ok"
    assert result.rejections >= 1
    assert (paths.cartridge / "holistic.md").exists()
    assert (paths.cartridge / "macro.md").exists()
    assert (paths.cartridge / "micro" / "cartridge-translator-v1.md").exists()
    assert (paths.cartridge / "memory.md").exists()
    assert status_path.exists()

    holistic = (paths.cartridge / "holistic.md").read_text(encoding="utf-8")
    assert DRAFT_BANNER in holistic
    assert "Mission" in holistic

    for path in paths.cartridge.rglob("*"):
        if path.is_file():
            assert paths.cartridge.resolve() in path.resolve().parents or path.resolve() == paths.cartridge.resolve()

    assert not (repo / "docs" / "delta").exists() or not any((repo / "docs" / "delta").rglob("*.md"))


def test_reject_segments_excluded_from_output(tmp_path: Path) -> None:
    repo = tmp_path / "repo2"
    repo.mkdir()
    (repo / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (repo / "docs" / "planning-rosetta-stone.md").parent.mkdir(parents=True)
    (repo / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")

    input_md = repo / "noise.md"
    input_md.write_text("Hello world.\n\nMore random text.\n", encoding="utf-8")
    paths = RepoPaths(root=repo)
    result = translate_document(paths, input_md, "x")
    holistic = (paths.cartridge / "holistic.md").read_text(encoding="utf-8")
    assert "Hello world" not in holistic
    assert result.rejections >= 1


def test_unknown_input_errors(tmp_path: Path) -> None:
    repo = tmp_path / "repo3"
    repo.mkdir()
    paths = RepoPaths(root=repo)
    with pytest.raises(TranslatorError, match="not found"):
        translate_document(paths, Path("missing.md"), "feature")


def test_translate_cli_integration(tmp_path: Path) -> None:
    repo = tmp_path / "repo4"
    repo.mkdir()
    (repo / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (repo / "docs" / "planning-rosetta-stone.md").parent.mkdir(parents=True)
    (repo / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")

    micro = repo / "docs" / "delta" / "20_micro" / "cartridge-compiler-v3.md"
    micro.parent.mkdir(parents=True)
    micro.write_text(
        "# Feature\n\nMission: test alignment.\n\nAcceptance criteria: tests pass.\n",
        encoding="utf-8",
    )

    paths = RepoPaths(root=repo)
    result = translate_document(paths, micro, "cartridge-translator-v1")
    assert result.promotions.get("spec_seed_created") is True
    assert (paths.cartridge / "specs" / "cartridge-translator-v1.specseed.md").exists()

def test_translate_skips_manual_cartridge_without_force(tmp_path: Path) -> None:
    from hive_planner.delta_emit import MANUAL_MARKER

    repo = tmp_path / "repo-manual"
    repo.mkdir()
    (repo / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    (repo / "docs" / "planning-rosetta-stone.md").parent.mkdir(parents=True)
    (repo / "docs" / "planning-rosetta-stone.md").write_text("# rosetta\n", encoding="utf-8")

    cartridge = repo / "cartridge"
    cartridge.mkdir()
    holistic = cartridge / "holistic.md"
    original = f"{MANUAL_MARKER} keep -->\n\n# Curated holistic\n"
    holistic.write_text(original, encoding="utf-8")

    input_md = repo / "notes.md"
    input_md.write_text(
        "Mission: ship translation.\n\nSubsystem workflow for planner modules.\n",
        encoding="utf-8",
    )
    paths = RepoPaths(root=repo)
    result = translate_document(paths, input_md, "manual-feature")

    assert "holistic.md" in result.files_skipped
    assert "holistic.md" not in result.files_written
    assert holistic.read_text(encoding="utf-8") == original

    forced = translate_document(paths, input_md, "manual-feature", force=True)
    assert "holistic.md" in forced.files_written
    assert DRAFT_BANNER in holistic.read_text(encoding="utf-8")
