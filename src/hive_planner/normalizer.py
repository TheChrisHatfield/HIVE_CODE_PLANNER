from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from hive_planner.config import RepoPaths
from hive_planner.discovery import content_hash, doc_id_for_path, infer_category, relative_source_path
from hive_planner.models import NormalizeResult, SourceDocument
from hive_planner.normalizers import EmptySourceError, MissingDependencyError, NormalizationError
from hive_planner.normalizers.csv import normalize_csv
from hive_planner.normalizers.docx import normalize_docx
from hive_planner.normalizers.html import normalize_html
from hive_planner.normalizers.pdf import normalize_pdf
from hive_planner.normalizers.pptx import normalize_pptx
from hive_planner.normalizers.text import normalize_text


def read_source_text(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="replace")


def _dispatch_normalize(file_path: Path) -> NormalizeResult:
    fmt = file_path.suffix.lower().lstrip(".")
    if fmt in ("md", "txt"):
        return normalize_text(file_path)
    if fmt == "pdf":
        return normalize_pdf(file_path)
    if fmt == "docx":
        return normalize_docx(file_path)
    if fmt in ("html", "htm"):
        return normalize_html(file_path)
    if fmt == "csv":
        return normalize_csv(file_path)
    if fmt == "pptx":
        return normalize_pptx(file_path)
    raise NormalizationError(f"Unsupported format: {fmt}")


def normalize_document(paths: RepoPaths, file_path: Path) -> tuple[SourceDocument, str, str]:
    rel = relative_source_path(paths, file_path)
    doc_id = doc_id_for_path(rel)
    fmt = file_path.suffix.lower().lstrip(".")
    result = _dispatch_normalize(file_path)

    doc = SourceDocument(
        doc_id=doc_id,
        source_path=rel,
        format=fmt,
        title=result.title,
        content_hash=content_hash(result.raw_text),
        category=infer_category(file_path.relative_to(paths.sources).as_posix()),
    )

    paths.normalized_md.mkdir(parents=True, exist_ok=True)
    paths.normalized_meta.mkdir(parents=True, exist_ok=True)

    normalized_path = paths.normalized_md / f"{doc_id}.md"
    normalized_path.write_text(result.normalized_body, encoding="utf-8")

    metadata = {
        "doc_id": doc_id,
        "source_path": rel,
        "normalized_path": f"context-library/normalized/markdown/{doc_id}.md",
        "document_type": doc.category,
        "format": fmt,
        "title": result.title,
        "last_updated": date.today().isoformat(),
        "trust_level": "high",
        "content_hash": doc.content_hash,
    }
    metadata.update(result.extra_metadata)

    meta_path = paths.normalized_meta / f"{doc_id}.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return doc, result.normalized_body, result.raw_text
