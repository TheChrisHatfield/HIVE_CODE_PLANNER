from __future__ import annotations

from pathlib import Path

from hive_planner.models import NormalizeResult
from hive_planner.normalizers import EmptySourceError, MissingDependencyError
from hive_planner.ocr_runtime import ensure_ocr_runtime, ocr_pdf_enabled, ocr_pdf_pages


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

        page_count = len(doc)
        if page_count == 0:
            raise EmptySourceError("PDF has no pages")

        embedded: dict[int, str] = {}
        for page_num in range(page_count):
            text = doc[page_num].get_text("text").strip()
            if text:
                embedded[page_num + 1] = text

        extraction = "text"
        ocr_install = None
        ocr_attempted = False
        missing_indices = [i for i in range(page_count) if (i + 1) not in embedded]
        had_embedded_text = bool(embedded)

        if missing_indices and ocr_pdf_enabled.get():
            status = ensure_ocr_runtime()
            if status.available and status.install is not None:
                ocr_attempted = True
                try:
                    ocr_pages = ocr_pdf_pages(
                        file_path,
                        status.install,
                        page_indices=missing_indices,
                    )
                    if ocr_pages:
                        ocr_install = status.install
                        extraction = "mixed" if had_embedded_text else "ocr"
                        for page_num, text in ocr_pages:
                            embedded[page_num] = text
                except Exception as exc:
                    if not embedded:
                        raise EmptySourceError(f"PDF OCR failed: {exc}") from exc

        still_missing = [i + 1 for i in missing_indices if (i + 1) not in embedded]
        ocr_unavailable = bool(missing_indices) and ocr_pdf_enabled.get() and not ocr_attempted
        ocr_disabled_skips = bool(missing_indices) and not ocr_pdf_enabled.get() and still_missing
        if still_missing and had_embedded_text and extraction == "text" and ocr_attempted:
            extraction = "mixed"

        if not embedded:
            if ocr_pdf_enabled.get():
                raise EmptySourceError(
                    "PDF has no extractable text (image-only or empty). "
                    "Install Tesseract to D:\\Program Files\\Tesseract-OCR, bundle vendor/tesseract, "
                    "or set HIVE_TESSERACT_EXE."
                )
            raise EmptySourceError("PDF has no extractable text (image-only or empty); OCR disabled")

        lines = [f"# {title}", ""]
        if ocr_disabled_skips:
            skipped_label = ", ".join(str(n) for n in still_missing)
            lines.extend(
                [
                    f"> Warning: OCR disabled — {len(still_missing)} image page(s) not OCR'd: {skipped_label}",
                    "",
                ]
            )
        if ocr_unavailable and still_missing:
            skipped_label = ", ".join(str(n) for n in still_missing)
            lines.extend(
                [
                    f"> Warning: Tesseract unavailable — {len(still_missing)} image page(s) not OCR'd: {skipped_label}",
                    "",
                ]
            )
        if extraction == "ocr":
            lines.extend(["> Extracted via Tesseract OCR", ""])
        elif extraction == "mixed":
            banner = "> Mixed PDF: embedded text plus Tesseract OCR on image pages"
            if still_missing:
                banner += f" ({len(still_missing)} page(s) unresolved after OCR)"
            lines.extend([banner, ""])
        raw_parts: list[str] = []
        page_placeholder = "_(No extractable text on this page.)_"
        for page_num in range(1, page_count + 1):
            text = embedded.get(page_num)
            if text is None and page_num in still_missing:
                text = page_placeholder
            if text is None:
                continue
            lines.extend([f"## Page {page_num}", "", text, ""])
            raw_parts.append(text)

        normalized_body = "\n".join(lines).strip() + "\n"
        raw_text = "\n\n".join(raw_parts)
        extra = {"page_count": page_count, "format": "pdf", "extraction": extraction}
        if still_missing and ocr_attempted:
            extra["ocr_unresolved_pages"] = still_missing
        if still_missing and ocr_unavailable:
            extra["ocr_skipped_pages"] = still_missing
        if still_missing and ocr_disabled_skips:
            extra["ocr_disabled_pages"] = still_missing
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
