from pathlib import Path

from docx import Document

from hive_planner.normalizers.docx import normalize_docx


def test_docx_keeps_a_heading_and_table_cell(tmp_path: Path) -> None:
    path = tmp_path / "notes.docx"
    document = Document()
    document.add_heading("Section", level=1)
    document.add_paragraph("Intro line")
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Cell fact"
    document.save(path)

    result = normalize_docx(path)

    assert "## Section" in result.normalized_body
    assert "Intro line" in result.raw_text
    assert "Cell fact" in result.raw_text
    assert result.raw_text.index("Intro line") < result.raw_text.index("Cell fact")


def test_header_and_footer_text_is_indexed(tmp_path: Path) -> None:
    path = tmp_path / "header.docx"
    document = Document()
    document.add_paragraph("Body line")
    document.sections[0].header.paragraphs[0].text = "Running header"
    document.sections[0].footer.paragraphs[0].text = "Running footer"
    document.save(path)

    result = normalize_docx(path)

    assert "Body line" in result.raw_text
    assert "Running header" in result.raw_text
    assert "Running footer" in result.raw_text
    assert result.raw_text.index("Body line") < result.raw_text.index("Running header")


def test_header_only_docx_is_not_empty(tmp_path: Path) -> None:
    path = tmp_path / "header-only.docx"
    document = Document()
    document.sections[0].header.paragraphs[0].text = "Only header"
    document.save(path)

    result = normalize_docx(path)

    assert "Only header" in result.normalized_body


def test_table_only_docx_is_not_empty(tmp_path: Path) -> None:
    path = tmp_path / "table.docx"
    document = Document()
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Only cell"
    document.save(path)

    result = normalize_docx(path)

    assert "Only cell" in result.normalized_body
    assert result.title == "Table"
