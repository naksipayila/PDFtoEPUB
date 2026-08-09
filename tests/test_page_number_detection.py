import pytest

from app.core.models import ParsedPage
from app.layout.headers_footers import is_page_number
from tests.conftest import source_block


@pytest.mark.parametrize("text", ["1", "Page 24", "- 24 -", "  398  "])
def test_recognizes_common_page_number_patterns(text: str) -> None:
    page = ParsedPage(number=1, width=595, height=842)
    assert is_page_number(source_block(text, y0=815, y1=827), page)
