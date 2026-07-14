from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RepoPaths:
    root: Path

    @property
    def sources(self) -> Path:
        return self.root / "context-library" / "sources"

    @property
    def normalized_md(self) -> Path:
        return self.root / "context-library" / "normalized" / "markdown"

    @property
    def normalized_meta(self) -> Path:
        return self.root / "context-library" / "normalized" / "metadata"

    @property
    def indexes(self) -> Path:
        return self.root / "context-library" / "indexes"

    @property
    def document_index(self) -> Path:
        return self.indexes / "document-index.json"

    @property
    def chunk_index(self) -> Path:
        return self.indexes / "chunk-index.json"

    @property
    def embedding_index(self) -> Path:
        return self.indexes / "embedding-index.json"

    @property
    def cartridge(self) -> Path:
        return self.root / "cartridge"

    @property
    def hive_dir(self) -> Path:
        return self.root / ".hive"

    @property
    def shared_memory(self) -> Path:
        return self.hive_dir / "shared-memory"

    @property
    def shared_memory_staging(self) -> Path:
        return self.shared_memory / "staging"

    @property
    def shared_memory_permanent(self) -> Path:
        return self.shared_memory / "permanent"

    @property
    def shared_memory_manifest(self) -> Path:
        return self.shared_memory / "manifest.json"

    def ensure_dirs(self) -> None:
        for path in (
            self.sources,
            self.normalized_md,
            self.normalized_meta,
            self.indexes,
            self.cartridge,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def ensure_shared_memory_dirs(self) -> None:
        self.shared_memory_staging.mkdir(parents=True, exist_ok=True)
        self.shared_memory_permanent.mkdir(parents=True, exist_ok=True)


SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".docx", ".html", ".htm", ".csv", ".pptx"}

FEATURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def validate_feature_id(feature: str) -> str:
    if not FEATURE_ID_RE.match(feature):
        raise ValueError(
            f"Invalid feature id '{feature}' — use lowercase letters, digits, and hyphens only"
        )
    return feature


def resolve_repo_file_path(paths: RepoPaths, file_path: Path) -> Path:
    target = file_path if file_path.is_absolute() else paths.root / file_path
    resolved = target.resolve()
    try:
        resolved.relative_to(paths.root.resolve())
    except ValueError as exc:
        raise ValueError(f"Path must be inside repo root: {file_path}") from exc
    return resolved


def resolve_repo_agents_path(paths: RepoPaths, agents_path: Path | None) -> Path:
    target = agents_path if agents_path else paths.root / "AGENTS.md"
    if not target.is_absolute():
        target = paths.root / target
    resolved = target.resolve()
    try:
        resolved.relative_to(paths.root.resolve())
    except ValueError as exc:
        raise ValueError(f"AGENTS.md path must be inside repo root: {agents_path}") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"AGENTS.md not found: {resolved}")
    return resolved


def resolve_root(root: Path | None) -> tuple[Path, bool]:
    """Return (repo_root, was_auto_detected)."""
    if root is not None:
        return root.resolve(), False
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "START_HERE.md").exists() and (candidate / "docs" / "planning-rosetta-stone.md").exists():
            return candidate, True
    return cwd, False


def is_repo_root(path: Path) -> bool:
    return (path / "START_HERE.md").exists() and (path / "docs" / "planning-rosetta-stone.md").exists()
