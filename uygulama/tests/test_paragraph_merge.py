import pytest

from app.core.models import BoundingBox, Paragraph
from app.layout.paragraphs import (
    ParagraphBuilder,
    is_dialogue_start,
    list_item,
    merge_page_continuations,
)
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


@pytest.mark.parametrize("marker", ["-", "–", "—"])
def test_dialogue_lines_stay_as_separate_paragraphs(marker: str) -> None:
    paragraphs = ParagraphBuilder().build(
        [
            source_block(f"{marker} Birinci konuşma.", y0=100, y1=112),
            source_block(f"{marker} İkinci konuşma.", y0=114, y1=126),
        ]
    )

    assert [paragraph.text for paragraph in paragraphs] == [
        f"{marker} Birinci konuşma.",
        f"{marker} İkinci konuşma.",
    ]
    assert all(is_dialogue_start(paragraph.text) for paragraph in paragraphs)


def test_dialogue_marker_is_not_treated_as_a_list_item() -> None:
    block = source_block("– Liste gibi görünen konuşma", y0=100, y1=112)

    assert list_item(block) is None


def test_unmarked_dialogue_wrap_stays_in_the_same_paragraph() -> None:
    paragraphs = ParagraphBuilder().build(
        [
            source_block("— Uzun konuşmanın ilk satırı", y0=100, y1=112),
            source_block("devam eden ikinci satırı.", y0=114, y1=126),
        ]
    )

    assert [paragraph.text for paragraph in paragraphs] == [
        "— Uzun konuşmanın ilk satırı devam eden ikinci satırı."
    ]


def test_paragraphs_with_a_normal_visual_gap_stay_separate() -> None:
    paragraphs = ParagraphBuilder().build(
        [
            source_block("Birinci paragraf.", y0=100, y1=112),
            source_block("İkinci paragraf.", y0=128, y1=140),
        ]
    )

    assert [paragraph.text for paragraph in paragraphs] == [
        "Birinci paragraf.",
        "İkinci paragraf.",
    ]
