from app.core.models import ParsedPage
from app.layout.headers_footers import is_page_number, repeated_header_footer_ids
from tests.conftest import source_block


def test_detects_repeated_header_at_page_edge() -> None:
    pages = [
        ParsedPage(
            number=index,
            width=600,
            height=800,
            text_blocks=[
                source_block("Book Title", page=index, y0=20, y1=30, identifier=f"header-{index}"),
                source_block(f"Unique {index}", page=index, y0=120, y1=132),
            ],
        )
        for index in range(1, 4)
    ]

    removed = repeated_header_footer_ids(pages)

    assert removed == {"header-1", "header-2", "header-3"}


def test_matches_only_edge_page_numbers() -> None:
    page = ParsedPage(number=1, width=600, height=800)
    assert is_page_number(source_block("- 24 -", y0=780, y1=790), page)
    assert not is_page_number(source_block("24", y0=400, y1=412), page)
