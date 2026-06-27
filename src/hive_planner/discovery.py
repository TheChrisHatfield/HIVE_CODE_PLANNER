from __future__ import annotations

import hashlib
import re
from pathlib import Path

from hive_planner.config import SUPPORTED_EXTENSIONS, RepoPaths


def doc_id_for_path(relative_path: str) -> str:
    digest = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()
    return digest[:16]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def infer_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return re.sub(r"^#+\s*", "", stripped).strip() or fallback
    return fallback


def infer_category(relative_path: str) -> str:
    parts = Path(relative_path).parts
    if len(parts) > 1:
        return parts[0]
    return "reference"


def discover_sources(paths: RepoPaths) -> list[Path]:
    if not paths.sources.exists():
        return []
    found: list[Path] = []
    for path in sorted(paths.sources.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            found.append(path)
    return found


def relative_source_path(paths: RepoPaths, file_path: Path) -> str:
    rel = file_path.relative_to(paths.sources).as_posix()
    return f"context-library/sources/{rel}"
