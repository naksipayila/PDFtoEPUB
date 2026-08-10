import pytest

from app.core.models import ParsedPage
from app.layout.headers_footers import is_page_number
from tests.conftest import source_block


@pytest.mark.parametrize(
    "text",
    [
        "1",
        "Page 24",
        "Sayfa 24",
        "s. 24",
        "(24)",
        "24.",
        "12 / 144",
        "- 24 -",
        "  398  ",
        "ıoo",
        "1 1 7",
        "ıB",
    ],
)
def test_recognizes_common_page_number_patterns(text: str) -> None:
    page = ParsedPage(number=1, width=595, height=842)
    assert is_page_number(source_block(text, y0=815, y1=827), page)


def test_uses_the_configured_edge_zone() -> None:
    page = ParsedPage(number=1, width=595, height=1000)
    assert is_page_number(source_block("24", y0=855, y1=867), page)


@pytest.mark.parametrize("text", ["ıoo", "Sayfa 24", "12 / 144"])
def test_does_not_remove_number_like_body_text(text: str) -> None:
    page = ParsedPage(number=1, width=595, height=842)
    assert not is_page_number(source_block(text, y0=400, y1=412), page)
