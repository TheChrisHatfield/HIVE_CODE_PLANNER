from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from hive_planner import __version__ as COMPILER_VERSION
from hive_planner.config import RepoPaths
from hive_planner.indexer import load_chunk_index, load_document_index
from hive_planner.embeddings import embed_query, embedding_lookup, load_embedding_index
from hive_planner.models import ChunkRecord

MAX_SOURCE_DOCUMENTS = 3
MAX_SOURCE_EXCERPTS = 8
KEYWORD_WEIGHT = 0.4
SEMANTIC_WEIGHT = 0.6


def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)


def _score_chunk(chunk: ChunkRecord, query_terms: list[str]) -> int:
    haystack = " ".join([chunk.text, " ".join(chunk.keywords), chunk.heading_path])
    return sum(1 for term in query_terms if _term_pattern(term).search(haystack))


def keyword_score(chunk: ChunkRecord, query_terms: list[str]) -> int:
    return _score_chunk(chunk, query_terms)


def _hybrid_score(
    chunk: ChunkRecord,
    query_terms: list[str],
    query_vector: list[float] | None,
    vectors: dict[str, list[float]],
) -> float:
    kw = keyword_score(chunk, query_terms)
    kw_component = kw / max(len(query_terms), 1)
    if query_vector and chunk.chunk_id in vectors:
        from hive_planner.embeddings import cosine_similarity

        sem = max(0.0, cosine_similarity(query_vector, vectors[chunk.chunk_id]))
        return KEYWORD_WEIGHT * kw_component + SEMANTIC_WEIGHT * sem
    return float(kw)


def select_chunks(
    chunks: list[ChunkRecord],
    feature: str,
    limit: int = MAX_SOURCE_EXCERPTS,
    *,
    embedding_vectors: dict[str, list[float]] | None = None,
    embedding_model_id: str | None = None,
) -> list[ChunkRecord]:
    terms = [t for t in feature.lower().replace("-", " ").split() if t]
    query_vector = (
        embed_query(feature, model_id=embedding_model_id) if embedding_vectors else None
    )
    ranked = sorted(
        chunks,
        key=lambda c: _hybrid_score(c, terms, query_vector, embedding_vectors or {}),
        reverse=True,
    )
    selected: list[ChunkRecord] = []
    doc_ids: set[str] = set()

    for chunk in ranked:
        if len(selected) >= limit:
            break
        if chunk.doc_id not in doc_ids and len(doc_ids) >= MAX_SOURCE_DOCUMENTS:
            continue
        selected.append(chunk)
        doc_ids.add(chunk.doc_id)

    return selected


def emit_cartridge(
    paths: RepoPaths,
    feature: str,
    *,
    force_delta: bool = False,
) -> tuple[dict[str, Path], list[str]]:
    paths.ensure_dirs()
    paths.cartridge.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    doc_index = load_document_index(paths.document_index)
    chunk_index = load_chunk_index(paths.chunk_index)
    if not doc_index.documents:
        warnings.append("No documents indexed — run ingest before emit.")
    if not chunk_index.chunks:
        warnings.append("No chunks indexed — source-context will be empty.")

    terms = [t for t in feature.lower().replace("-", " ").split() if t]
    embed_index = load_embedding_index(paths.embedding_index)
    vectors = embedding_lookup(embed_index) if embed_index.embeddings else None
    embedding_model_id = embed_index.model_id if vectors else None
    selected = select_chunks(
        chunk_index.chunks,
        feature,
        embedding_vectors=vectors,
        embedding_model_id=embedding_model_id,
    )
    if chunk_index.chunks and terms and selected:
        if vectors:
            query_vector = embed_query(feature, model_id=embedding_model_id)
            if max(_hybrid_score(c, terms, query_vector, vectors) for c in selected) <= 0:
                warnings.append(
                    f"No chunks matched feature terms/embeddings for '{feature}' — using best available excerpts."
                )
        elif max(keyword_score(c, terms) for c in selected) == 0:
            warnings.append(f"No chunks matched feature terms for '{feature}' — using best available excerpts.")

    manifest = {
        "schema_version": "cartridge.v1",
        "cartridge_id": f"ctx-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{feature}",
        "title": f"Cartridge context for {feature}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {"type": "context-library", "compiler": "hive_planner", "version": COMPILER_VERSION},
        "targets": {"delta_docs": True, "spec_kit": True, "cursor_rules": False, "agents_md": False},
        "features": [feature],
        "status": "draft",
        "source_context": {
            "enabled": True,
            "library_root": "context-library/sources",
            "normalized_root": "context-library/normalized",
            "mode": "supplemental",
            "max_documents": MAX_SOURCE_DOCUMENTS,
            "max_excerpts": MAX_SOURCE_EXCERPTS,
        },
        "stats": {
            "documents": len(doc_index.documents),
            "chunks": len(chunk_index.chunks),
            "embeddings": len(embed_index.embeddings),
            "selected_chunks": len(selected),
            "selected_documents": len({c.doc_id for c in selected}),
            "retrieval_mode": "hybrid" if vectors else "keyword",
        },
    }

    from hive_planner.delta_emit import sync_delta_cartridge

    delta_results, delta_paths, delta_warnings = sync_delta_cartridge(paths, feature, force=force_delta)
    warnings.extend(delta_warnings)

    from hive_planner.cartridge_pack import emit_cartridge_pack, validate_pack_completeness

    pack_paths, pack_results, pack_warnings = emit_cartridge_pack(paths, feature, force=force_delta)
    warnings.extend(pack_warnings)

    manifest["stats"]["delta_sync"] = delta_results
    manifest["stats"]["pack_sync"] = pack_results

    lines = [
        "# Source Context",
        "",
        f"**Feature:** `{feature}`",
        f"**Generated:** {manifest['created_at']}",
        f"**Limits:** max {MAX_SOURCE_DOCUMENTS} documents, max {MAX_SOURCE_EXCERPTS} excerpts",
        "",
        "## Active documents",
    ]
    doc_ids = {c.doc_id for c in selected}
    for doc in doc_index.documents:
        if doc.doc_id in doc_ids:
            lines.append(f"- {doc.source_path} — {doc.title}")

    lines.extend(["", "## Retrieved excerpts", ""])
    for chunk in selected:
        doc = next((d for d in doc_index.documents if d.doc_id == chunk.doc_id), None)
        source_label = doc.source_path if doc else chunk.doc_id
        page_note = f", page {chunk.page}" if chunk.page is not None else ""
        lines.append(f"### Source: {source_label} ({chunk.heading_path}{page_note})")
        summary = chunk.text.strip().replace("\n", " ")
        if len(summary) > 400:
            summary = summary[:397] + "..."
        lines.append(f"- {summary}")
        lines.append("")

    lines.extend(
        [
            "## Why relevant",
            "- Tertiary context retrieved by "
            + ("hybrid keyword/embedding match" if vectors else "keyword match")
            + " for the active feature.",
            "- Does not override Delta docs, spec, plan, or tasks.",
            "",
            "## Hooks",
            "- `planning.rosetta`",
            "- `compiler.pipeline`",
            "- `context.document_sourcing`",
        ]
    )

    source_context_path = paths.cartridge / "source-context.md"
    source_context_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    outputs: dict[str, Path] = {
        "source_context": source_context_path,
    }
    outputs.update(delta_paths)
    outputs.update(pack_paths)

    manifest["stats"]["pack_files"] = len(outputs) + 1
    rel_files = sorted(
        path.relative_to(paths.root).as_posix() for path in outputs.values()
    )
    rel_files.append("cartridge/manifest.json")
    manifest["files"] = rel_files
    manifest_path = paths.cartridge / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    outputs["manifest"] = manifest_path

    for missing in validate_pack_completeness(paths):
        warnings.append(f"Missing required pack file: {missing}")

    return outputs, warnings
