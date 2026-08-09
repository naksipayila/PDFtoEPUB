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
