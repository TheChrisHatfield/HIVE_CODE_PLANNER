from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from hive_planner.normalizers.pptx import normalize_pptx


def test_grouped_slide_text_is_indexed(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[0])
    slide.shapes.title.text = "Deck title"
    box = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(3), Inches(1))
    box.text_frame.text = "Grouped fact"
    slide.shapes.add_group_shape([box])
    plain = slide.shapes.add_textbox(Inches(1), Inches(4), Inches(3), Inches(1))
    plain.text_frame.text = "Plain fact"
    presentation.save(path)

    result = normalize_pptx(path)

    assert result.raw_text.count("Deck title") == 1
    assert "Grouped fact" in result.raw_text
    assert "Plain fact" in result.raw_text


def test_group_only_slide_is_not_empty(tmp_path: Path) -> None:
    path = tmp_path / "group.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1))
    box.text_frame.text = "Only grouped"
    slide.shapes.add_group_shape([box])
    presentation.save(path)

    result = normalize_pptx(path)

    assert "Only grouped" in result.normalized_body
    assert "## Slide 1" in result.normalized_body
