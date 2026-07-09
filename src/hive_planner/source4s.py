"""Source4s — upload txt/pdf reference files for cartridge-linked agent retrieval."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.config import RepoPaths, validate_feature_id
from hive_planner.discovery import doc_id_for_path
from hive_planner.format_deps import (
    ingest_pdf_dependency_warnings,
    pdf_support_available,
    pdf_support_message,
)
from hive_planner.emitter import emit_source_context
from hive_planner.indexer import load_document_index
from hive_planner.ocr_runtime import ocr_pdf_enabled
from hive_planner.pipeline import ingest

SOURCE4S_DIR_NAME = "source4s"
SOURCE4S_EXTENSIONS = {".txt", ".pdf"}


def _combine_errors(*parts: str | None) -> str | None:
    messages: list[str] = []
    for part in parts:
        if not part:
            continue
        if part not in messages:
            messages.append(part)
    if not messages:
        return None
    combined = messages[0]
    for msg in messages[1:]:
        if msg not in combined:
            combined = f"{combined} Also: {msg}"
    return combined


def pdf_ocr_quality_warnings(warnings: list[str]) -> list[str]:
    """Warnings from indexed PDFs with OCR quality issues (unresolved, skipped, or disabled)."""
    return [
        w
        for w in warnings
        if w.startswith("PDF ") and ("OCR" in w or "Tesseract" in w)
    ]


def _unique_source_files(source_files: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in source_files:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _selection_error_message(
    source_files: list[Path], copied: list[str], stage_warnings: list[str]
) -> str | None:
    if len(copied) >= len(source_files):
        return None
    if not any("Load Sources accepts .txt and .pdf only" in w for w in stage_warnings):
        return None
    return (
        f"Only {len(copied)} of {len(source_files)} selected file(s) were staged — "
        "Load Sources accepts .txt and .pdf only."
    )


def _pdf_index_failure_hint(*, ocr_pdf: bool, pdf_failures: list[str]) -> str:
    if not pdf_failures:
        return "see warnings"
    if not pdf_support_available():
        return pdf_support_message()
    ocr_hint = " or Tesseract OCR" if ocr_pdf else ""
    from hive_planner.runtime_paths import is_portable_runtime

    if pdf_failures and is_portable_runtime():
        return (
            "see warnings (PDF may be corrupt, password-protected, or image-only needing"
            f"{ocr_hint})"
        )
    return f"see warnings (PDF may require pip install -e '.[pdf]'{ocr_hint})"


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


def source4s_needs_pdf_support(paths: RepoPaths, source_files: list[Path]) -> bool:
    """True when ingest will touch any PDF under context-library/sources."""
    if any(path.suffix.lower() == ".pdf" for path in source_files):
        return True
    sources_root = paths.sources
    if not sources_root.is_dir():
        return False
    return any(
        path.suffix.lower() == ".pdf" for path in sources_root.rglob("*") if path.is_file()
    )


def stage_source4s_files(paths: RepoPaths, source_files: list[Path]) -> tuple[list[str], list[str]]:
    """Copy uploaded txt/pdf files into context-library/sources/source4s/."""
    dest_dir = source4s_dir(paths)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest_dir.resolve()
    copied: list[str] = []
    warnings: list[str] = []
    seen_sources: set[Path] = set()
    for raw in source_files:
        src = raw.resolve()
        if src in seen_sources:
            continue
        seen_sources.add(src)
        if not src.is_file():
            warnings.append(f"Skipped (not a file): {src}")
            continue
        suffix = src.suffix.lower()
        if suffix not in SOURCE4S_EXTENSIONS:
            warnings.append(f"Skipped (Load Sources accepts .txt and .pdf only): {src.name}")
            continue
        try:
            rel_under_dest = src.relative_to(dest_resolved)
        except ValueError:
            rel_under_dest = None
        if rel_under_dest is not None:
            rel = (dest_dir / rel_under_dest).relative_to(paths.root).as_posix()
            if rel not in copied:
                copied.append(rel)
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
        disabled = meta.get("ocr_disabled_pages") or []
        if unresolved:
            warnings.append(
                f"PDF {rel}: OCR left {len(unresolved)} page(s) unresolved: {unresolved}"
            )
        if skipped:
            warnings.append(
                f"PDF {rel}: Tesseract unavailable — {len(skipped)} image page(s) not OCR'd: {skipped}"
            )
        if disabled:
            warnings.append(
                f"PDF {rel}: OCR disabled — {len(disabled)} image page(s) not OCR'd: {disabled}"
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

    source_files = _unique_source_files(source_files)

    if source4s_needs_pdf_support(paths, source_files) and not pdf_support_available():
        result.ok = False
        result.error = pdf_support_message()
        return result

    paths.ensure_dirs()
    copied, stage_warnings = stage_source4s_files(paths, source_files)
    result.copied = copied
    result.warnings.extend(stage_warnings)
    if not copied:
        result.ok = False
        if stage_warnings:
            result.error = "; ".join(stage_warnings)
        else:
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
    pdf_dep_error: str | None = None
    if ingest_pdf_dependency_warnings(ingest_report.warnings):
        pdf_dep_error = (
            "Ingest skipped one or more PDF(s) because PDF support is unavailable."
        )

    selection_error: str | None = _selection_error_message(source_files, copied, stage_warnings)

    indexed_paths = {doc.source_path for doc in load_document_index(paths.document_index).documents}
    indexed_copied = [rel for rel in copied if rel in indexed_paths]
    not_indexed = [rel for rel in copied if rel not in indexed_paths]
    result.indexed_staged = len(indexed_copied)
    result.warnings.extend(staged_pdf_ocr_warnings(paths, indexed_copied))
    index_error: str | None = None
    if not_indexed:
        pdf_failures = [rel for rel in not_indexed if rel.lower().endswith(".pdf")]
        index_hint = _pdf_index_failure_hint(ocr_pdf=ocr_pdf, pdf_failures=pdf_failures)
        index_error = (
            f"{len(not_indexed)} of {len(copied)} staged file(s) could not be indexed: "
            + ", ".join(not_indexed)
            + f" — {index_hint}."
        )
        if not indexed_copied:
            result.ok = False
            result.error = _combine_errors(pdf_dep_error, index_error, selection_error)
            return result

    if not update_cartridge:
        final_error = _combine_errors(pdf_dep_error, index_error, selection_error)
        if final_error:
            result.ok = False
            result.error = final_error
        return result

    if not feature or not feature.strip():
        result.ok = False
        result.error = _combine_errors(
            "Feature id is required to update cartridge source-context.md.",
            pdf_dep_error,
            index_error,
            selection_error,
        )
        return result

    try:
        validate_feature_id(feature.strip())
    except ValueError as exc:
        result.ok = False
        result.error = _combine_errors(str(exc), pdf_dep_error, index_error, selection_error)
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
        result.error = _combine_errors(str(exc), pdf_dep_error, index_error, selection_error)
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
    context_error: str | None = None
    if skipped_context:
        context_error = (
            "Cartridge source-context was not updated — remove draft/manual banner or use force."
        )
        result.source_context_path = None
        result.cartridge_outputs.pop("source_context", None)
    final_error = _combine_errors(context_error, pdf_dep_error, index_error, selection_error)
    if final_error:
        result.ok = False
        result.error = final_error
    return result
