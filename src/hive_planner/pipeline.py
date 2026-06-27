from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.chunker import chunk_markdown, chunk_plain_text
from hive_planner.config import RepoPaths
from hive_planner.discovery import discover_sources, doc_id_for_path, relative_source_path
from hive_planner.indexer import (
    load_chunk_index,
    load_document_index,
    prune_index,
    save_chunk_index,
    save_document_index,
    upsert_chunks,
    upsert_document,
)
from hive_planner.embeddings import (
    load_embedding_index,
    prune_embedding_index,
    save_embedding_index,
    sync_embedding_index,
)
from hive_planner.normalizer import normalize_document
from hive_planner.normalizers import EmptySourceError, MissingDependencyError, NormalizationError


@dataclass
class IngestReport:
    processed: int = 0
    skipped: int = 0
    pruned: int = 0
    warnings: list[str] = field(default_factory=list)


def _remove_normalized_artifacts(paths: RepoPaths, doc_id: str) -> None:
    for path in (
        paths.normalized_md / f"{doc_id}.md",
        paths.normalized_meta / f"{doc_id}.json",
    ):
        if path.exists():
            path.unlink()


def ingest(paths: RepoPaths, *, embed: bool = False) -> IngestReport:
    paths.ensure_dirs()
    report = IngestReport()
    sources = discover_sources(paths)
    doc_index = load_document_index(paths.document_index)
    chunk_index = load_chunk_index(paths.chunk_index)

    expected_doc_ids = {
        doc_id_for_path(relative_source_path(paths, file_path)) for file_path in sources
    }

    if not sources:
        report.warnings.append(f"No supported sources found under {paths.sources}")

    for file_path in sources:
        try:
            doc, normalized_body, raw_text = normalize_document(paths, file_path)
            if doc.format == "txt":
                chunks = chunk_plain_text(doc.doc_id, doc.title, raw_text)
            else:
                chunks = chunk_markdown(doc.doc_id, normalized_body)

            if not chunks:
                report.warnings.append(
                    f"No chunks produced for {relative_source_path(paths, file_path)} (empty or whitespace-only)"
                )

            upsert_document(doc_index, doc)
            upsert_chunks(chunk_index, doc.doc_id, chunks)
            report.processed += 1
        except (MissingDependencyError, EmptySourceError, NormalizationError) as exc:
            report.skipped += 1
            report.warnings.append(f"Skipped {file_path}: {exc}")
        except OSError as exc:
            report.skipped += 1
            report.warnings.append(f"Skipped {file_path}: {exc}")
        except Exception as exc:
            report.skipped += 1
            report.warnings.append(f"Skipped {file_path}: {type(exc).__name__}: {exc}")

    pruned_doc_ids = prune_index(doc_index, chunk_index, expected_doc_ids)
    for doc_id in pruned_doc_ids:
        _remove_normalized_artifacts(paths, doc_id)
    report.pruned = len(pruned_doc_ids)
    if pruned_doc_ids:
        report.warnings.append(f"Pruned {len(pruned_doc_ids)} stale indexed document(s)")

    save_document_index(paths.document_index, doc_index)
    save_chunk_index(paths.chunk_index, chunk_index)

    active_chunk_ids = {chunk.chunk_id for chunk in chunk_index.chunks}
    embed_index = load_embedding_index(paths.embedding_index)
    pruned_embed = prune_embedding_index(embed_index, active_chunk_ids)
    if pruned_embed:
        save_embedding_index(paths.embedding_index, embed_index)
        report.warnings.append(f"Pruned {pruned_embed} stale embedding row(s)")

    if embed:
        _, embed_warnings = sync_embedding_index(paths.embedding_index, chunk_index)
        report.warnings.extend(embed_warnings)

    return report


def status_summary(paths: RepoPaths) -> dict[str, int | bool]:
    doc_index = load_document_index(paths.document_index)
    chunk_index = load_chunk_index(paths.chunk_index)
    from hive_planner.embeddings import load_embedding_index

    embed_index = load_embedding_index(paths.embedding_index)
    return {
        "sources_dir_exists": paths.sources.exists(),
        "source_files_on_disk": len(discover_sources(paths)),
        "documents_indexed": len(doc_index.documents),
        "chunks_indexed": len(chunk_index.chunks),
        "embeddings_indexed": len(embed_index.embeddings),
        "cartridge_manifest_exists": (paths.cartridge / "manifest.json").exists(),
    }
