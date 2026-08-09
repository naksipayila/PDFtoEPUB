from app.layout.paragraphs import ParagraphBuilder
from tests.conftest import source_block


def test_merges_visual_lines_and_repairs_discretionary_hyphen() -> None:
    lines = [
        source_block("This is an inter-", y0=100, y1=112),
        source_block("national example.", y0=113, y1=125),
    ]

    paragraphs = ParagraphBuilder().build(lines)

    assert [paragraph.text for paragraph in paragraphs] == ["This is an international example."]


def test_keeps_widely_separated_lines_as_paragraphs() -> None:
    paragraphs = ParagraphBuilder().build(
        [
            source_block("First paragraph.", y0=100, y1=112),
            source_block("Second paragraph.", y0=150, y1=162),
        ]
    )

    assert len(paragraphs) == 2
