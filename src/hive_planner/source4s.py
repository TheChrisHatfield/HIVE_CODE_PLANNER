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
SOURCE4S_FILETYPES = [
    ("Text and PDF", "*.txt *.pdf"),
    ("Text", "*.txt"),
    ("PDF", "*.pdf"),
    ("All files", "*.*"),
]
SOURCE4S_DISCOVER_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "node_modules",
    "__pycache__",
    "venv",
    "dist",
    "build",
    ".hive",
    ".cursor",
    "context-library",
    "cartridge",
    "tests",
    "vendor",
}


def discover_source4s_files_in_folder(folder: Path, *, recursive: bool = True) -> list[Path]:
    """Return .txt/.pdf files under a folder (recursive by default)."""
    root = folder.resolve()
    if not root.is_dir():
        return []
    found: list[Path] = []

    def scan_dir(current: Path) -> None:
        if current != root and current.name in SOURCE4S_DISCOVER_SKIP_DIR_NAMES:
            return
        try:
            entries = sorted(current.iterdir())
        except OSError:
            return
        for path in entries:
            if path.is_dir():
                if recursive:
                    scan_dir(path)
                continue
            if path.suffix.lower() not in SOURCE4S_EXTENSIONS:
                continue
            found.append(path)

    scan_dir(root)
    return found


def merge_source4s_selection(existing: list[Path], added: list[Path]) -> list[Path]:
    """Append source paths while deduplicating by resolved path."""
    merged = _unique_source_files([*existing, *added])
    added_dirs = [path.resolve() for path in added if path.is_dir()]
    if not added_dirs:
        return merged
    trimmed: list[Path] = []
    for path in merged:
        if path.is_dir():
            trimmed.append(path)
            continue
        resolved = path.resolve()
        if any(_path_is_under(resolved, root) for root in added_dirs):
            continue
        trimmed.append(path)
    return _unique_source_files(trimmed)


def _path_is_under(path: Path, root: Path) -> bool:
    try:
        return path.is_relative_to(root)
    except ValueError:
        return False


def expand_source4s_inputs(source_files: list[Path]) -> list[Path]:
    """Expand folder paths to supported files; keep files and missing paths as-is."""
    expanded: list[Path] = []
    for path in source_files:
        if path.is_dir():
            expanded.extend(discover_source4s_files_in_folder(path))
        else:
            expanded.append(path)
    return _unique_source_files(expanded)


def source4s_selection_error(source_files: list[Path]) -> str | None:
    """Return a user-facing error when nothing in the selection can be staged."""
    if not source_files:
        return "Choose at least one .txt or .pdf file."
    expanded = expand_source4s_inputs(source_files)
    if any(
        path.is_file() and path.suffix.lower() in SOURCE4S_EXTENSIONS for path in expanded
    ):
        return None
    dirs = [path for path in source_files if path.is_dir()]
    missing = [path for path in source_files if not path.is_file() and not path.is_dir()]
    unsupported = [
        path
        for path in source_files
        if path.is_file() and path.suffix.lower() not in SOURCE4S_EXTENSIONS
    ]
    if dirs and not missing and not unsupported:
        return "No .txt or .pdf files found in the selected folder(s)."
    parts: list[str] = []
    if missing:
        parts.append(f"{len(missing)} selected file(s) no longer exist")
    if unsupported:
        sample = ", ".join(path.name for path in unsupported[:3])
        if len(unsupported) > 3:
            sample = f"{sample} (+{len(unsupported) - 3} more)"
        parts.append(f"unsupported type(s): {sample}")
    return (
        f"{'; '.join(parts)}. Load Sources accepts .txt and .pdf only."
        if parts
        else "Load Sources accepts .txt and .pdf only."
    )


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


def _staging_shortfall_error(
    source_files: list[Path], copied: list[str], stage_warnings: list[str]
) -> str | None:
    if any("Load Sources accepts .txt and .pdf only" in w for w in stage_warnings):
        if len(copied) < len(source_files):
            return (
                f"Only {len(copied)} of {len(source_files)} selected file(s) were staged — "
                "Load Sources accepts .txt and .pdf only."
            )
        return None
    stageable = [
        path
        for path in source_files
        if path.is_file() and path.suffix.lower() in SOURCE4S_EXTENSIONS
    ]
    if not stageable or len(copied) >= len(stageable):
        return None
    if any("duplicate basename" in w for w in stage_warnings):
        return (
            f"Only {len(copied)} of {len(stageable)} stageable file(s) were staged — "
            "duplicate filenames collide when copied to source4s/ (see warnings)."
        )
    return None


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
    for path in source_files:
        if path.is_dir():
            if any(
                item.suffix.lower() == ".pdf"
                for item in discover_source4s_files_in_folder(path)
            ):
                return True
        elif path.suffix.lower() == ".pdf":
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
    staged_from: dict[str, Path] = {}
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
        rel = dest.relative_to(paths.root).as_posix()
        prev = staged_from.get(rel)
        if prev is not None and prev != src:
            warnings.append(
                f"Replaced staged {dest.name} — kept upload from {src} "
                f"(skipped duplicate basename from {prev})"
            )
        shutil.copy2(src, dest)
        staged_from[rel] = src
        if rel not in copied:
            copied.append(rel)
    return copied, warnings


def staged_pdf_ocr_warnings(paths: RepoPaths, copied: list[str]) -> list[str]:
    """Surface OCR quality issues recorded during PDF normalization."""
    warnings: list[str] = []
    indexed = {
        doc.source_path: doc for doc in load_document_index(paths.document_index).documents
    }
    for rel in copied:
        if not rel.lower().endswith(".pdf"):
            continue
        doc = indexed.get(rel)
        if doc is None:
            continue
        meta_path = paths.normalized_meta / f"{doc_id_for_path(rel)}.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meta_hash = meta.get("content_hash")
        if not meta_hash or meta_hash != doc.content_hash:
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

    had_directories = any(path.is_dir() for path in source_files)
    source_files = expand_source4s_inputs(source_files)
    if not source_files:
        result.ok = False
        result.error = (
            "No .txt or .pdf files found in the selected folder(s)."
            if had_directories
            else "Choose at least one .txt or .pdf file."
        )
        return result

    selection_problem = source4s_selection_error(source_files)
    if selection_problem:
        result.ok = False
        result.error = selection_problem
        return result

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
            pdf_support_message()
            if not pdf_support_available()
            else "Ingest skipped one or more PDF(s) — see warnings."
        )

    selection_error: str | None = _staging_shortfall_error(source_files, copied, stage_warnings)

    indexed_paths = {doc.source_path for doc in load_document_index(paths.document_index).documents}
    indexed_copied = [rel for rel in copied if rel in indexed_paths]
    not_indexed = [rel for rel in copied if rel not in indexed_paths]
    result.indexed_staged = len(indexed_copied)
    ocr_staged_warnings = staged_pdf_ocr_warnings(paths, indexed_copied)
    result.warnings.extend(ocr_staged_warnings)
    ocr_quality_error: str | None = None
    if ocr_staged_warnings:
        ocr_quality_error = (
            "One or more staged PDF(s) have OCR quality issues — see warnings."
        )
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
            result.error = _combine_errors(
                pdf_dep_error, ocr_quality_error, index_error, selection_error
            )
            return result

    if not update_cartridge:
        final_error = _combine_errors(
            pdf_dep_error, ocr_quality_error, index_error, selection_error
        )
        if final_error:
            result.ok = False
            result.error = final_error
        return result

    if ocr_quality_error:
        result.ok = False
        result.error = _combine_errors(
            ocr_quality_error, pdf_dep_error, index_error, selection_error
        )
        return result

    if not feature or not feature.strip():
        result.ok = False
        result.error = _combine_errors(
            "Feature id is required to update cartridge source-context.md.",
            pdf_dep_error,
            ocr_quality_error,
            index_error,
            selection_error,
        )
        return result

    try:
        validate_feature_id(feature.strip())
    except ValueError as exc:
        result.ok = False
        result.error = _combine_errors(
            str(exc), pdf_dep_error, ocr_quality_error, index_error, selection_error
        )
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
        result.error = _combine_errors(
            str(exc), pdf_dep_error, ocr_quality_error, index_error, selection_error
        )
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
    final_error = _combine_errors(
        context_error, pdf_dep_error, ocr_quality_error, index_error, selection_error
    )
    if final_error:
        result.ok = False
        result.error = final_error
    return result
