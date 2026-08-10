from app.core.config import ConversionOptions
from app.core.models import ConversionReport, DocumentMetadata, Footnote, Paragraph, ParsedPage
from app.layout.analyzer import HeuristicLayoutAnalyzer
from app.layout.footnotes import extract_footnotes
from tests.conftest import source_block


def _page_with_footnotes() -> ParsedPage:
    return ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block("Ana metin paragrafı.", y0=100, y1=112, font_size=10),
            source_block("1. Birinci açıklamanın ilk satırı.", y0=620, y1=630, font_size=8),
            source_block("devam eden satırı.", y0=632, y1=642, font_size=8),
            source_block("[2] İkinci açıklama.", y0=665, y1=675, font_size=8),
        ],
    )


def test_groups_bottom_footnote_continuations_and_preserves_labels() -> None:
    page = _page_with_footnotes()

    body, notes = extract_footnotes(page, page.text_blocks, body_size=10)

    assert [block.text for block in body] == ["Ana metin paragrafı."]
    assert [note.label for note in notes] == ["1.", "[2]"]
    assert [note.text for note in notes] == [
        "Birinci açıklamanın ilk satırı. devam eden satırı.",
        "İkinci açıklama.",
    ]
    assert [note.identifier for note in notes] == ["note-1-1", "note-1-2"]


def test_analyzer_emits_footnotes_as_separate_elements_in_order() -> None:
    report = ConversionReport()
    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        [_page_with_footnotes()],
        ConversionOptions(
            detect_columns=False,
            detect_chapters=False,
            detect_tables=False,
        ),
        report,
    )
    elements = document.chapters[0].elements

    assert isinstance(elements[0], Paragraph)
    assert [element.text for element in elements[1:] if isinstance(element, Footnote)] == [
        "Birinci açıklamanın ilk satırı. devam eden satırı.",
        "İkinci açıklama.",
    ]
    assert report.footnotes_detected == 2
