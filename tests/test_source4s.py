from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.discovery import doc_id_for_path
from hive_planner.source4s import (
    SOURCE4S_DIR_NAME,
    discover_source4s_files_in_folder,
    expand_source4s_inputs,
    list_source4s_files,
    merge_source4s_selection,
    pdf_ocr_quality_warnings,
    run_source4s,
    source4s_needs_pdf_support,
    source4s_selection_error,
    stage_source4s_files,
    staged_pdf_ocr_warnings,
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


def test_stage_source4s_refreshes_existing_basename(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    dest = paths.sources / SOURCE4S_DIR_NAME / "dup.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("existing", encoding="utf-8")

    incoming = tmp_path / "dup.txt"
    incoming.write_text("new content", encoding="utf-8")
    copied, _ = stage_source4s_files(paths, [incoming])
    assert copied == ["context-library/sources/source4s/dup.txt"]
    assert dest.read_text(encoding="utf-8") == "new content"
    assert not (paths.sources / SOURCE4S_DIR_NAME / "dup-2.txt").exists()


def test_stage_source4s_reuses_existing_library_file_without_duplicate(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    existing = paths.sources / SOURCE4S_DIR_NAME / "brief.pdf"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"%PDF-1.4 existing")

    copied, warnings = stage_source4s_files(paths, [existing])
    assert copied == ["context-library/sources/source4s/brief.pdf"]
    assert warnings == []
    assert not (paths.sources / SOURCE4S_DIR_NAME / "brief-2.pdf").exists()


def test_stage_source4s_dedupes_duplicate_selection(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    incoming = tmp_path / "once.txt"
    incoming.write_text("single upload", encoding="utf-8")

    copied, warnings = stage_source4s_files(paths, [incoming, incoming])
    assert copied == ["context-library/sources/source4s/once.txt"]
    assert warnings == []
    assert not (paths.sources / SOURCE4S_DIR_NAME / "once-2.txt").exists()


def test_stage_source4s_warns_on_duplicate_basename_in_batch(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    first = tmp_path / "dir_a" / "notes.txt"
    second = tmp_path / "dir_b" / "notes.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first version", encoding="utf-8")
    second.write_text("second version", encoding="utf-8")

    copied, warnings = stage_source4s_files(paths, [first, second])
    assert copied == ["context-library/sources/source4s/notes.txt"]
    assert len(warnings) == 1
    assert "duplicate basename" in warnings[0]
    assert (paths.sources / SOURCE4S_DIR_NAME / "notes.txt").read_text(encoding="utf-8") == (
        "second version"
    )


def test_run_source4s_fails_on_duplicate_basename_shortfall(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    first = tmp_path / "dir_a" / "notes.txt"
    second = tmp_path / "dir_b" / "notes.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("# First\n\nAlpha reference content.\n", encoding="utf-8")
    second.write_text("# Second\n\nBeta reference content.\n", encoding="utf-8")

    result = run_source4s(
        paths,
        [first, second],
        feature="load-sources-v1",
        update_cartridge=False,
    )
    assert not result.ok
    assert "duplicate filenames collide" in (result.error or "")


def test_discover_source4s_files_in_folder_finds_txt_and_pdf_recursively(tmp_path: Path) -> None:
    folder = tmp_path / "refs"
    (folder / "sub").mkdir(parents=True)
    (folder / "a.txt").write_text("a", encoding="utf-8")
    (folder / "b.pdf").write_bytes(b"%PDF-1.4")
    (folder / "sub" / "c.txt").write_text("c", encoding="utf-8")
    (folder / "skip.md").write_text("skip", encoding="utf-8")

    found = discover_source4s_files_in_folder(folder)
    assert {path.name for path in found} == {"a.txt", "b.pdf", "c.txt"}


def test_discover_source4s_files_in_folder_non_recursive(tmp_path: Path) -> None:
    folder = tmp_path / "refs"
    (folder / "sub").mkdir(parents=True)
    (folder / "top.txt").write_text("top", encoding="utf-8")
    (folder / "sub" / "nested.txt").write_text("nested", encoding="utf-8")

    found = discover_source4s_files_in_folder(folder, recursive=False)
    assert [path.name for path in found] == ["top.txt"]


def test_discover_source4s_files_in_folder_skips_common_vendor_dirs(tmp_path: Path) -> None:
    folder = tmp_path / "refs"
    (folder / "node_modules" / "pkg").mkdir(parents=True)
    (folder / "good").mkdir()
    (folder / "node_modules" / "pkg" / "bad.pdf").write_bytes(b"%PDF")
    (folder / "good" / "keep.txt").write_text("keep", encoding="utf-8")

    found = discover_source4s_files_in_folder(folder)
    assert [path.name for path in found] == ["keep.txt"]


def test_discover_source4s_files_in_folder_skips_project_internals_from_repo_root(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "refs").mkdir(parents=True)
    (project / "refs" / "external.txt").write_text("external", encoding="utf-8")
    internal = project / "context-library" / "sources" / "source4s"
    internal.mkdir(parents=True)
    (internal / "stale.txt").write_text("stale", encoding="utf-8")

    found = discover_source4s_files_in_folder(project)
    assert [path.name for path in found] == ["external.txt"]


def test_discover_source4s_files_in_folder_still_finds_files_under_context_library_root(
    tmp_path: Path,
) -> None:
    library = tmp_path / "context-library" / "sources" / "source4s"
    library.mkdir(parents=True)
    (library / "pick.txt").write_text("pick me", encoding="utf-8")

    found = discover_source4s_files_in_folder(library)
    assert [path.name for path in found] == ["pick.txt"]


def test_discover_source4s_files_in_folder_skips_unreadable_subdirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "refs"
    (folder / "ok").mkdir(parents=True)
    (folder / "ok" / "keep.txt").write_text("keep", encoding="utf-8")
    blocked = folder / "locked"

    real_iterdir = Path.iterdir

    def fake_iterdir(self: Path):
        if self == blocked:
            raise PermissionError("access denied")
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    found = discover_source4s_files_in_folder(folder)
    assert [path.name for path in found] == ["keep.txt"]


def test_source4s_selection_error_for_empty_folder_path(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert source4s_selection_error([empty]) == "No .txt or .pdf files found in the selected folder(s)."


def test_source4s_selection_error_none_when_folder_has_supported_files(tmp_path: Path) -> None:
    folder = tmp_path / "refs"
    folder.mkdir()
    (folder / "brief.txt").write_text("hello", encoding="utf-8")
    assert source4s_selection_error([folder]) is None


def test_source4s_needs_pdf_support_when_folder_argument_contains_pdf(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    folder = tmp_path / "refs"
    folder.mkdir()
    (folder / "brief.txt").write_text("txt", encoding="utf-8")
    (folder / "scan.pdf").write_bytes(b"%PDF")

    assert source4s_needs_pdf_support(paths, [folder]) is True
    assert source4s_needs_pdf_support(paths, [folder / "brief.txt"]) is False


def test_merge_source4s_selection_dedupes_paths(tmp_path: Path) -> None:
    first = tmp_path / "a.txt"
    second = tmp_path / "b.pdf"
    first.write_text("a", encoding="utf-8")
    second.write_bytes(b"%PDF")

    merged = merge_source4s_selection([first, second], [first, second])
    assert merged == [first, second]


def test_source4s_selection_error_flags_missing_and_unsupported(tmp_path: Path) -> None:
    good = tmp_path / "good.txt"
    good.write_text("ok", encoding="utf-8")
    bad = tmp_path / "notes.docx"
    bad.write_text("nope", encoding="utf-8")
    missing = tmp_path / "gone.txt"

    assert source4s_selection_error([]) == "Choose at least one .txt or .pdf file."
    assert source4s_selection_error([good]) is None
    assert source4s_selection_error([good, bad]) is None
    assert "no longer exist" in (source4s_selection_error([missing]) or "")
    assert "unsupported type(s)" in (source4s_selection_error([bad]) or "")
    mixed = source4s_selection_error([missing, bad])
    assert mixed is not None
    assert "no longer exist" in mixed
    assert "unsupported type(s)" in mixed


def test_expand_source4s_inputs_expands_folders_and_dedupes(tmp_path: Path) -> None:
    folder = tmp_path / "refs"
    folder.mkdir()
    txt = folder / "a.txt"
    txt.write_text("a", encoding="utf-8")

    expanded = expand_source4s_inputs([folder, txt])
    assert expanded == [txt]


def test_run_source4s_expands_folder_argument(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    folder = tmp_path / "refs"
    folder.mkdir()
    (folder / "brief.txt").write_text(
        "# Brief\n\nReference content for folder upload.\n",
        encoding="utf-8",
    )

    result = run_source4s(
        paths,
        [folder],
        feature="load-sources-v1",
        update_cartridge=False,
    )
    assert result.ok
    assert result.copied == ["context-library/sources/source4s/brief.txt"]


def test_run_source4s_reports_empty_folder_argument(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    folder = tmp_path / "empty"
    folder.mkdir()

    result = run_source4s(
        paths,
        [folder],
        feature="load-sources-v1",
        update_cartridge=False,
    )
    assert not result.ok
    assert "No .txt or .pdf files found in the selected folder(s)" in (result.error or "")


def test_run_source4s_rejects_all_unsupported_selection(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    doc = tmp_path / "notes.docx"
    doc.write_text("unsupported", encoding="utf-8")

    result = run_source4s(paths, [doc], feature="load-sources-v1", update_cartridge=False)
    assert not result.ok
    assert "unsupported type(s)" in (result.error or "")

def test_pdf_index_failure_hint_omits_pip_on_portable(monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.source4s import _pdf_index_failure_hint

    monkeypatch.setattr("hive_planner.runtime_paths.is_portable_runtime", lambda: True)
    monkeypatch.setattr("hive_planner.source4s.pdf_support_available", lambda: True)

    hint = _pdf_index_failure_hint(
        ocr_pdf=True,
        pdf_failures=["context-library/sources/source4s/broken.pdf"],
    )
    assert "pip install" not in hint
    assert "Tesseract OCR" in hint


def test_pdf_index_failure_hint_uses_generic_message_for_txt_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hive_planner.source4s import _pdf_index_failure_hint

    monkeypatch.setattr("hive_planner.runtime_paths.is_portable_runtime", lambda: False)

    hint = _pdf_index_failure_hint(ocr_pdf=True, pdf_failures=[])
    assert hint == "see warnings"
    assert "pip install" not in hint


def test_run_source4s_ignores_duplicate_selection_for_selection_error(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    good = tmp_path / "good.txt"
    good.write_text("# Good\n\nIndexed reference content.\n", encoding="utf-8")

    result = run_source4s(
        paths,
        [good, good],
        feature="load-sources-v1",
        update_cartridge=False,
    )
    assert result.ok
    assert result.error is None
    assert len(result.copied) == 1


def test_run_source4s_skips_selection_error_for_missing_files(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    good = tmp_path / "good.txt"
    good.write_text("# Good\n\nIndexed reference content.\n", encoding="utf-8")
    missing = tmp_path / "missing.txt"

    result = run_source4s(
        paths,
        [good, missing],
        feature="load-sources-v1",
        update_cartridge=False,
    )
    assert result.ok
    assert result.error is None
    assert any("not a file" in w for w in result.warnings)


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


def test_run_source4s_keeps_partial_index_error_when_feature_missing(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    good = tmp_path / "good.txt"
    good.write_text("# Good\n\nIndexed reference content.\n", encoding="utf-8")
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(b"%PDF-1.4\nnot a real pdf structure")

    result = run_source4s(
        paths,
        [good, pdf],
        feature=None,
        update_cartridge=True,
    )
    assert not result.ok
    assert "Feature id is required" in result.error
    assert "could not be indexed" in result.error


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


def test_staged_pdf_ocr_warnings_ignores_unindexed_stale_metadata(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    rel = "context-library/sources/source4s/stale.pdf"
    meta_path = paths.normalized_meta / f"{doc_id_for_path(rel)}.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps({"ocr_unresolved_pages": [2]}),
        encoding="utf-8",
    )

    warnings = staged_pdf_ocr_warnings(paths, [])
    assert warnings == []


def test_staged_pdf_ocr_warnings_ignores_stale_metadata_hash(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    rel = "context-library/sources/source4s/mixed.pdf"
    meta_path = paths.normalized_meta / f"{doc_id_for_path(rel)}.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps({"content_hash": "stale-hash", "ocr_unresolved_pages": [2]}),
        encoding="utf-8",
    )
    paths.document_index.parent.mkdir(parents=True, exist_ok=True)
    paths.document_index.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "doc_id": doc_id_for_path(rel),
                        "source_path": rel,
                        "format": "pdf",
                        "title": "Mixed",
                        "content_hash": "fresh-hash",
                        "category": "source4s",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    warnings = staged_pdf_ocr_warnings(paths, [rel])
    assert warnings == []


def test_staged_pdf_ocr_warnings_ignores_metadata_without_content_hash(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    rel = "context-library/sources/source4s/mixed.pdf"
    meta_path = paths.normalized_meta / f"{doc_id_for_path(rel)}.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps({"ocr_unresolved_pages": [2]}), encoding="utf-8")
    paths.document_index.parent.mkdir(parents=True, exist_ok=True)
    paths.document_index.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "doc_id": doc_id_for_path(rel),
                        "source_path": rel,
                        "format": "pdf",
                        "title": "Mixed",
                        "content_hash": "current-hash",
                        "category": "source4s",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    warnings = staged_pdf_ocr_warnings(paths, [rel])
    assert warnings == []


def test_staged_pdf_ocr_warnings_reads_normalized_metadata(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    rel = "context-library/sources/source4s/mixed.pdf"
    meta_path = paths.normalized_meta / f"{doc_id_for_path(rel)}.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(
            {
                "content_hash": "current-hash",
                "ocr_unresolved_pages": [2, 3],
                "ocr_skipped_pages": [4],
                "ocr_disabled_pages": [5],
            }
        ),
        encoding="utf-8",
    )
    paths.document_index.parent.mkdir(parents=True, exist_ok=True)
    paths.document_index.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "doc_id": doc_id_for_path(rel),
                        "source_path": rel,
                        "format": "pdf",
                        "title": "Mixed",
                        "content_hash": "current-hash",
                        "category": "source4s",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    warnings = staged_pdf_ocr_warnings(paths, [rel])
    assert len(warnings) == 3
    assert "unresolved" in warnings[0]
    assert "Tesseract unavailable" in warnings[1]
    assert "OCR disabled" in warnings[2]


def test_pdf_ocr_quality_warnings_filters_pdf_ocr_messages() -> None:
    warnings = [
        "Skipped (not a file): x",
        "PDF a.pdf: OCR left 1 page(s) unresolved: [2]",
        "PDF b.pdf: OCR disabled — 1 image page(s) not OCR'd: [3]",
        "PDF c.pdf: Tesseract unavailable — 1 image page(s) not OCR'd: [4]",
    ]
    matched = pdf_ocr_quality_warnings(warnings)
    assert len(matched) == 3
    assert all(w.startswith("PDF ") for w in matched)


def test_run_source4s_fails_when_staged_pdf_has_ocr_quality_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    doc = tmp_path / "scan.pdf"
    doc.write_bytes(b"%PDF-1.4 stub")

    monkeypatch.setattr(
        "hive_planner.source4s.staged_pdf_ocr_warnings",
        lambda *_args, **_kwargs: [
            "PDF context-library/sources/source4s/scan.pdf: OCR left 1 page(s) unresolved: [2]"
        ],
    )

    result = run_source4s(
        paths,
        [doc],
        feature="load-sources-v1",
        update_cartridge=False,
    )
    assert not result.ok
    assert "OCR quality issues" in (result.error or "")


def test_run_source4s_skips_cartridge_when_staged_pdf_has_ocr_quality_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    doc = tmp_path / "scan.pdf"
    doc.write_bytes(b"%PDF-1.4 stub")

    monkeypatch.setattr(
        "hive_planner.source4s.staged_pdf_ocr_warnings",
        lambda *_args, **_kwargs: [
            "PDF context-library/sources/source4s/scan.pdf: OCR left 1 page(s) unresolved: [2]"
        ],
    )

    result = run_source4s(
        paths,
        [doc],
        feature="load-sources-v1",
        update_cartridge=True,
    )
    assert not result.ok
    assert "OCR quality issues" in (result.error or "")
    assert result.source_context_path is None
    assert not (paths.cartridge / "source-context.md").is_file()


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


def test_run_source4s_reports_stage_warning_when_nothing_staged(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    docx = tmp_path / "notes.docx"
    docx.write_bytes(b"not docx")

    result = run_source4s(paths, [docx], feature="load-sources-v1", update_cartridge=False)
    assert not result.ok
    assert result.copied == []
    assert "Load Sources accepts .txt and .pdf only" in result.error


def test_run_source4s_reports_all_stage_warnings_when_nothing_staged(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    docx = tmp_path / "notes.docx"
    docx.write_bytes(b"not docx")
    md = tmp_path / "readme.md"
    md.write_text("# Nope", encoding="utf-8")

    result = run_source4s(paths, [docx, md], feature="load-sources-v1", update_cartridge=False)
    assert not result.ok
    assert result.copied == []
    assert result.error is not None
    assert "notes.docx" in result.error
    assert "readme.md" in result.error


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


def test_source4s_cli_exits_nonzero_on_pdf_ocr_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.cli import main
    from hive_planner.source4s import Source4sResult

    def fake_run(*_args: object, **_kwargs: object) -> Source4sResult:
        return Source4sResult(
            ok=True,
            copied=["context-library/sources/source4s/mixed.pdf"],
            indexed_staged=1,
            warnings=[
                "PDF context-library/sources/source4s/mixed.pdf: OCR disabled — "
                "1 image page(s) not OCR'd: [2]"
            ],
        )

    monkeypatch.setattr("hive_planner.source4s.run_source4s", fake_run)

    txt = tmp_path / "notes.txt"
    txt.write_text("reference", encoding="utf-8")
    code = main(["--root", str(tmp_path), "source4s", "--ingest-only", "--files", str(txt)])
    assert code == 1


def test_source4s_cli_exits_zero_without_pdf_ocr_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.cli import main
    from hive_planner.source4s import Source4sResult

    def fake_run(*_args: object, **_kwargs: object) -> Source4sResult:
        return Source4sResult(
            ok=True,
            copied=["context-library/sources/source4s/notes.txt"],
            indexed_staged=1,
            warnings=["Skipped (not a file): elsewhere"],
        )

    monkeypatch.setattr("hive_planner.source4s.run_source4s", fake_run)

    txt = tmp_path / "notes.txt"
    txt.write_text("reference", encoding="utf-8")
    code = main(["--root", str(tmp_path), "source4s", "--ingest-only", "--files", str(txt)])
    assert code == 0


def test_source4s_cli_exits_nonzero_on_pdf_dependency_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.cli import main
    from hive_planner.source4s import Source4sResult

    def fake_run(*_args: object, **_kwargs: object) -> Source4sResult:
        return Source4sResult(
            ok=True,
            copied=["context-library/sources/source4s/notes.txt"],
            indexed_staged=1,
            warnings=["Skipped need.pdf: PDF support requires pymupdf"],
        )

    monkeypatch.setattr("hive_planner.source4s.run_source4s", fake_run)

    txt = tmp_path / "notes.txt"
    txt.write_text("reference", encoding="utf-8")
    code = main(["--root", str(tmp_path), "source4s", "--ingest-only", "--files", str(txt)])
    assert code == 1
