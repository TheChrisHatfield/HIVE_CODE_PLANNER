from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from hive_planner import __version__ as COMPILER_VERSION
from hive_planner.config import RepoPaths, validate_feature_id
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


def merge_preferred_chunks(
    selected: list[ChunkRecord],
    chunks: list[ChunkRecord],
    prefer_doc_ids: list[str],
    limit: int = MAX_SOURCE_EXCERPTS,
) -> list[ChunkRecord]:
    """Ensure chunks from preferred documents appear first in source-context excerpts."""
    if not prefer_doc_ids:
        return selected[:limit]
    merged: list[ChunkRecord] = []
    seen: set[str] = set()
    for doc_id in prefer_doc_ids:
        for chunk in chunks:
            if chunk.doc_id == doc_id and chunk.chunk_id not in seen:
                merged.append(chunk)
                seen.add(chunk.chunk_id)
                break
    for chunk in selected:
        if len(merged) >= limit:
            break
        if chunk.chunk_id not in seen:
            merged.append(chunk)
            seen.add(chunk.chunk_id)
    return merged[:limit]


def _warn_unembedded_preferred_docs(
    warnings: list[str],
    *,
    prefer_doc_ids: list[str],
    doc_index,
    chunk_index,
    embed_index,
) -> None:
    """Warn when freshly staged sources were chunked but not embedded."""
    vectors_lookup = embedding_lookup(embed_index)
    for doc_id in prefer_doc_ids:
        doc = next((d for d in doc_index.documents if d.doc_id == doc_id), None)
        if doc is None:
            continue
        doc_chunks = [c for c in chunk_index.chunks if c.doc_id == doc_id]
        if doc_chunks and not any(c.chunk_id in vectors_lookup for c in doc_chunks):
            warnings.append(
                f"Staged source {doc.source_path} has {len(doc_chunks)} chunk(s) but no embeddings — "
                "turn on Improve AI search quality in Load cartridge, or run: "
                "py -3.11 -m hive_planner ingest --embed"
            )


def _load_cartridge_manifest(paths: RepoPaths) -> dict:
    manifest_path = paths.cartridge / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _merge_source_context_manifest(existing: dict, patch: dict) -> dict:
    if not existing:
        return patch
    merged = dict(existing)
    merged["source_context"] = patch["source_context"]
    merged["stats"] = {**existing.get("stats", {}), **patch.get("stats", {})}
    features = list(existing.get("features") or [])
    for feature in patch.get("features") or []:
        if feature not in features:
            features.append(feature)
    if features:
        merged["features"] = features
    files = set(existing.get("files") or [])
    files.update(patch.get("files") or [])
    merged["files"] = sorted(files)
    return merged


def emit_source_context(
    paths: RepoPaths,
    feature: str,
    *,
    force: bool = False,
    prefer_source_paths: list[str] | None = None,
) -> tuple[dict[str, Path], list[str]]:
    """Refresh cartridge/source-context.md and manifest stats without delta/pack sync."""
    validate_feature_id(feature)
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
    prefer_doc_ids: list[str] = []
    if prefer_source_paths:
        path_order = {path: index for index, path in enumerate(prefer_source_paths)}
        prefer_doc_ids = [
            doc.doc_id
            for doc in sorted(
                (doc for doc in doc_index.documents if doc.source_path in path_order),
                key=lambda doc: path_order[doc.source_path],
            )
        ]
        selected = merge_preferred_chunks(selected, chunk_index.chunks, prefer_doc_ids)
        _warn_unembedded_preferred_docs(
            warnings,
            prefer_doc_ids=prefer_doc_ids,
            doc_index=doc_index,
            chunk_index=chunk_index,
            embed_index=embed_index,
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

    created_at = datetime.now(timezone.utc).isoformat()
    manifest_patch = {
        "schema_version": "cartridge.v1",
        "cartridge_id": f"ctx-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{feature}",
        "title": f"Cartridge context for {feature}",
        "created_at": created_at,
        "source": {"type": "context-library", "compiler": "hive_planner", "version": COMPILER_VERSION},
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
            "source_context_updated_at": created_at,
        },
    }

    lines = [
        "# Source Context",
        "",
        f"**Feature:** `{feature}`",
        f"**Generated:** {created_at}",
        f"**Limits:** max {MAX_SOURCE_DOCUMENTS} documents, max {MAX_SOURCE_EXCERPTS} excerpts",
        "",
        "## Active documents",
    ]
    doc_ids = {c.doc_id for c in selected}
    listed_docs: list = []
    seen_doc_ids: set[str] = set()
    for doc_id in prefer_doc_ids:
        doc = next((d for d in doc_index.documents if d.doc_id == doc_id), None)
        if doc and doc.doc_id in doc_ids and doc.doc_id not in seen_doc_ids:
            listed_docs.append(doc)
            seen_doc_ids.add(doc.doc_id)
    for doc in doc_index.documents:
        if doc.doc_id in doc_ids and doc.doc_id not in seen_doc_ids:
            listed_docs.append(doc)
            seen_doc_ids.add(doc.doc_id)
    for doc in listed_docs:
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

    from hive_planner.delta_emit import _auto_sync_banner, _should_skip_existing

    source_context_path = paths.cartridge / "source-context.md"
    context_body = "\n".join(lines) + "\n"
    skip_context, context_reason = _should_skip_existing(source_context_path, force=force)
    if skip_context:
        warnings.append(f"Skipped cartridge/source-context.md ({context_reason})")
        outputs: dict[str, Path] = (
            {"source_context": source_context_path} if source_context_path.exists() else {}
        )
        return outputs, warnings

    banner = _auto_sync_banner(paths.chunk_index, paths)
    source_context_path.write_text(f"{banner}\n\n{context_body}", encoding="utf-8")
    outputs = {"source_context": source_context_path}

    rel_files = [path.relative_to(paths.root).as_posix() for path in outputs.values()]
    rel_files.append("cartridge/manifest.json")
    manifest_patch["files"] = sorted(set(rel_files))
    manifest = _merge_source_context_manifest(_load_cartridge_manifest(paths), manifest_patch)
    manifest_path = paths.cartridge / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    outputs["manifest"] = manifest_path
    return outputs, warnings


def emit_cartridge(
    paths: RepoPaths,
    feature: str,
    *,
    force_delta: bool = False,
    emit_rules_seeds: bool = False,
    prefer_source_paths: list[str] | None = None,
) -> tuple[dict[str, Path], list[str]]:
    validate_feature_id(feature)
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
    prefer_doc_ids: list[str] = []
    if prefer_source_paths:
        path_order = {path: index for index, path in enumerate(prefer_source_paths)}
        prefer_doc_ids = [
            doc.doc_id
            for doc in sorted(
                (doc for doc in doc_index.documents if doc.source_path in path_order),
                key=lambda doc: path_order[doc.source_path],
            )
        ]
        selected = merge_preferred_chunks(selected, chunk_index.chunks, prefer_doc_ids)
        _warn_unembedded_preferred_docs(
            warnings,
            prefer_doc_ids=prefer_doc_ids,
            doc_index=doc_index,
            chunk_index=chunk_index,
            embed_index=embed_index,
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
        "targets": {
            "delta_docs": True,
            "spec_kit": True,
            "cursor_rules": "disabled",
            "agents_md": False,
        },
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

    from hive_planner.delta_emit import _auto_sync_banner, _should_skip_existing, sync_delta_cartridge

    delta_results, delta_paths, delta_warnings = sync_delta_cartridge(paths, feature, force=force_delta)
    warnings.extend(delta_warnings)

    from hive_planner.cartridge_pack import emit_cartridge_pack, validate_pack_completeness

    pack_paths, pack_results, pack_warnings = emit_cartridge_pack(
        paths,
        feature,
        force=force_delta,
        emit_rules_seeds=emit_rules_seeds,
    )
    warnings.extend(pack_warnings)

    manifest["stats"]["delta_sync"] = delta_results
    manifest["stats"]["pack_sync"] = pack_results
    if emit_rules_seeds and pack_results.get("rules_seed") in {"written", "updated"}:
        manifest["targets"]["cursor_rules"] = "seed"

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
    listed_docs: list = []
    seen_doc_ids: set[str] = set()
    for doc_id in prefer_doc_ids:
        doc = next((d for d in doc_index.documents if d.doc_id == doc_id), None)
        if doc and doc.doc_id in doc_ids and doc.doc_id not in seen_doc_ids:
            listed_docs.append(doc)
            seen_doc_ids.add(doc.doc_id)
    for doc in doc_index.documents:
        if doc.doc_id in doc_ids and doc.doc_id not in seen_doc_ids:
            listed_docs.append(doc)
            seen_doc_ids.add(doc.doc_id)
    for doc in listed_docs:
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
    context_body = "\n".join(lines) + "\n"
    skip_context, context_reason = _should_skip_existing(source_context_path, force=force_delta)
    if skip_context:
        warnings.append(f"Skipped cartridge/source-context.md ({context_reason})")
        if source_context_path.exists():
            outputs: dict[str, Path] = {"source_context": source_context_path}
        else:
            outputs = {}
    else:
        banner = _auto_sync_banner(paths.chunk_index, paths)
        source_context_path.write_text(f"{banner}\n\n{context_body}", encoding="utf-8")
        outputs = {"source_context": source_context_path}
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
