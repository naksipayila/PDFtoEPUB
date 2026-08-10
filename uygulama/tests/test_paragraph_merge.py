from app.core.models import BoundingBox, Paragraph
from app.layout.paragraphs import ParagraphBuilder, merge_page_continuations
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


def test_merges_a_word_continuation_across_adjacent_pages() -> None:
    elements = [
        Paragraph("yakın çevrede öyley-", BoundingBox(4, 700, 250, 712), 9),
        Paragraph("miş. Çocuk devam etti.", BoundingBox(5, 30, 250, 42), 10),
    ]

    merged, count = merge_page_continuations(elements, {9: 255, 10: 255})

    assert count == 1
    assert [element.text for element in merged] == [
        "yakın çevrede öyleymiş. Çocuk devam etti."
    ]
    assert merged[0].page_number == 10


def test_keeps_sentence_ended_page_paragraphs_separate() -> None:
    elements = [
        Paragraph("İlk paragraf bitti.", BoundingBox(4, 700, 250, 712), 1),
        Paragraph("Yeni paragraf başladı.", BoundingBox(5, 30, 250, 42), 2),
    ]

    merged, count = merge_page_continuations(elements, {1: 255, 2: 255})

    assert count == 0
    assert [element.text for element in merged] == [
        "İlk paragraf bitti.",
        "Yeni paragraf başladı.",
    ]
