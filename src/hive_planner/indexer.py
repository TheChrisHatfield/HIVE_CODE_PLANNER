from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from hive_planner.models import ChunkIndex, ChunkRecord, DocumentIndex, SourceDocument


def _load_json_list(path: Path, key: str) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    rows = data.get(key, [])
    return list(rows) if isinstance(rows, list) else []


def _parse_documents(rows: list[dict]) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            docs.append(SourceDocument(**row))
        except TypeError:
            continue
    return docs


def _parse_chunks(rows: list[dict]) -> list[ChunkRecord]:
    chunks: list[ChunkRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            if "page" not in row:
                row = {**row, "page": None}
            chunks.append(ChunkRecord(**row))
        except TypeError:
            continue
    return chunks


def load_document_index(path: Path) -> DocumentIndex:
    rows = _load_json_list(path, "documents")
    return DocumentIndex(documents=_parse_documents(rows))


def load_chunk_index(path: Path) -> ChunkIndex:
    rows = _load_json_list(path, "chunks")
    return ChunkIndex(chunks=_parse_chunks(rows))


def save_document_index(path: Path, index: DocumentIndex) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"documents": [asdict(doc) for doc in index.documents]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_chunk_index(path: Path, index: ChunkIndex) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"chunks": [asdict(chunk) for chunk in index.chunks]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def upsert_document(index: DocumentIndex, doc: SourceDocument) -> None:
    index.documents = [d for d in index.documents if d.doc_id != doc.doc_id]
    index.documents.append(doc)
    index.documents.sort(key=lambda d: d.source_path)


def upsert_chunks(index: ChunkIndex, doc_id: str, chunks: list[ChunkRecord]) -> None:
    index.chunks = [c for c in index.chunks if c.doc_id != doc_id]
    index.chunks.extend(chunks)
    index.chunks.sort(key=lambda c: (c.doc_id, c.chunk_index))


def prune_index(
    doc_index: DocumentIndex,
    chunk_index: ChunkIndex,
    active_doc_ids: set[str],
) -> list[str]:
    """Remove index entries (and return pruned doc_ids) not present in active_doc_ids."""
    pruned_doc_ids = [d.doc_id for d in doc_index.documents if d.doc_id not in active_doc_ids]
    doc_index.documents = [d for d in doc_index.documents if d.doc_id in active_doc_ids]
    chunk_index.chunks = [c for c in chunk_index.chunks if c.doc_id in active_doc_ids]
    return pruned_doc_ids
