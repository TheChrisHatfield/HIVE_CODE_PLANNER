"""Source4s — upload txt/pdf reference files for cartridge-linked agent retrieval."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.config import RepoPaths, validate_feature_id
from hive_planner.discovery import doc_id_for_path
from hive_planner.emitter import emit_source_context
from hive_planner.indexer import load_document_index
from hive_planner.ocr_runtime import ocr_pdf_enabled
from hive_planner.pipeline import ingest

SOURCE4S_DIR_NAME = "source4s"
SOURCE4S_EXTENSIONS = {".txt", ".pdf"}


@dataclass
class Source4sResult:
    copied: list[str] = field(default_factory=list)
    processed: int = 0
    skipped: int = 0
    pruned: int = 0
    indexed_staged: int = 0
    feature: str | None = None
    cartridge_outputs: dict[str, str] = field(default_factory=dict)
    source_context_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    ok: bool = True
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "error": self.error,
            "copied": self.copied,
            "processed": self.processed,
            "skipped": self.skipped,
            "pruned": self.pruned,
            "indexed_staged": self.indexed_staged,
            "feature": self.feature,
            "cartridge_outputs": self.cartridge_outputs,
            "source_context_path": self.source_context_path,
            "warnings": self.warnings,
        }


def source4s_dir(paths: RepoPaths) -> Path:
    return paths.sources / SOURCE4S_DIR_NAME


def list_source4s_files(paths: RepoPaths) -> list[str]:
    root = source4s_dir(paths)
    if not root.is_dir():
        return []
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SOURCE4S_EXTENSIONS:
            found.append(path.relative_to(paths.root).as_posix())
    return found


def stage_source4s_files(paths: RepoPaths, source_files: list[Path]) -> tuple[list[str], list[str]]:
    """Copy uploaded txt/pdf files into context-library/sources/source4s/."""
    dest_dir = source4s_dir(paths)
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    warnings: list[str] = []
    for raw in source_files:
        src = raw.resolve()
        if not src.is_file():
            warnings.append(f"Skipped (not a file): {src}")
            continue
        suffix = src.suffix.lower()
        if suffix not in SOURCE4S_EXTENSIONS:
            warnings.append(f"Skipped (Load Sources accepts .txt and .pdf only): {src.name}")
            continue
        dest = dest_dir / src.name
        if dest.exists():
            stem = dest.stem
            counter = 2
            while dest.exists():
                dest = dest_dir / f"{stem}-{counter}{suffix}"
                counter += 1
        shutil.copy2(src, dest)
        copied.append(dest.relative_to(paths.root).as_posix())
    return copied, warnings


def staged_pdf_ocr_warnings(paths: RepoPaths, copied: list[str]) -> list[str]:
    """Surface OCR quality issues recorded during PDF normalization."""
    warnings: list[str] = []
    for rel in copied:
        if not rel.lower().endswith(".pdf"):
            continue
        meta_path = paths.normalized_meta / f"{doc_id_for_path(rel)}.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        unresolved = meta.get("ocr_unresolved_pages") or []
        skipped = meta.get("ocr_skipped_pages") or []
        if unresolved:
            warnings.append(
                f"PDF {rel}: OCR left {len(unresolved)} page(s) unresolved: {unresolved}"
            )
        if skipped:
            warnings.append(
                f"PDF {rel}: Tesseract unavailable — {len(skipped)} image page(s) not OCR'd: {skipped}"
            )
    return warnings


def run_source4s(
    paths: RepoPaths,
    source_files: list[Path],
    *,
    feature: str | None = None,
    embed: bool = False,
    update_cartridge: bool = True,
    force_delta: bool = False,
    ocr_pdf: bool = True,
) -> Source4sResult:
    """Stage txt/pdf uploads, ingest into context-library, optionally refresh cartridge source-context."""
    result = Source4sResult()
    if not source_files:
        result.ok = False
        result.error = "Choose at least one .txt or .pdf file."
        return result

    paths.ensure_dirs()
    copied, stage_warnings = stage_source4s_files(paths, source_files)
    result.copied = copied
    result.warnings.extend(stage_warnings)
    if not copied:
        result.ok = False
        result.error = "No supported files were staged (.txt and .pdf only)."
        return result

    token = ocr_pdf_enabled.set(ocr_pdf)
    try:
        ingest_report = ingest(paths, embed=embed)
    finally:
        ocr_pdf_enabled.reset(token)
    result.processed = ingest_report.processed
    result.skipped = ingest_report.skipped
    result.pruned = ingest_report.pruned
    result.warnings.extend(ingest_report.warnings)
    result.warnings.extend(staged_pdf_ocr_warnings(paths, copied))

    selection_error: str | None = None
    if len(copied) < len(source_files):
        selection_error = (
            f"Only {len(copied)} of {len(source_files)} selected file(s) were staged — "
            "Load Sources accepts .txt and .pdf only."
        )

    indexed_paths = {doc.source_path for doc in load_document_index(paths.document_index).documents}
    indexed_copied = [rel for rel in copied if rel in indexed_paths]
    not_indexed = [rel for rel in copied if rel not in indexed_paths]
    result.indexed_staged = len(indexed_copied)
    index_error: str | None = None
    if not_indexed:
        ocr_hint = " or Tesseract OCR" if ocr_pdf else ""
        index_error = (
            f"{len(not_indexed)} of {len(copied)} staged file(s) could not be indexed: "
            + ", ".join(not_indexed)
            + f" — see warnings (PDF may require pip install -e '.[pdf]'{ocr_hint})."
        )
        if not indexed_copied:
            result.ok = False
            result.error = index_error
            if selection_error:
                result.error = f"{index_error} Also: {selection_error}"
            return result

    if not update_cartridge:
        if index_error and selection_error:
            result.ok = False
            result.error = f"{index_error} Also: {selection_error}"
        elif selection_error:
            result.ok = False
            result.error = selection_error
        elif index_error:
            result.ok = False
            result.error = index_error
        return result

    if not feature or not feature.strip():
        result.ok = False
        result.error = "Feature id is required to update cartridge source-context.md."
        return result

    try:
        validate_feature_id(feature.strip())
    except ValueError as exc:
        result.ok = False
        result.error = str(exc)
        return result

    result.feature = feature.strip()
    try:
        outputs, emit_warnings = emit_source_context(
            paths,
            result.feature,
            force=force_delta,
            prefer_source_paths=indexed_copied,
        )
    except ValueError as exc:
        result.ok = False
        result.error = str(exc)
        return result

    result.warnings.extend(emit_warnings)
    result.cartridge_outputs = {
        name: path.relative_to(paths.root).as_posix() for name, path in outputs.items()
    }
    source_ctx = outputs.get("source_context")
    if source_ctx is not None:
        result.source_context_path = source_ctx.relative_to(paths.root).as_posix()
    skipped_context = any(
        w.startswith("Skipped cartridge/source-context.md") for w in emit_warnings
    )
    if skipped_context:
        result.ok = False
        result.error = (
            "Cartridge source-context was not updated — remove draft/manual banner or use force."
        )
        result.source_context_path = None
        result.cartridge_outputs.pop("source_context", None)
    if index_error:
        result.ok = False
        if result.error:
            if index_error not in result.error:
                result.error = f"{result.error} Also: {index_error}"
        else:
            result.error = index_error
    if selection_error:
        result.ok = False
        if result.error:
            if selection_error not in result.error:
                result.error = f"{result.error} Also: {selection_error}"
        else:
            result.error = selection_error
    return result
