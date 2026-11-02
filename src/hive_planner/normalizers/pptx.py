from __future__ import annotations

from pathlib import Path

from hive_planner.models import NormalizeResult
from hive_planner.normalizers import EmptySourceError, MissingDependencyError


def _shape_texts(shape) -> list[str]:
    """Text on a shape. A group has no text of its own; its members do."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        parts: list[str] = []
        for child in shape.shapes:
            parts.extend(_shape_texts(child))
        return parts
    if not hasattr(shape, "text"):
        return []
    text = shape.text.strip()
    return [text] if text else []


def _slide_text(slide) -> str:
    parts: list[str] = []
    title = ""
    if slide.shapes.title and slide.shapes.title.text:
        title = slide.shapes.title.text.strip()
        if title:
            parts.append(title)
    for shape in slide.shapes:
        for text in _shape_texts(shape):
            if title and text == title:
                continue
            parts.append(text)
    return "\n".join(parts).strip()


def normalize_pptx(file_path: Path) -> NormalizeResult:
    try:
        from pptx import Presentation
    except ImportError as exc:
        raise MissingDependencyError(
            "PPTX support requires python-pptx: pip install -e '.[pptx]'"
        ) from exc

    title = file_path.stem.replace("-", " ").title()
    try:
        presentation = Presentation(file_path)
    except Exception as exc:
        raise EmptySourceError(f"Could not open PPTX: {exc}") from exc

    lines: list[str] = [f"# {title}", ""]
    raw_parts: list[str] = []
    slide_num = 0

    for slide in presentation.slides:
        slide_num += 1
        text = _slide_text(slide)
        if not text:
            continue
        lines.extend([f"## Slide {slide_num}", "", text, ""])
        raw_parts.append(text)

    if not raw_parts:
        raise EmptySourceError("PPTX has no extractable text")

    normalized_body = "\n".join(lines).strip() + "\n"
    return NormalizeResult(
        normalized_body=normalized_body,
        raw_text="\n\n".join(raw_parts),
        title=title,
        extra_metadata={"format": "pptx", "slide_count": slide_num},
    )
