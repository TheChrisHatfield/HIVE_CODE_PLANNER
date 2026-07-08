from __future__ import annotations

from pathlib import Path

from hive_planner.models import NormalizeResult
from hive_planner.normalizers import EmptySourceError, MissingDependencyError
from hive_planner.ocr_runtime import ocr_pdf_enabled, ocr_pdf_pages, ocr_runtime_status


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

        extraction = "text"
        ocr_install = None
        if not pages_text and ocr_pdf_enabled.get():
            status = ocr_runtime_status()
            if status.available and status.install is not None:
                try:
                    pages_text = ocr_pdf_pages(file_path, status.install)
                    extraction = "ocr"
                    ocr_install = status.install
                except Exception as exc:
                    raise EmptySourceError(f"PDF OCR failed: {exc}") from exc

        if not pages_text:
            if ocr_pdf_enabled.get():
                raise EmptySourceError(
                    "PDF has no extractable text (image-only or empty). "
                    "Install Tesseract to D:\\Program Files\\Tesseract-OCR, bundle vendor/tesseract, "
                    "or set HIVE_TESSERACT_EXE."
                )
            raise EmptySourceError("PDF has no extractable text (image-only or empty); OCR disabled")

        lines = [f"# {title}", ""]
        if extraction == "ocr":
            lines.extend(["> Extracted via Tesseract OCR", ""])
        raw_parts: list[str] = []
        for page_num, text in pages_text:
            lines.extend([f"## Page {page_num}", "", text, ""])
            raw_parts.append(text)

        normalized_body = "\n".join(lines).strip() + "\n"
        raw_text = "\n\n".join(raw_parts)
        extra = {"page_count": len(pages_text), "format": "pdf", "extraction": extraction}
        if ocr_install is not None:
            extra["ocr_engine"] = ocr_install.source
        return NormalizeResult(
            normalized_body=normalized_body,
            raw_text=raw_text,
            title=title,
            extra_metadata=extra,
        )
    finally:
        doc.close()
