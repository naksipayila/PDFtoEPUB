from app.core.config import ConversionOptions
from app.core.models import ConversionReport, DocumentMetadata, ParsedPage
from app.layout.analyzer import HeuristicLayoutAnalyzer
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


def test_detects_repeated_header_with_changing_page_number() -> None:
    pages = [
        ParsedPage(
            number=index,
            width=600,
            height=800,
            text_blocks=[
                source_block(
                    f"Synthetic Layout Book - {index}",
                    page=index,
                    y0=115,
                    y1=127,
                    identifier=f"variable-header-{index}",
                ),
                source_block(f"Unique {index}", page=index, y0=240, y1=252),
            ],
        )
        for index in range(1, 4)
    ]

    removed = repeated_header_footer_ids(pages)

    assert removed == {"variable-header-1", "variable-header-2", "variable-header-3"}


def test_detects_variable_running_headers_with_a_shared_margin_style() -> None:
    running_headers = ("Author name", "Spring story", "Autumn tale", "Winter note")
    pages = [
        ParsedPage(
            number=index,
            width=600,
            height=800,
            text_blocks=[
                source_block(
                    running_headers[index - 1],
                    page=index,
                    y0=22,
                    y1=34,
                    font_size=8,
                    identifier=f"running-header-{index}",
                ),
                source_block(f"Unique {index}", page=index, y0=160, y1=172),
            ],
        )
        for index in range(1, 5)
    ]

    removed = repeated_header_footer_ids(pages)

    assert removed == {
        "running-header-1",
        "running-header-2",
        "running-header-3",
        "running-header-4",
    }


def test_keeps_large_repeated_top_headings() -> None:
    running_headers = ("Author name", "Spring story", "Autumn tale", "Winter note")
    chapter_titles = ("First arrival", "Stormy night", "Silent train", "Final letter")
    pages = [
        ParsedPage(
            number=index,
            width=600,
            height=800,
            text_blocks=[
                source_block(
                    running_headers[index - 1],
                    page=index,
                    y0=22,
                    y1=34,
                    font_size=8,
                    identifier=f"running-header-{index}",
                ),
                source_block(
                    chapter_titles[index - 1],
                    page=index,
                    y0=56,
                    y1=76,
                    font_size=20,
                    identifier=f"chapter-{index}",
                ),
                source_block(f"Unique {index}", page=index, y0=160, y1=172),
            ],
        )
        for index in range(1, 5)
    ]

    removed = repeated_header_footer_ids(pages)

    assert removed == {
        "running-header-1",
        "running-header-2",
        "running-header-3",
        "running-header-4",
    }


def test_analyzer_excludes_repeated_header_blocks() -> None:
    pages = [
        ParsedPage(
            number=index,
            width=600,
            height=800,
            text_blocks=[
                source_block(
                    f"Synthetic Layout Book - {index}",
                    page=index,
                    y0=115,
                    y1=127,
                    identifier=f"variable-header-{index}",
                ),
                source_block(f"Body text {index}", page=index, y0=240, y1=252),
            ],
        )
        for index in range(1, 4)
    ]
    report = ConversionReport()
    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        pages,
        ConversionOptions(
            detect_columns=False,
            detect_chapters=False,
            detect_tables=False,
            preserve_footnotes=False,
        ),
        report,
    )

    texts = [
        element.text
        for chapter in document.chapters
        for element in chapter.elements
        if hasattr(element, "text")
    ]
    assert report.headers_removed == 3
    assert all("Synthetic Layout Book" not in text for text in texts)
