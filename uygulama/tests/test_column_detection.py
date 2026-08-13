from app.core.models import ParsedPage
from app.layout.columns import ReadingOrderResolver
from tests.conftest import source_block


def test_resolves_two_columns_left_to_right_then_top_to_bottom() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block("A1", x0=54, x1=160, y0=100, y1=112),
            source_block("B1", x0=340, x1=450, y0=100, y1=112),
            source_block("A2", x0=54, x1=160, y0=120, y1=132),
            source_block("B2", x0=340, x1=450, y0=120, y1=132),
        ],
    )

    blocks = ReadingOrderResolver().resolve(page)

    assert [block.text for block in blocks] == ["A1", "A2", "B1", "B2"]


def test_keeps_singleton_block_outside_detected_column_clusters() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block("A1", x0=54, x1=160, y0=100, y1=112, identifier="a1"),
            source_block("A2", x0=54, x1=160, y0=120, y1=132, identifier="a2"),
            source_block("Not", x0=210, x1=260, y0=110, y1=122, identifier="note"),
            source_block("B1", x0=340, x1=450, y0=100, y1=112, identifier="b1"),
            source_block("B2", x0=340, x1=450, y0=120, y1=132, identifier="b2"),
        ],
    )

    blocks = ReadingOrderResolver().resolve(page)

    assert {block.id for block in blocks} == {block.id for block in page.text_blocks}
    assert len(blocks) == len(page.text_blocks)


def test_keeps_right_column_beside_a_wide_left_column_and_centered_heading() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block("Contents", x0=275, x1=325, y0=30, y1=48, identifier="heading"),
            source_block("A1", x0=50, x1=260, y0=100, y1=112, identifier="a1"),
            source_block("A2", x0=50, x1=260, y0=125, y1=137, identifier="a2"),
            source_block("B1", x0=340, x1=550, y0=100, y1=112, identifier="b1"),
            source_block("B2", x0=340, x1=550, y0=125, y1=137, identifier="b2"),
        ],
    )

    blocks = ReadingOrderResolver().resolve(page)

    assert {block.id for block in blocks} == {block.id for block in page.text_blocks}
    assert len(blocks) == len(page.text_blocks)
