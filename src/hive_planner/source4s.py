"""Source4s — upload txt/pdf reference files for cartridge-linked agent retrieval."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.config import RepoPaths, validate_feature_id
from hive_planner.emitter import emit_source_context
from hive_planner.indexer import load_document_index
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


def run_source4s(
    paths: RepoPaths,
    source_files: list[Path],
    *,
    feature: str | None = None,
    embed: bool = False,
    update_cartridge: bool = True,
    force_delta: bool = False,
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

    ingest_report = ingest(paths, embed=embed)
    result.processed = ingest_report.processed
    result.skipped = ingest_report.skipped
    result.pruned = ingest_report.pruned
    result.warnings.extend(ingest_report.warnings)

    indexed_paths = {doc.source_path for doc in load_document_index(paths.document_index).documents}
    indexed_copied = [rel for rel in copied if rel in indexed_paths]
    not_indexed = [rel for rel in copied if rel not in indexed_paths]
    result.indexed_staged = len(indexed_copied)
    if not_indexed:
        result.ok = False
        result.error = (
            f"{len(not_indexed)} of {len(copied)} staged file(s) could not be indexed: "
            + ", ".join(not_indexed)
            + " — see warnings (PDF may require pip install -e '.[pdf]')."
        )
        return result

    selection_error: str | None = None
    if len(copied) < len(source_files):
        selection_error = (
            f"Only {len(copied)} of {len(source_files)} selected file(s) were staged — "
            "Load Sources accepts .txt and .pdf only."
        )

    if not update_cartridge:
        if selection_error:
            result.ok = False
            result.error = selection_error
        return result

    if not feature or not feature.strip():
        result.warnings.append(
            "Cartridge link skipped — provide a feature id to refresh cartridge/source-context.md."
        )
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
            prefer_source_paths=copied,
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
    if selection_error:
        result.ok = False
        result.error = selection_error
    return result
