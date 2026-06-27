from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.discovery import content_hash
from hive_planner.embeddings import (
    EmbeddingIndex,
    EmbeddingRecord,
    cosine_similarity,
    embed_query,
    embed_texts,
    load_embedding_index,
    prune_embedding_index,
    sync_embedding_index,
)
from hive_planner.emitter import keyword_score, select_chunks
from hive_planner.indexer import save_chunk_index
from hive_planner.models import ChunkIndex, ChunkRecord
from hive_planner.pipeline import ingest


def test_cosine_similarity_identical() -> None:
    vectors, _ = embed_texts(["compiler pipeline ingest"])
    assert cosine_similarity(vectors[0], vectors[0]) == pytest.approx(1.0)


def test_sync_embedding_index_skips_unchanged_hash(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    chunk = ChunkRecord(
        chunk_id="abc-c001",
        doc_id="abc",
        heading_path="h",
        text="compiler pipeline semantic retrieval",
        chunk_index=0,
    )
    save_chunk_index(paths.chunk_index, ChunkIndex(chunks=[chunk]))
    sync_embedding_index(paths.embedding_index, ChunkIndex(chunks=[chunk]))
    first = load_embedding_index(paths.embedding_index)
    sync_embedding_index(paths.embedding_index, ChunkIndex(chunks=[chunk]))
    second = load_embedding_index(paths.embedding_index)
    assert len(first.embeddings) == 1
    assert second.embeddings[0].content_hash == first.embeddings[0].content_hash


def test_prune_embedding_index_removes_orphans() -> None:
    index = EmbeddingIndex(
        embeddings=[
            EmbeddingRecord("keep", content_hash("a"), "hive-tfidf-v1", [1.0, 0.0]),
            EmbeddingRecord("drop", content_hash("b"), "hive-tfidf-v1", [0.0, 1.0]),
        ]
    )
    removed = prune_embedding_index(index, {"keep"})
    assert removed == 1
    assert len(index.embeddings) == 1


def test_hybrid_select_prefers_semantic_match() -> None:
    query = "embedding retrieval semantic ranking"
    query_vec = embed_query(query)
    chunks = [
        ChunkRecord("a-c0", "a", "h", "unrelated kitchen recipes and cooking tips", chunk_index=0),
        ChunkRecord("b-c0", "b", "h", "vector semantic ranking improves retrieval quality", chunk_index=0),
    ]
    vectors = {}
    for chunk in chunks:
        vecs, _ = embed_texts([chunk.text])
        vectors[chunk.chunk_id] = vecs[0]

    terms = [t for t in query.replace("-", " ").split() if t]
    assert keyword_score(chunks[0], terms) == 0
    selected = select_chunks(chunks, query, embedding_vectors=vectors)
    assert selected[0].doc_id == "b"


def test_ingest_embed_builds_index(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    sample = paths.sources / "semantic.md"
    sample.write_text("# Semantic\n\nvector embedding retrieval improves ranking\n", encoding="utf-8")
    report = ingest(paths, embed=True)
    assert report.processed == 1
    embed_index = load_embedding_index(paths.embedding_index)
    assert len(embed_index.embeddings) >= 1


def test_ingest_without_embed_leaves_embedding_empty(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    sample = paths.sources / "plain.md"
    sample.write_text("# Plain\n\nkeyword only path\n", encoding="utf-8")
    ingest(paths, embed=False)
    embed_index = load_embedding_index(paths.embedding_index)
    assert embed_index.embeddings == []


def test_ingest_prune_removes_stale_embeddings(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    sample = paths.sources / "gone.md"
    sample.write_text("# Gone\n\ntemporary semantic chunk\n", encoding="utf-8")
    ingest(paths, embed=True)
    assert load_embedding_index(paths.embedding_index).embeddings
    sample.unlink()
    report = ingest(paths, embed=False)
    assert report.pruned == 1
    assert load_embedding_index(paths.embedding_index).embeddings == []
