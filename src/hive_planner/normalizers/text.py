from __future__ import annotations

from pathlib import Path

from hive_planner.discovery import infer_title
from hive_planner.models import NormalizeResult


def normalize_text(file_path: Path) -> NormalizeResult:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    fmt = file_path.suffix.lower().lstrip(".")
    title = infer_title(text, file_path.stem.replace("-", " ").title())

    if fmt == "md":
        normalized_body = text
    else:
        normalized_body = f"# {title}\n\n```text\n{text}\n```\n"

    return NormalizeResult(normalized_body=normalized_body, raw_text=text, title=title)
