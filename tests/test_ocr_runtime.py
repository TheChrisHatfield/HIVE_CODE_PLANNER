from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.ocr_runtime import (
    TesseractInstall,
    discover_tesseract,
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
        "hive_planner.normalizers.pdf.ocr_runtime_status",
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
        "hive_planner.normalizers.pdf.ocr_runtime_status",
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


def test_ocr_runtime_status_to_dict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HIVE_TESSERACT_EXE", raising=False)
    status = ocr_runtime_status(refresh=True)
    payload = status.to_dict()
    assert "available" in payload
    assert "searched" in payload
