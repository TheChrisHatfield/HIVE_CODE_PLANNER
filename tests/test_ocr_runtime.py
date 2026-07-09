from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.ocr_runtime import (
    OcrRuntimeStatus,
    TesseractInstall,
    discover_tesseract,
    ensure_ocr_runtime,
    ocr_pdf_enabled,
    ocr_runtime_status,
)
from hive_planner.normalizers import EmptySourceError
from hive_planner.normalizers.pdf import normalize_pdf


def test_discover_tesseract_prefers_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root = tmp_path / "tess"
    tessdata = fake_root / "tessdata"
    tessdata.mkdir(parents=True)
    (tessdata / "eng.traineddata").write_bytes(b"x")
    exe = fake_root / "tesseract.exe"
    exe.write_bytes(b"stub")

    monkeypatch.setenv("HIVE_TESSERACT_EXE", str(exe))
    status = discover_tesseract(refresh=True)
    assert status.available
    assert status.install is not None
    assert status.install.exe == exe.resolve()
    assert status.install.source == "env:HIVE_TESSERACT_EXE"


def test_discover_tesseract_bundled_vendor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vendor = tmp_path / "vendor" / "tesseract"
    tessdata = vendor / "tessdata"
    tessdata.mkdir(parents=True)
    (tessdata / "eng.traineddata").write_bytes(b"x")
    exe = vendor / "tesseract.exe"
    exe.write_bytes(b"stub")

    monkeypatch.delenv("HIVE_TESSERACT_EXE", raising=False)
    monkeypatch.setenv("HIVE_PLANNER_APP_ROOT", str(tmp_path))
    status = discover_tesseract(refresh=True)
    assert status.available
    assert status.install is not None
    assert status.install.source == "portable:vendor/tesseract"


def test_normalize_pdf_rejects_zero_page_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fitz

    from hive_planner.normalizers import EmptySourceError

    class FakeDoc:
        needs_pass = False

        def __len__(self) -> int:
            return 0

        def close(self) -> None:
            return None

    monkeypatch.setattr(fitz, "open", lambda _path: FakeDoc())

    with pytest.raises(EmptySourceError, match="no pages"):
        normalize_pdf(tmp_path / "empty.pdf")


def test_normalize_pdf_ocr_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fitz")
    import fitz

    pdf_path = tmp_path / "scan.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    fake_install = TesseractInstall(
        exe=tmp_path / "tesseract.exe",
        tessdata_dir=tmp_path / "tessdata",
        source="test",
    )

    monkeypatch.setattr(
        "hive_planner.normalizers.pdf.ensure_ocr_runtime",
        lambda: type("S", (), {"available": True, "install": fake_install})(),
    )
    monkeypatch.setattr(
        "hive_planner.normalizers.pdf.ocr_pdf_pages",
        lambda *_a, **_k: [(1, "OCR mission text from scanned page")],
    )

    result = normalize_pdf(pdf_path)
    assert "OCR mission text" in result.normalized_body
    assert result.extra_metadata.get("extraction") == "ocr"


def test_normalize_pdf_mixed_embedded_and_ocr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fitz")
    import fitz

    pdf_path = tmp_path / "mixed.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Embedded page one text")
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    fake_install = TesseractInstall(
        exe=tmp_path / "tesseract.exe",
        tessdata_dir=tmp_path / "tessdata",
        source="test",
    )

    monkeypatch.setattr(
        "hive_planner.normalizers.pdf.ensure_ocr_runtime",
        lambda: type("S", (), {"available": True, "install": fake_install})(),
    )
    monkeypatch.setattr(
        "hive_planner.normalizers.pdf.ocr_pdf_pages",
        lambda *_a, **kwargs: [(2, "OCR text from scanned page two")],
    )

    result = normalize_pdf(pdf_path)
    assert "Embedded page one" in result.normalized_body
    assert "OCR text from scanned page two" in result.normalized_body
    assert result.extra_metadata.get("extraction") == "mixed"
    assert result.extra_metadata.get("page_count") == 2


def test_normalize_pdf_includes_placeholder_for_unresolved_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fitz")
    import fitz

    pdf_path = tmp_path / "mixed-gap.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Embedded page one text")
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    fake_install = TesseractInstall(
        exe=tmp_path / "tesseract.exe",
        tessdata_dir=tmp_path / "tessdata",
        source="test",
    )

    monkeypatch.setattr(
        "hive_planner.normalizers.pdf.ensure_ocr_runtime",
        lambda: type("S", (), {"available": True, "install": fake_install})(),
    )
    monkeypatch.setattr(
        "hive_planner.normalizers.pdf.ocr_pdf_pages",
        lambda *_a, **_k: [],
    )

    result = normalize_pdf(pdf_path)
    assert "## Page 1" in result.normalized_body
    assert "## Page 2" in result.normalized_body
    assert "No extractable text on this page" in result.normalized_body


def test_normalize_pdf_mixed_marks_unresolved_image_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fitz")
    import fitz

    pdf_path = tmp_path / "mixed-unresolved.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Embedded page one text")
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    fake_install = TesseractInstall(
        exe=tmp_path / "tesseract.exe",
        tessdata_dir=tmp_path / "tessdata",
        source="test",
    )

    monkeypatch.setattr(
        "hive_planner.normalizers.pdf.ensure_ocr_runtime",
        lambda: type("S", (), {"available": True, "install": fake_install})(),
    )
    monkeypatch.setattr(
        "hive_planner.normalizers.pdf.ocr_pdf_pages",
        lambda *_a, **_k: [],
    )

    result = normalize_pdf(pdf_path)
    assert "Embedded page one" in result.normalized_body
    assert result.extra_metadata.get("extraction") == "mixed"
    assert result.extra_metadata.get("ocr_unresolved_pages") == [2]
    assert "unresolved after OCR" in result.normalized_body


def test_normalize_pdf_warns_when_ocr_unavailable_on_mixed_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fitz")
    import fitz

    pdf_path = tmp_path / "mixed-no-tess.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Embedded page one text")
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    monkeypatch.setattr(
        "hive_planner.normalizers.pdf.ensure_ocr_runtime",
        lambda: type("S", (), {"available": False, "install": None})(),
    )

    result = normalize_pdf(pdf_path)
    assert "Embedded page one" in result.normalized_body
    assert "Tesseract unavailable" in result.normalized_body
    assert result.extra_metadata.get("ocr_skipped_pages") == [2]
    assert result.extra_metadata.get("extraction") == "text"


def test_normalize_pdf_mixed_without_ocr_keeps_text_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fitz")
    import fitz

    pdf_path = tmp_path / "mixed-no-ocr.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Embedded page one text")
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    token = ocr_pdf_enabled.set(False)
    try:
        result = normalize_pdf(pdf_path)
    finally:
        ocr_pdf_enabled.reset(token)

    assert result.extra_metadata.get("extraction") == "text"
    assert "ocr_unresolved_pages" not in result.extra_metadata
    assert "Embedded page one" in result.normalized_body


def test_normalize_pdf_skips_ocr_when_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fitz")
    import fitz

    pdf_path = tmp_path / "scan.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    token = ocr_pdf_enabled.set(False)
    try:
        with pytest.raises(EmptySourceError, match="OCR disabled"):
            normalize_pdf(pdf_path)
    finally:
        ocr_pdf_enabled.reset(token)


def test_scan_drive_skips_invalid_tesseract(tmp_path: Path) -> None:
    from hive_planner.ocr_runtime import _scan_drive_for_tesseract

    bad = tmp_path / "bad" / "Tesseract-OCR"
    bad.mkdir(parents=True)
    (bad / "tesseract.exe").write_bytes(b"stub")

    good = tmp_path / "good" / "Tesseract-OCR"
    tessdata = good / "tessdata"
    tessdata.mkdir(parents=True)
    (tessdata / "eng.traineddata").write_bytes(b"x")
    (good / "tesseract.exe").write_bytes(b"stub")

    found = _scan_drive_for_tesseract(tmp_path)
    assert found == (good / "tesseract.exe").resolve()


def test_ensure_ocr_runtime_refreshes_when_cached_install_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = TesseractInstall(
        exe=tmp_path / "tesseract.exe",
        tessdata_dir=tmp_path / "tessdata",
        source="test",
    )
    stale = OcrRuntimeStatus(True, install, [], "stale")
    refreshed = OcrRuntimeStatus(False, None, [], "missing")
    calls: list[bool] = []

    def fake_discover(*, scan_d_drive: bool | None = None, refresh: bool = False):
        calls.append(refresh)
        return stale if not refresh else refreshed

    monkeypatch.setattr("hive_planner.ocr_runtime.discover_tesseract", fake_discover)
    status = ensure_ocr_runtime()
    assert calls == [False, True]
    assert not status.available


def test_ensure_ocr_runtime_refreshes_when_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = TesseractInstall(
        exe=tmp_path / "tesseract.exe",
        tessdata_dir=tmp_path / "tessdata",
        source="test",
    )
    unavailable = OcrRuntimeStatus(False, None, [], "missing")
    available = OcrRuntimeStatus(True, install, [], "found")
    calls: list[bool] = []

    def fake_discover(*, scan_d_drive: bool | None = None, refresh: bool = False):
        calls.append(refresh)
        return unavailable if not refresh else available

    monkeypatch.setattr("hive_planner.ocr_runtime.discover_tesseract", fake_discover)
    status = ensure_ocr_runtime()
    assert calls == [False, True]
    assert status.available
    assert status.install is install


def test_ocr_pdf_pages_continues_after_page_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fitz")
    import fitz

    from hive_planner.ocr_runtime import TesseractInstall, ocr_pdf_pages

    pdf_path = tmp_path / "two-page.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    install = TesseractInstall(
        exe=tmp_path / "tesseract.exe",
        tessdata_dir=tmp_path / "tessdata",
        source="test",
    )

    def fake_tesseract(_install: TesseractInstall, png_path: Path, *, lang: str = "eng") -> str:
        if "page-2" in png_path.name:
            raise RuntimeError("simulated page 2 OCR failure")
        return "recovered page one text"

    monkeypatch.setattr("hive_planner.ocr_runtime._run_tesseract_on_png", fake_tesseract)
    pages = ocr_pdf_pages(pdf_path, install)
    assert pages == [(1, "recovered page one text")]


def test_pdf_needs_ocr_detects_mixed_and_image_only_pdfs(tmp_path: Path) -> None:
    pytest.importorskip("fitz")
    import fitz

    from hive_planner.ocr_runtime import pdf_needs_ocr

    image_only = tmp_path / "scan.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(image_only)
    doc.close()
    assert pdf_needs_ocr(image_only)

    mixed = tmp_path / "mixed.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "embedded text")
    doc.new_page()
    doc.save(mixed)
    doc.close()
    assert pdf_needs_ocr(mixed)

    text_only = tmp_path / "text.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "all pages have text")
    doc.save(text_only)
    doc.close()
    assert not pdf_needs_ocr(text_only)


def test_run_tesseract_on_png_tolerates_non_utf8_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.ocr_runtime import TesseractInstall, _run_tesseract_on_png

    install = TesseractInstall(
        exe=tmp_path / "tesseract.exe",
        tessdata_dir=tmp_path / "tessdata",
        source="test",
    )
    png_path = tmp_path / "page.png"
    png_path.write_bytes(b"png")

    class Completed:
        returncode = 0
        stdout = "caf\xe9 scan"
        stderr = ""

    monkeypatch.setattr("hive_planner.ocr_runtime.subprocess.run", lambda *a, **k: Completed())
    assert _run_tesseract_on_png(install, png_path) == "caf\xe9 scan"


def test_convert_pdf_to_markdown_rejects_password_protected_pdf(tmp_path: Path) -> None:
    pytest.importorskip("fitz")
    import fitz

    from hive_planner.ocr_runtime import TesseractInstall, convert_pdf_to_markdown

    pdf_path = tmp_path / "locked.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf_path, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="secret", user_pw="secret")
    doc.close()

    install = TesseractInstall(
        exe=tmp_path / "tesseract.exe",
        tessdata_dir=tmp_path / "tessdata",
        source="test",
    )

    with pytest.raises(RuntimeError, match="Password-protected"):
        convert_pdf_to_markdown(pdf_path, install=install)


def test_convert_pdf_to_markdown_warns_on_unresolved_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fitz")
    import fitz

    from hive_planner.ocr_runtime import TesseractInstall, convert_pdf_to_markdown

    pdf_path = tmp_path / "partial-ocr.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    install = TesseractInstall(
        exe=tmp_path / "tesseract.exe",
        tessdata_dir=tmp_path / "tessdata",
        source="test",
    )

    monkeypatch.setattr(
        "hive_planner.ocr_runtime.ocr_pdf_pages",
        lambda *_a, **_k: [(1, "only page one recovered")],
    )

    dest = convert_pdf_to_markdown(pdf_path, install=install)
    body = dest.read_text(encoding="utf-8")
    assert "only page one recovered" in body
    assert "produced no OCR text: 2" in body


def test_ocr_sidecar_basename_unique_per_path(tmp_path: Path) -> None:
    from hive_planner.ocr_runtime import ocr_sidecar_basename

    a = tmp_path / "batch" / "scan.pdf"
    b = tmp_path / "other" / "scan.pdf"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_bytes(b"%PDF-1.4\n")
    b.write_bytes(b"%PDF-1.4\n")

    name_a = ocr_sidecar_basename(a)
    name_b = ocr_sidecar_basename(b)
    assert name_a != name_b
    assert name_a.startswith("scan-")
    assert name_a.endswith(".ocr.md")


def test_ingest_skips_image_pdf_when_ocr_disabled(tmp_path: Path) -> None:
    pytest.importorskip("fitz")
    import fitz

    from hive_planner.config import RepoPaths
    from hive_planner.ocr_runtime import ocr_pdf_enabled
    from hive_planner.pipeline import ingest

    paths = RepoPaths(root=tmp_path)
    paths.sources.mkdir(parents=True)
    pdf = paths.sources / "scan.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf)
    doc.close()

    token = ocr_pdf_enabled.set(False)
    try:
        report = ingest(paths)
    finally:
        ocr_pdf_enabled.reset(token)

    assert report.skipped == 1
    assert any("OCR disabled" in w or "extractable" in w.lower() for w in report.warnings)


def test_ocr_runtime_status_to_dict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HIVE_TESSERACT_EXE", raising=False)
    status = ocr_runtime_status(refresh=True)
    payload = status.to_dict()
    assert "available" in payload
    assert "searched" in payload
