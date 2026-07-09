from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.format_deps import pdf_support_available, pdf_support_message
from hive_planner.source4s import SOURCE4S_DIR_NAME, run_source4s, source4s_needs_pdf_support


def test_pdf_support_available_when_fitz_installed() -> None:
    pytest.importorskip("fitz")
    assert pdf_support_available() is True


def test_pdf_support_message_for_dev_install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HIVE_PLANNER_PORTABLE", raising=False)
    monkeypatch.setattr("hive_planner.runtime_paths.is_frozen", lambda: False)
    assert "pip install" in pdf_support_message()


def test_pdf_support_message_for_portable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HIVE_PLANNER_PORTABLE", "1")
    message = pdf_support_message()
    assert "build_portable" in message
    assert "pymupdf" in message


def test_run_source4s_fails_fast_when_pdf_selected_without_pymupdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.config import RepoPaths

    monkeypatch.setattr("hive_planner.source4s.pdf_support_available", lambda: False)
    monkeypatch.setattr(
        "hive_planner.source4s.pdf_support_message",
        lambda: "PDF support requires pymupdf: pip install -e \".[pdf]\"",
    )

    paths = RepoPaths(root=tmp_path)
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 stub")

    result = run_source4s(paths, [pdf], feature="example-feature")
    assert not result.ok
    assert result.error == "PDF support requires pymupdf: pip install -e \".[pdf]\""
    assert result.copied == []


def test_source4s_needs_pdf_support_when_library_has_pdf(tmp_path: Path) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    pdf = paths.sources / SOURCE4S_DIR_NAME / "existing.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 stub")
    txt = tmp_path / "notes.txt"
    txt.write_text("notes only", encoding="utf-8")

    assert source4s_needs_pdf_support(paths, [txt]) is True
    assert source4s_needs_pdf_support(paths, [txt.with_suffix(".md")]) is True


def test_run_source4s_fails_fast_when_library_has_pdf_without_pymupdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RepoPaths(root=tmp_path)
    paths.ensure_dirs()
    pdf = paths.sources / SOURCE4S_DIR_NAME / "existing.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 stub")
    txt = tmp_path / "notes.txt"
    txt.write_text("# Notes\n\nText-only upload.\n", encoding="utf-8")

    monkeypatch.setattr("hive_planner.source4s.pdf_support_available", lambda: False)
    monkeypatch.setattr(
        "hive_planner.source4s.pdf_support_message",
        lambda: "PDF support requires pymupdf: pip install -e \".[pdf]\"",
    )

    result = run_source4s(paths, [txt], feature="example-feature", update_cartridge=False)
    assert not result.ok
    assert result.error == "PDF support requires pymupdf: pip install -e \".[pdf]\""
    assert result.copied == []
