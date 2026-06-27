from __future__ import annotations

from pathlib import Path

from hive_planner.models import NormalizeResult
from hive_planner.normalizers import EmptySourceError, MissingDependencyError


def _heading_level(style_name: str | None) -> int | None:
    if not style_name:
        return None
    if style_name.startswith("Heading"):
        suffix = style_name.replace("Heading", "").strip()
        if suffix.isdigit():
            return int(suffix)
        if style_name == "Heading":
            return 1
    return None


def normalize_docx(file_path: Path) -> NormalizeResult:
    try:
        from docx import Document
    except ImportError as exc:
        raise MissingDependencyError(
            "DOCX support requires python-docx: pip install -e '.[docx]'"
        ) from exc

    title = file_path.stem.replace("-", " ").title()
    try:
        document = Document(file_path)
    except Exception as exc:
        raise EmptySourceError(f"Could not open DOCX: {exc}") from exc

    lines: list[str] = [f"# {title}", ""]
    raw_parts: list[str] = []
    has_heading = False

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        level = _heading_level(paragraph.style.name if paragraph.style else None)
        if level:
            has_heading = True
            lines.append(f"{'#' * min(level + 1, 6)} {text}")
        else:
            lines.append(text)
        lines.append("")
        raw_parts.append(text)

    if not raw_parts:
        raise EmptySourceError("DOCX has no extractable text")

    if not has_heading:
        body = "\n\n".join(raw_parts)
        normalized_body = f"# {title}\n\n{body}\n"
    else:
        normalized_body = "\n".join(lines).strip() + "\n"

    return NormalizeResult(
        normalized_body=normalized_body,
        raw_text="\n".join(raw_parts),
        title=title,
        extra_metadata={"format": "docx"},
    )
