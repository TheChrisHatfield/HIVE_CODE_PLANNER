from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.chunker import chunk_markdown
from hive_planner.config import RepoPaths
from hive_planner.discovery import doc_id_for_path
from hive_planner.emitter import MAX_SOURCE_DOCUMENTS, MAX_SOURCE_EXCERPTS, select_chunks
from hive_planner.indexer import load_chunk_index, load_document_index
from hive_planner.models import ChunkRecord
from hive_planner.normalizer import normalize_document
from hive_planner.normalizers import MissingDependencyError
from hive_planner.normalizers.pdf import normalize_pdf
from hive_planner.pipeline import ingest


def _make_pdf(path: Path, pages: list[str]) -> None:
    import fitz

    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def _make_docx(path: Path, paragraphs: list[tuple[str, str | None]]) -> None:
    from docx import Document

    doc = Document()
    for text, style in paragraphs:
        p = doc.add_paragraph(text)
        if style:
            p.style = style
    doc.save(path)


@pytest.fixture
def pdf_dep():
    pytest.importorskip("fitz")
    return True


@pytest.fixture
def docx_dep():
    pytest.importorskip("docx")
    return True


def test_nested_heading_paths() -> None:
    text = "# One\n\na\n\n## Two\n\nb\n\n### Three\n\nc\n"
    paths = {c.heading_path for c in chunk_markdown("id", text)}
    assert "One" in paths
    assert "One > Two" in paths
    assert "One > Two > Three" in paths


def test_pdf_page_metadata(pdf_dep, tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _make_pdf(pdf_path, ["cartridge compiler page one", "second page text"])
    result = normalize_pdf(pdf_path)
    assert "Page 1" in result.normalized_body
    chunks = chunk_markdown("doc1", result.normalized_body)
    pages = [c.page for c in chunks if c.page is not None]
    assert 1 in pages


def test_empty_pdf_skipped(pdf_dep, tmp_path: Path) -> None:
    import fitz

    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    pdf = paths.sources / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf)
    doc.close()

    report = ingest(paths)
    assert report.skipped == 1
    assert any("extractable" in w.lower() or "empty" in w.lower() for w in report.warnings)


def test_corrupt_pdf_skipped(pdf_dep, tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.sources.mkdir(parents=True)
    bad = paths.sources / "bad.pdf"
    bad.write_bytes(b"not a real pdf")
    report = ingest(paths)
    assert report.skipped == 1


def test_docx_without_headings(docx_dep, tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.sources.mkdir(parents=True)
    docx = paths.sources / "plain.docx"
    _make_docx(docx, [("Hello body text for compiler.", None), ("More content here.", None)])
    report = ingest(paths)
    assert report.processed == 1
    chunks = load_chunk_index(paths.chunk_index).chunks
    assert chunks
    assert any("Hello" in c.text for c in chunks)


def test_pdf_reingest_same_doc_id(pdf_dep, tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.sources.mkdir(parents=True)
    pdf = paths.sources / "ref" / "doc.pdf"
    pdf.parent.mkdir(parents=True)
    _make_pdf(pdf, ["version one"])
    ingest(paths)
    doc_id_1 = load_document_index(paths.document_index).documents[0].doc_id
    hash_1 = load_document_index(paths.document_index).documents[0].content_hash

    _make_pdf(pdf, ["version two changed"])
    ingest(paths)
    doc = load_document_index(paths.document_index).documents[0]
    assert doc.doc_id == doc_id_1
    assert doc.content_hash != hash_1


def test_missing_pdf_dep_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.sources.mkdir(parents=True)
    pdf = paths.sources / "need.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    def fail_pdf(_path: Path):
        raise MissingDependencyError("PDF support requires pymupdf")

    monkeypatch.setattr("hive_planner.normalizer.normalize_pdf", fail_pdf)
    (paths.sources / "ok.md").write_text("# OK\n\nmd still works\n", encoding="utf-8")
    report = ingest(paths)
    assert report.processed == 1
    assert report.skipped == 1
    assert any("pymupdf" in w for w in report.warnings)


def test_emitter_respects_doc_and_excerpt_limits() -> None:
    chunks = []
    for doc_idx in range(5):
        doc_id = f"doc{doc_idx}"
        for chunk_idx in range(3):
            chunks.append(
                ChunkRecord(
                    chunk_id=f"{doc_id}-c{chunk_idx}",
                    doc_id=doc_id,
                    heading_path="h",
                    text=f"cartridge compiler doc {doc_idx} chunk {chunk_idx}",
                    chunk_index=chunk_idx,
                )
            )
    selected = select_chunks(chunks, "cartridge-compiler-v2")
    assert len(selected) <= MAX_SOURCE_EXCERPTS
    assert len({c.doc_id for c in selected}) <= MAX_SOURCE_DOCUMENTS


def test_merge_preferred_chunks_respects_max_documents() -> None:
    from hive_planner.emitter import merge_preferred_chunks

    chunks = [
        ChunkRecord(
            chunk_id=f"doc{i}-c0",
            doc_id=f"doc{i}",
            heading_path="h",
            text=f"preferred upload {i}",
            chunk_index=0,
        )
        for i in range(6)
    ]
    selected = select_chunks(chunks, "preferred-upload")
    prefer_ids = [f"doc{i}" for i in range(6)]
    merged = merge_preferred_chunks(selected, chunks, prefer_ids)
    assert len(merged) <= MAX_SOURCE_EXCERPTS
    assert len({c.doc_id for c in merged}) <= MAX_SOURCE_DOCUMENTS
    # First preferred uploads win the document slots
    assert {c.doc_id for c in merged} == {"doc0", "doc1", "doc2"}
