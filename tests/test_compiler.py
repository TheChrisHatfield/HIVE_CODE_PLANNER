from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.chunker import chunk_markdown, chunk_plain_text
from hive_planner.config import RepoPaths
from hive_planner.discovery import discover_sources, doc_id_for_path
from hive_planner.emitter import _score_chunk, emit_cartridge
from hive_planner.indexer import load_chunk_index, load_document_index
from hive_planner.models import ChunkRecord
from hive_planner.normalizer import normalize_document
from hive_planner.normalizers.text import normalize_text
from hive_planner.pipeline import ingest


def test_doc_id_stable() -> None:
    assert doc_id_for_path("context-library/sources/a.md") == doc_id_for_path(
        "context-library/sources/a.md"
    )


def test_chunk_markdown_preserves_headings() -> None:
    text = "# Alpha\n\none\n\n## Beta\n\ntwo\n"
    chunks = chunk_markdown("abc123", text)
    headings = {c.heading_path for c in chunks}
    assert "Alpha" in headings
    assert "Alpha > Beta" in headings


def test_empty_markdown_produces_no_chunks() -> None:
    assert chunk_markdown("abc123", "   \n") == []
    assert chunk_markdown("abc123", "") == []


def test_heading_only_markdown_produces_no_chunks() -> None:
    assert chunk_markdown("abc123", "# Title Only\n") == []


def test_chunk_markdown_ignores_headings_in_code_blocks() -> None:
    text = "# Real\n\n```python\n# not a heading\nprint(1)\n```\n"
    chunks = chunk_markdown("abc123", text)
    headings = {c.heading_path for c in chunks}
    assert headings == {"Real"}


def test_ingest_keeps_index_when_processing_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sources = tmp_path / "context-library" / "sources"
    sources.mkdir(parents=True)
    good = sources / "good.md"
    bad = sources / "bad.md"
    good.write_text("# Good\n\ncontent\n", encoding="utf-8")
    bad.write_text("# Bad\n\ncontent\n", encoding="utf-8")

    paths = RepoPaths(root=tmp_path)
    ingest(paths)
    assert len(load_document_index(paths.document_index).documents) == 2

    original = normalize_document

    def flaky_normalize(paths_arg: RepoPaths, file_path: Path):
        if file_path.name == "bad.md":
            raise OSError("simulated read failure")
        return original(paths_arg, file_path)

    import hive_planner.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "normalize_document", flaky_normalize)
    report = pipeline_module.ingest(paths)
    assert report.skipped == 1
    assert len(load_document_index(paths.document_index).documents) == 2


def test_normalize_text_markdown_passthrough(tmp_path: Path) -> None:
    md = tmp_path / "note.md"
    md.write_text("# Title\n\nbody text\n", encoding="utf-8")
    result = normalize_text(md)
    assert result.normalized_body == "# Title\n\nbody text\n"
    assert result.title == "Title"


def test_normalize_text_plain_wraps_code_fence(tmp_path: Path) -> None:
    txt = tmp_path / "readme.txt"
    txt.write_text("plain content\n", encoding="utf-8")
    result = normalize_text(txt)
    assert result.normalized_body.startswith("# Readme\n\n```text\n")
    assert "plain content" in result.normalized_body


def test_empty_txt_produces_no_chunks(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    txt = paths.sources / "empty.txt"
    txt.write_text("", encoding="utf-8")
    doc, _, raw = normalize_document(paths, txt)
    assert chunk_plain_text(doc.doc_id, doc.title, raw) == []


def test_normalize_creates_output_dirs(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.sources.mkdir(parents=True)
    sample = paths.sources / "x.md"
    sample.write_text("# X\n\nbody\n", encoding="utf-8")
    normalize_document(paths, sample)
    assert paths.normalized_md.exists()
    assert paths.normalized_meta.exists()


def test_ingest_sample_repo(tmp_path: Path) -> None:
    sources = tmp_path / "context-library" / "sources" / "reference"
    sources.mkdir(parents=True)
    (sources / "sample.md").write_text("# Sample\n\ncompiler pipeline ingest\n", encoding="utf-8")

    paths = RepoPaths(root=tmp_path)
    report = ingest(paths)
    assert report.processed == 1
    assert paths.document_index.exists()
    assert paths.chunk_index.exists()
    assert discover_sources(paths)


def test_discover_ignores_unsupported(tmp_path: Path) -> None:
    sources = tmp_path / "context-library" / "sources"
    sources.mkdir(parents=True)
    (sources / "skip.json").write_text("{}", encoding="utf-8")
    (sources / "keep.md").write_text("# OK\n", encoding="utf-8")
    paths = RepoPaths(root=tmp_path)
    found = discover_sources(paths)
    assert len(found) == 1
    assert found[0].name == "keep.md"


def test_ingest_prunes_deleted_sources(tmp_path: Path) -> None:
    sources = tmp_path / "context-library" / "sources"
    sources.mkdir(parents=True)
    sample = sources / "gone.md"
    sample.write_text("# Gone\n\ncontent\n", encoding="utf-8")

    paths = RepoPaths(root=tmp_path)
    ingest(paths)
    assert load_document_index(paths.document_index).documents
    assert load_chunk_index(paths.chunk_index).chunks

    sample.unlink()
    report = ingest(paths)
    assert report.pruned == 1
    assert len(load_document_index(paths.document_index).documents) == 0
    assert len(load_chunk_index(paths.chunk_index).chunks) == 0


def test_ingest_warns_on_empty_source(tmp_path: Path) -> None:
    sources = tmp_path / "context-library" / "sources"
    sources.mkdir(parents=True)
    (sources / "empty.md").write_text("  \n", encoding="utf-8")

    paths = RepoPaths(root=tmp_path)
    report = ingest(paths)
    assert report.processed == 1
    assert any("No chunks produced" in w for w in report.warnings)
    assert len(load_chunk_index(paths.chunk_index).chunks) == 0


def test_indexer_tolerates_corrupt_json(tmp_path: Path) -> None:
    indexes = tmp_path / "context-library" / "indexes"
    indexes.mkdir(parents=True)
    (indexes / "document-index.json").write_text("{not json", encoding="utf-8")
    (indexes / "chunk-index.json").write_text('{"chunks": "bad"}', encoding="utf-8")

    paths = RepoPaths(root=tmp_path)
    assert load_document_index(paths.document_index).documents == []
    assert load_chunk_index(paths.chunk_index).chunks == []


def test_score_uses_word_boundaries() -> None:
    chunk = ChunkRecord("c1", "d1", "h", "cartridge compiler pipeline", keywords=[])
    assert _score_chunk(chunk, ["compiler"]) == 1
    assert _score_chunk(chunk, ["art"]) == 0
    assert _score_chunk(chunk, ["car"]) == 0


def test_emit_warns_without_index(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    _, warnings = emit_cartridge(paths, "cartridge-compiler-v1")
    assert any("No documents indexed" in w for w in warnings)
