from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.source4s import (
    SOURCE4S_DIR_NAME,
    list_source4s_files,
    run_source4s,
    stage_source4s_files,
)


def test_stage_source4s_accepts_txt_and_pdf(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    txt = tmp_path / "notes.txt"
    txt.write_text("Mission: build source4s upload path.\n", encoding="utf-8")
    pdf = tmp_path / "brief.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    copied, warnings = stage_source4s_files(paths, [txt, pdf, tmp_path / "skip.md"])
    assert len(copied) == 2
    assert any("source4s/notes.txt" in rel for rel in copied)
    assert any("source4s/brief.pdf" in rel for rel in copied)
    assert any("skip.md" in w for w in warnings)


def test_stage_source4s_deduplicates_filename(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    dest = paths.sources / SOURCE4S_DIR_NAME / "dup.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("existing", encoding="utf-8")

    incoming = tmp_path / "dup.txt"
    incoming.write_text("new content", encoding="utf-8")
    copied, _ = stage_source4s_files(paths, [incoming])
    assert copied == ["context-library/sources/source4s/dup-2.txt"]


def test_run_source4s_ingest_only(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    doc = tmp_path / "ref.txt"
    doc.write_text(
        "# Reference\n\nAcceptance criteria for source4s feature scope.\n",
        encoding="utf-8",
    )

    result = run_source4s(paths, [doc], feature=None, update_cartridge=False)
    assert result.ok
    assert result.copied
    assert result.indexed_staged == 1
    assert result.processed >= 1
    assert result.source_context_path is None
    assert list_source4s_files(paths)


def test_run_source4s_links_cartridge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "source4s-v1"
    doc = tmp_path / "plan.txt"
    doc.write_text(
        "# Plan\n\nMission: cartridge-linked reference uploads for planning agents.\n",
        encoding="utf-8",
    )

    emitted: list[str] = []

    def fake_emit(repo_paths: RepoPaths, feat: str, **kwargs: object) -> tuple[dict, list[str]]:
        assert feat == feature
        source_path = repo_paths.cartridge / "source-context.md"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("# Source Context\n\nlinked\n", encoding="utf-8")
        emitted.append(feat)
        return {"source_context": source_path}, []

    monkeypatch.setattr("hive_planner.source4s.emit_source_context", fake_emit)

    result = run_source4s(paths, [doc], feature=feature, update_cartridge=True)
    assert result.ok
    assert result.source_context_path == "cartridge/source-context.md"
    assert emitted == [feature]


def test_run_source4s_requires_feature_when_updating_cartridge(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    doc = tmp_path / "ref.txt"
    doc.write_text("# Reference\n\nMission content.\n", encoding="utf-8")

    result = run_source4s(paths, [doc], feature=None, update_cartridge=True)
    assert not result.ok
    assert result.indexed_staged == 1
    assert "Feature id is required" in result.error


def test_run_source4s_requires_files(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    result = run_source4s(paths, [], feature="x-v1")
    assert not result.ok
    assert result.error


def test_run_source4s_fails_when_staged_file_not_indexed(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    good = tmp_path / "good.txt"
    good.write_text("# Good\n\nIndexed reference content.\n", encoding="utf-8")
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(b"%PDF-1.4\nnot a real pdf structure")

    result = run_source4s(
        paths,
        [good, pdf],
        feature="load-sources-v1",
        update_cartridge=False,
    )
    assert not result.ok
    assert len(result.copied) == 2
    assert result.indexed_staged == 1
    assert result.error
    assert "1 of 2 staged file(s)" in result.error


def test_run_source4s_ingest_only_reports_partial_index_and_selection(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    good = tmp_path / "good.txt"
    good.write_text("# Good\n\nIndexed reference content.\n", encoding="utf-8")
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(b"%PDF-1.4\nnot a real pdf structure")
    docx = tmp_path / "notes.docx"
    docx.write_bytes(b"not docx")

    result = run_source4s(
        paths,
        [good, pdf, docx],
        feature="load-sources-v1",
        update_cartridge=False,
    )
    assert not result.ok
    assert "could not be indexed" in result.error
    assert "2 of 3 selected file(s)" in result.error


def test_run_source4s_reports_selection_error_when_all_staged_fail_index(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(b"%PDF-1.4\nnot a real pdf structure")
    docx = tmp_path / "notes.docx"
    docx.write_bytes(b"not docx")

    result = run_source4s(
        paths,
        [pdf, docx],
        feature="load-sources-v1",
        update_cartridge=False,
    )
    assert not result.ok
    assert "could not be indexed" in result.error
    assert "1 of 2 selected file(s)" in result.error


def test_run_source4s_index_error_omits_tesseract_when_ocr_disabled(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    good = tmp_path / "good.txt"
    good.write_text("# Good\n\nIndexed reference content.\n", encoding="utf-8")
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(b"%PDF-1.4\nnot a real pdf structure")

    result = run_source4s(
        paths,
        [good, pdf],
        feature="load-sources-v1",
        update_cartridge=False,
        ocr_pdf=False,
    )
    assert not result.ok
    assert result.error
    assert "Tesseract" not in result.error


def test_load_sources_still_links_cartridge_on_partial_index(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    good = tmp_path / "good.txt"
    good.write_text("# Good\n\nMission for load-sources-v1 partial index.\n", encoding="utf-8")
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(b"%PDF-1.4\nnot a real pdf structure")

    result = run_source4s(
        paths,
        [good, pdf],
        feature="load-sources-v1",
        update_cartridge=True,
    )
    assert not result.ok
    assert "1 of 2 staged file(s)" in result.error
    assert result.source_context_path == "cartridge/source-context.md"
    assert (paths.cartridge / "source-context.md").is_file()


def test_run_source4s_fails_when_selected_file_types_unsupported(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    good = tmp_path / "good.txt"
    good.write_text("# Good\n\nIndexed reference content.\n", encoding="utf-8")
    docx = tmp_path / "notes.docx"
    docx.write_bytes(b"not docx")

    result = run_source4s(
        paths,
        [good, docx],
        feature="load-sources-v1",
        update_cartridge=False,
    )
    assert not result.ok
    assert result.indexed_staged == 1
    assert len(result.copied) == 1
    assert "1 of 2 selected file(s)" in result.error


def test_load_sources_keeps_cartridge_error_on_partial_selection(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    good = tmp_path / "good.txt"
    good.write_text("# Good\n\nMission for load-sources-v1 partial selection.\n", encoding="utf-8")
    docx = tmp_path / "notes.docx"
    docx.write_bytes(b"not docx")

    source_context = paths.cartridge / "source-context.md"
    source_context.parent.mkdir(parents=True, exist_ok=True)
    source_context.write_text("<!-- MANUAL: reviewed -->\n\n# Source Context\n", encoding="utf-8")

    result = run_source4s(
        paths,
        [good, docx],
        feature="load-sources-v1",
        update_cartridge=True,
    )
    assert not result.ok
    assert "was not updated" in result.error
    assert "1 of 2 selected file(s)" in result.error


def test_load_sources_still_links_cartridge_on_partial_selection(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    good = tmp_path / "good.txt"
    good.write_text("# Good\n\nMission for load-sources-v1 partial selection.\n", encoding="utf-8")
    docx = tmp_path / "notes.docx"
    docx.write_bytes(b"not docx")

    result = run_source4s(
        paths,
        [good, docx],
        feature="load-sources-v1",
        update_cartridge=True,
    )
    assert not result.ok
    assert "1 of 2 selected file(s)" in result.error
    assert result.source_context_path == "cartridge/source-context.md"
    assert (paths.cartridge / "source-context.md").is_file()


def test_load_sources_partial_log_not_shown_for_unsupported_mix(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    good = tmp_path / "good.txt"
    good.write_text("# Good\n\nIndexed reference content.\n", encoding="utf-8")
    docx = tmp_path / "notes.docx"
    docx.write_bytes(b"not docx")

    result = run_source4s(
        paths,
        [good, docx],
        feature="load-sources-v1",
        update_cartridge=False,
    )
    assert not result.ok
    assert result.indexed_staged == len(result.copied)


def test_load_sources_prefers_newly_staged_docs_in_source_context(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "load-sources-v1"

    old = paths.sources / SOURCE4S_DIR_NAME / "old.txt"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text("# Old\n\nLegacy library content unrelated to feature.\n", encoding="utf-8")

    from hive_planner.pipeline import ingest

    ingest(paths)

    new_upload = tmp_path / "new.txt"
    new_upload.write_text(
        "# New upload\n\nMission for load-sources-v1 newly uploaded reference.\n",
        encoding="utf-8",
    )

    result = run_source4s(paths, [new_upload], feature=feature, update_cartridge=True)
    assert result.ok
    body = (paths.cartridge / "source-context.md").read_text(encoding="utf-8")
    new_path = "context-library/sources/source4s/new.txt"
    old_path = "context-library/sources/source4s/old.txt"
    assert new_path in body
    assert body.index(new_path) < body.index(old_path)


def test_load_sources_preserves_upload_order_in_source_context(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "load-sources-v1"
    first = tmp_path / "aaa-first.txt"
    second = tmp_path / "bbb-second.txt"
    first.write_text("# First\n\nFirst uploaded reference.\n", encoding="utf-8")
    second.write_text("# Second\n\nSecond uploaded reference.\n", encoding="utf-8")

    result = run_source4s(
        paths,
        [first, second],
        feature=feature,
        update_cartridge=True,
    )
    assert result.ok
    body = (paths.cartridge / "source-context.md").read_text(encoding="utf-8")
    first_path = "context-library/sources/source4s/aaa-first.txt"
    second_path = "context-library/sources/source4s/bbb-second.txt"
    assert body.index(first_path) < body.index(second_path)


def test_load_sources_reports_skipped_source_context(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "load-sources-v1"
    doc = tmp_path / "ref.txt"
    doc.write_text("# Reference\n\nMission for skipped source-context test.\n", encoding="utf-8")

    source_context = paths.cartridge / "source-context.md"
    source_context.parent.mkdir(parents=True, exist_ok=True)
    source_context.write_text("<!-- MANUAL: reviewed -->\n\n# Source Context\n", encoding="utf-8")

    result = run_source4s(paths, [doc], feature=feature, update_cartridge=True)
    assert not result.ok
    assert result.source_context_path is None
    assert result.error
    assert "was not updated" in result.error
    assert result.error not in result.warnings
    manifest_path = paths.cartridge / "manifest.json"
    assert not manifest_path.is_file()


def test_load_sources_force_overwrites_manual_source_context(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "load-sources-v1"
    doc = tmp_path / "ref.txt"
    doc.write_text("# Reference\n\nMission for force overwrite test.\n", encoding="utf-8")

    source_context = paths.cartridge / "source-context.md"
    source_context.parent.mkdir(parents=True, exist_ok=True)
    source_context.write_text("<!-- MANUAL: reviewed -->\n\n# Source Context\n", encoding="utf-8")

    result = run_source4s(paths, [doc], feature=feature, update_cartridge=True, force_delta=True)
    assert result.ok
    assert result.source_context_path == "cartridge/source-context.md"
    body = source_context.read_text(encoding="utf-8")
    assert "MANUAL" not in body.splitlines()[0]
    assert "Mission for force overwrite test" in body or "Reference" in body


def test_load_sources_skips_delta_and_pack_sync(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    feature = "load-sources-v1"
    holistic = paths.cartridge / "holistic.md"
    holistic.parent.mkdir(parents=True, exist_ok=True)
    holistic.write_text("<!-- MANUAL: keep me -->\n\n# Holistic\n", encoding="utf-8")

    doc = tmp_path / "ref.txt"
    doc.write_text("# Reference\n\nMission for load-sources feature.\n", encoding="utf-8")

    result = run_source4s(paths, [doc], feature=feature, update_cartridge=True)
    assert result.ok
    assert holistic.read_text(encoding="utf-8").startswith("<!-- MANUAL:")
    assert (paths.cartridge / "source-context.md").is_file()
    assert "pack_sync" not in json.loads((paths.cartridge / "manifest.json").read_text(encoding="utf-8")).get(
        "stats", {}
    )
