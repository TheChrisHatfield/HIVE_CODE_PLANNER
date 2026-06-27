from __future__ import annotations

from pathlib import Path

from hive_planner.models import NormalizeResult
from hive_planner.normalizers import EmptySourceError, MissingDependencyError


def normalize_pdf(file_path: Path) -> NormalizeResult:
    try:
        import fitz  # pymupdf
    except ImportError as exc:
        raise MissingDependencyError(
            "PDF support requires pymupdf: pip install -e '.[pdf]'"
        ) from exc

    title = file_path.stem.replace("-", " ").title()
    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        raise EmptySourceError(f"Could not open PDF: {exc}") from exc

    try:
        if doc.needs_pass:
            raise EmptySourceError("Password-protected PDF is not supported")

        pages_text: list[tuple[int, str]] = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            if text:
                pages_text.append((page_num + 1, text))

        if not pages_text:
            raise EmptySourceError("PDF has no extractable text (image-only or empty)")

        lines = [f"# {title}", ""]
        raw_parts: list[str] = []
        for page_num, text in pages_text:
            lines.extend([f"## Page {page_num}", "", text, ""])
            raw_parts.append(text)

        normalized_body = "\n".join(lines).strip() + "\n"
        raw_text = "\n\n".join(raw_parts)
        return NormalizeResult(
            normalized_body=normalized_body,
            raw_text=raw_text,
            title=title,
            extra_metadata={"page_count": len(pages_text), "format": "pdf"},
        )
    finally:
        doc.close()
