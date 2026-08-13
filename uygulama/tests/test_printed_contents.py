import zipfile

import pymupdf as fitz

from app.core.config import ConversionOptions
from app.core.converter import PdfToEpubConverter
from app.core.models import (
    Chapter,
    ConversionReport,
    DocumentMetadata,
    Heading,
    ParsedPage,
    PrintedTocBlock,
    PrintedTocEntry,
    SemanticDocument,
)
from app.epub.builder import EpubBuilder
from app.epub.validator import validate_epub
from app.layout.analyzer import HeuristicLayoutAnalyzer
from app.layout.contents import detect_printed_contents_pages
from tests.conftest import source_block


def test_reconstructs_entries_split_across_visual_lines() -> None:
    page = ParsedPage(
        number=3,
        width=1200,
        height=800,
        text_blocks=[
            source_block(
                "İçindekiler",
                x0=52,
                x1=180,
                y0=25,
                y1=42,
                font_size=16,
                bold=True,
                page=3,
                identifier="heading",
            ),
            source_block(
                "İnsan Neyle Yaşar?........................1 Kıvılcımı Söndürmeyen Ateşi Zapt",
                x0=52,
                x1=1000,
                y0=60,
                y1=72,
                page=3,
                identifier="line-1",
            ),
            source_block(
                "Edemez........................29 Mum........................47 Kızlar",
                x0=52,
                x1=1150,
                y0=84,
                y1=96,
                page=3,
                identifier="line-2",
            ),
            source_block(
                "Büyüklerden Akıllıymış........................59 İnsana Çok Toprak Gerek mi?........................63",
                x0=52,
                x1=1150,
                y0=108,
                y1=120,
                page=3,
                identifier="line-3",
            ),
            source_block(
                "İlyas........................81",
                x0=52,
                x1=900,
                y0=132,
                y1=144,
                page=3,
                identifier="line-4",
            ),
        ],
    )

    contents = detect_printed_contents_pages([page])[3]

    assert [(entry.title, entry.page_label) for entry in contents.entries] == [
        ("İnsan Neyle Yaşar?", "1"),
        ("Kıvılcımı Söndürmeyen Ateşi Zapt Edemez", "29"),
        ("Mum", "47"),
        ("Kızlar Büyüklerden Akıllıymış", "59"),
        ("İnsana Çok Toprak Gerek mi?", "63"),
        ("İlyas", "81"),
    ]
    assert contents.entry_block_ids == {"line-1", "line-2", "line-3", "line-4"}


def test_pairs_separate_titles_and_page_labels_by_geometry() -> None:
    page = ParsedPage(
        number=2,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "Contents", y0=35, y1=52, font_size=17, bold=True, identifier="heading"
            ),
            source_block("Preface", x0=55, x1=180, y0=110, y1=122, identifier="title-1"),
            source_block("vii", x0=510, x1=535, y0=110, y1=122, identifier="label-1"),
            source_block("First chapter", x0=55, x1=210, y0=135, y1=147, identifier="title-2"),
            source_block("1", x0=510, x1=520, y0=135, y1=147, identifier="label-2"),
            source_block("Second chapter", x0=55, x1=220, y0=160, y1=172, identifier="title-3"),
            source_block("18", x0=510, x1=530, y0=160, y1=172, identifier="label-3"),
        ],
    )

    contents = detect_printed_contents_pages([page])[2]

    assert [(entry.title, entry.page_label) for entry in contents.entries] == [
        ("Preface", "vii"),
        ("First chapter", "1"),
        ("Second chapter", "18"),
    ]


def test_orders_two_columns_of_separate_title_and_label_blocks_column_first() -> None:
    blocks = [
        source_block(
            "Contents", x0=50, x1=160, y0=30, y1=48, font_size=17, identifier="heading"
        )
    ]
    for identifier, title, label, x0, label_x, y0 in (
        ("left-1", "Left one", "1", 50, 250, 100),
        ("left-2", "Left two", "5", 50, 250, 125),
        ("right-1", "Right one", "9", 330, 550, 100),
        ("right-2", "Right two", "14", 330, 550, 125),
    ):
        blocks.extend(
            [
                source_block(
                    title,
                    x0=x0,
                    x1=label_x - 20,
                    y0=y0,
                    y1=y0 + 12,
                    identifier=f"{identifier}-title",
                ),
                source_block(
                    label,
                    x0=label_x,
                    x1=label_x + 20,
                    y0=y0,
                    y1=y0 + 12,
                    identifier=f"{identifier}-label",
                ),
            ]
        )
    page = ParsedPage(number=1, width=600, height=800, text_blocks=blocks)

    contents = detect_printed_contents_pages([page])[1]

    assert [entry.title for entry in contents.entries] == [
        "Left one",
        "Left two",
        "Right one",
        "Right two",
    ]


def test_preserves_source_order_when_leader_and_plain_rows_are_mixed() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "Contents", y0=30, y1=48, font_size=17, bold=True, identifier="heading"
            ),
            source_block("Preface vii", y0=90, y1=102, identifier="entry-1"),
            source_block("Chapter One ........ 1", y0=115, y1=127, identifier="entry-2"),
            source_block("Chapter Two 18", y0=140, y1=152, identifier="entry-3"),
        ],
    )

    contents = detect_printed_contents_pages([page])[1]

    assert [(entry.title, entry.page_label) for entry in contents.entries] == [
        ("Preface", "vii"),
        ("Chapter One", "1"),
        ("Chapter Two", "18"),
    ]


def test_joins_a_wrapped_title_before_its_leader_row() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "Contents", y0=30, y1=48, font_size=17, bold=True, identifier="heading"
            ),
            source_block("A Very Long Chapter", y0=90, y1=102, identifier="wrapped-1"),
            source_block("Title ........ 12", y0=104, y1=116, identifier="wrapped-2"),
            source_block("Second ........ 20", y0=135, y1=147, identifier="entry-2"),
        ],
    )

    contents = detect_printed_contents_pages([page])[1]

    assert [(entry.title, entry.page_label) for entry in contents.entries] == [
        ("A Very Long Chapter Title", "12"),
        ("Second", "20"),
    ]
    assert {"wrapped-1", "wrapped-2"}.issubset(contents.entry_block_ids)

    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        [page], ConversionOptions(use_ocr=False), ConversionReport()
    )
    toc_blocks = [
        element
        for chapter in document.chapters
        for element in chapter.elements
        if isinstance(element, PrintedTocBlock)
    ]
    assert len(toc_blocks) == 1
    assert [(entry.title, entry.page_label) for entry in toc_blocks[0].entries] == [
        ("A Very Long Chapter Title", "12"),
        ("Second", "20"),
    ]


def test_keeps_a_partially_recognized_source_line_as_text() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "Contents", y0=30, y1=48, font_size=17, bold=True, identifier="heading"
            ),
            source_block(
                "Valid ........ 1 unsupported remainder",
                y0=90,
                y1=102,
                identifier="partial",
            ),
            source_block("Second ........ 5", y0=200, y1=212, identifier="entry-2"),
            source_block("Third ........ 9", y0=225, y1=237, identifier="entry-3"),
        ],
    )

    contents = detect_printed_contents_pages([page])[1]

    assert "partial" not in contents.entry_block_ids
    assert [entry.title for entry in contents.entries] == ["Second", "Third"]


def test_analyzer_protects_bottom_contents_entries_from_footnote_filters() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "İÇİNDEKİLER",
                y0=40,
                y1=60,
                font_size=18,
                bold=True,
                identifier="heading",
            ),
            source_block("1. Başlangıç ........ 3", y0=570, y1=582, identifier="entry-1"),
            source_block("2. Devam ........ 15", y0=610, y1=622, identifier="entry-2"),
            source_block("3. Son ........ 28", y0=700, y1=712, identifier="entry-3"),
        ],
    )
    report = ConversionReport()

    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        [page], ConversionOptions(use_ocr=False), report
    )

    toc = next(
        element
        for chapter in document.chapters
        for element in chapter.elements
        if isinstance(element, PrintedTocBlock)
    )
    assert [entry.title for entry in toc.entries] == [
        "1. Başlangıç",
        "2. Devam",
        "3. Son",
    ]
    assert report.toc_entries_detected == 3
    assert report.footnotes_detected == 0
    assert report.page_numbers_removed == 0


def test_analyzer_still_extracts_a_real_footnote_on_contents_page() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "İçindekiler",
                y0=30,
                y1=48,
                font_size=17,
                bold=True,
                identifier="heading",
            ),
            source_block("Birinci ........ 1", y0=90, y1=102, identifier="entry-1"),
            source_block("İkinci ........ 5", y0=115, y1=127, identifier="entry-2"),
            source_block("1 Kaynak notu", y0=720, y1=732, font_size=8, identifier="note"),
        ],
    )
    report = ConversionReport()

    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        [page], ConversionOptions(use_ocr=False), report
    )

    elements = [element for chapter in document.chapters for element in chapter.elements]
    assert report.toc_entries_detected == 2
    assert report.footnotes_detected == 1
    assert any(getattr(element, "text", "") == "Kaynak notu" for element in elements)


def test_year_ending_footnote_is_not_promoted_to_plain_toc_entry() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "İçindekiler",
                y0=30,
                y1=48,
                font_size=17,
                bold=True,
                identifier="heading",
            ),
            source_block("Birinci ........ 1", y0=90, y1=102, identifier="entry-1"),
            source_block("İkinci ........ 5", y0=115, y1=127, identifier="entry-2"),
            source_block("1 Kaynak, 2020", y0=720, y1=732, font_size=8, identifier="note"),
        ],
    )
    report = ConversionReport()

    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        [page], ConversionOptions(use_ocr=False), report
    )

    toc = next(
        element
        for chapter in document.chapters
        for element in chapter.elements
        if isinstance(element, PrintedTocBlock)
    )
    assert [entry.title for entry in toc.entries] == ["Birinci", "İkinci"]
    assert report.footnotes_detected == 1


def test_alphabetic_and_superscript_footnotes_are_not_plain_toc_entries() -> None:
    for label in ("a", "¹"):
        page = ParsedPage(
            number=1,
            width=600,
            height=800,
            text_blocks=[
                source_block(
                    "Contents",
                    y0=30,
                    y1=48,
                    font_size=17,
                    bold=True,
                    identifier=f"heading-{label}",
                ),
                source_block(
                    "First ........ 1", y0=90, y1=102, identifier=f"entry-1-{label}"
                ),
                source_block(
                    "Second ........ 5", y0=115, y1=127, identifier=f"entry-2-{label}"
                ),
                source_block(
                    f"{label} Source, 2020",
                    y0=720,
                    y1=732,
                    font_size=8,
                    identifier=f"note-{label}",
                ),
            ],
        )
        report = ConversionReport()

        document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
            [page], ConversionOptions(use_ocr=False), report
        )

        toc = next(
            element
            for chapter in document.chapters
            for element in chapter.elements
            if isinstance(element, PrintedTocBlock)
        )
        assert [entry.title for entry in toc.entries] == ["First", "Second"]
        assert report.footnotes_detected == 1


def test_plain_contents_rows_do_not_consume_a_bottom_alphabetic_footnote() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "Contents", y0=30, y1=48, font_size=17, bold=True, identifier="heading"
            ),
            source_block("First 1", y0=90, y1=102, identifier="entry-1"),
            source_block("Second 5", y0=115, y1=127, identifier="entry-2"),
            source_block("Third 9", y0=140, y1=152, identifier="entry-3"),
            source_block("a Source, 2020", y0=720, y1=732, font_size=8, identifier="note"),
        ],
    )
    report = ConversionReport()

    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        [page], ConversionOptions(use_ocr=False), report
    )

    toc = next(
        element
        for chapter in document.chapters
        for element in chapter.elements
        if isinstance(element, PrintedTocBlock)
    )
    assert [entry.title for entry in toc.entries] == ["First", "Second", "Third"]
    assert report.footnotes_detected == 1


def test_bottom_numbered_contents_row_is_kept_when_it_matches_toc_context() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "Contents", y0=30, y1=48, font_size=17, bold=True, identifier="heading"
            ),
            source_block("First 1", y0=90, y1=102, identifier="entry-1"),
            source_block("Second 5", y0=115, y1=127, identifier="entry-2"),
            source_block("Third 9", y0=140, y1=152, identifier="entry-3"),
            source_block("1. Appendix 321", y0=720, y1=732, identifier="appendix"),
        ],
    )
    report = ConversionReport()

    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        [page], ConversionOptions(use_ocr=False), report
    )

    toc = next(
        element
        for chapter in document.chapters
        for element in chapter.elements
        if isinstance(element, PrintedTocBlock)
    )
    assert [entry.title for entry in toc.entries] == [
        "First",
        "Second",
        "Third",
        "1. Appendix",
    ]
    assert report.footnotes_detected == 0


def test_ignored_repeated_footer_is_not_promoted_to_plain_toc_entry() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "Contents", y0=30, y1=48, font_size=17, bold=True, identifier="heading"
            ),
            source_block("First ........ 1", y0=90, y1=102, identifier="entry-1"),
            source_block("Second ........ 5", y0=115, y1=127, identifier="entry-2"),
            source_block("Book title 3", y0=760, y1=772, font_size=8, identifier="footer"),
        ],
    )

    contents = detect_printed_contents_pages([page], {"footer"})[1]

    assert [entry.title for entry in contents.entries] == ["First", "Second"]
    assert "footer" not in contents.protected_block_ids


def test_invalid_leader_segment_keeps_the_entire_source_block() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "Contents", y0=30, y1=48, font_size=17, bold=True, identifier="heading"
            ),
            source_block(
                "........ 1 Valid ........ 5",
                y0=90,
                y1=102,
                identifier="partially-invalid",
            ),
            source_block("Second ........ 9", y0=130, y1=142, identifier="entry-2"),
            source_block("Third ........ 12", y0=155, y1=167, identifier="entry-3"),
        ],
    )

    contents = detect_printed_contents_pages([page])[1]

    assert "partially-invalid" not in contents.entry_block_ids
    assert [entry.title for entry in contents.entries] == ["Second", "Third"]


def test_accepts_a_plain_three_row_column_beside_a_leader_column() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "Contents", y0=30, y1=48, font_size=17, bold=True, identifier="heading"
            ),
            source_block(
                "Left one ........ 1", x0=50, x1=270, y0=90, y1=102, identifier="left-1"
            ),
            source_block(
                "Left two ........ 5", x0=50, x1=270, y0=115, y1=127, identifier="left-2"
            ),
            source_block(
                "Right one 9", x0=330, x1=550, y0=90, y1=102, identifier="right-1"
            ),
            source_block(
                "Right two 14", x0=330, x1=550, y0=115, y1=127, identifier="right-2"
            ),
            source_block(
                "Right three 21", x0=330, x1=550, y0=140, y1=152, identifier="right-3"
            ),
        ],
    )

    contents = detect_printed_contents_pages([page])[1]

    assert [entry.title for entry in contents.entries] == [
        "Left one",
        "Left two",
        "Right one",
        "Right two",
        "Right three",
    ]


def test_repeated_heading_on_adjacent_contents_page_does_not_start_another_chapter() -> None:
    pages = [
        ParsedPage(
            number=number,
            width=600,
            height=800,
            text_blocks=[
                source_block(
                    "Contents",
                    y0=30,
                    y1=48,
                    font_size=17,
                    bold=True,
                    page=number,
                    identifier=f"heading-{number}",
                ),
                source_block(
                    f"Entry {number}A ........ {number}",
                    y0=90,
                    y1=102,
                    page=number,
                    identifier=f"entry-{number}-1",
                ),
                source_block(
                    f"Entry {number}B ........ {number + 1}",
                    y0=115,
                    y1=127,
                    page=number,
                    identifier=f"entry-{number}-2",
                ),
            ],
        )
        for number in (1, 2)
    ]

    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        pages, ConversionOptions(use_ocr=False), ConversionReport()
    )

    assert [chapter.title for chapter in document.chapters] == ["Contents"]
    assert sum(
        isinstance(element, PrintedTocBlock)
        for chapter in document.chapters
        for element in chapter.elements
    ) == 2


def test_centered_contents_heading_precedes_two_column_entries() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "Contents",
                x0=275,
                x1=325,
                y0=30,
                y1=48,
                font_size=17,
                bold=True,
                identifier="heading",
            ),
            source_block(
                "Left one ........ 1", x0=50, x1=260, y0=100, y1=112, identifier="left-1"
            ),
            source_block(
                "Left two ........ 5", x0=50, x1=260, y0=125, y1=137, identifier="left-2"
            ),
            source_block(
                "Right one ........ 9", x0=340, x1=550, y0=100, y1=112, identifier="right-1"
            ),
            source_block(
                "Right two ........ 14", x0=340, x1=550, y0=125, y1=137, identifier="right-2"
            ),
        ],
    )

    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        [page], ConversionOptions(use_ocr=False), ConversionReport()
    )

    assert [chapter.title for chapter in document.chapters] == ["Contents"]
    assert isinstance(document.chapters[0].elements[0], Heading)
    assert isinstance(document.chapters[0].elements[1], PrintedTocBlock)
    assert [
        entry.title for entry in document.chapters[0].elements[1].entries
    ] == ["Left one", "Left two", "Right one", "Right two"]


def test_unrecognized_contents_text_stays_between_toc_blocks() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block(
                "Contents", y0=30, y1=48, font_size=17, bold=True, identifier="heading"
            ),
            source_block("First ........ 1", y0=90, y1=102, identifier="entry-1"),
            source_block("Part Two", y0=115, y1=127, font_size=14, bold=True, identifier="group"),
            source_block("Second ........ 5", y0=140, y1=152, identifier="entry-2"),
            source_block("Third ........ 9", y0=165, y1=177, identifier="entry-3"),
        ],
    )

    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        [page], ConversionOptions(use_ocr=False), ConversionReport()
    )

    elements = document.chapters[0].elements
    assert isinstance(elements[1], PrintedTocBlock)
    assert getattr(elements[2], "text", "") == "Part Two"
    assert isinstance(elements[3], PrintedTocBlock)
    assert [
        entry.title
        for element in elements
        if isinstance(element, PrintedTocBlock)
        for entry in element.entries
    ] == ["First", "Second", "Third"]


def test_top_repeated_header_is_not_a_continuation_toc_entry() -> None:
    pages = [
        ParsedPage(
            number=1,
            width=600,
            height=800,
            text_blocks=[
                source_block(
                    "Contents", y0=30, y1=48, font_size=17, bold=True, identifier="heading"
                ),
                source_block("First ........ 1", y0=90, y1=102, identifier="entry-1"),
                source_block("Second ........ 5", y0=115, y1=127, identifier="entry-2"),
            ],
        ),
        ParsedPage(
            number=2,
            width=600,
            height=800,
            text_blocks=[
                source_block("Book title 2", y0=20, y1=32, font_size=8, identifier="header-2"),
                source_block("Third ........ 9", y0=90, y1=102, identifier="entry-3"),
                source_block("Fourth ........ 14", y0=115, y1=127, identifier="entry-4"),
                source_block("Fifth ........ 21", y0=140, y1=152, identifier="entry-5"),
            ],
        ),
        ParsedPage(
            number=3,
            width=600,
            height=800,
            text_blocks=[
                source_block("Book title 3", y0=20, y1=32, font_size=8, identifier="header-3"),
                source_block("Body text.", y0=200, y1=212, identifier="body"),
            ],
        ),
    ]

    document = HeuristicLayoutAnalyzer(DocumentMetadata(), {}).analyze(
        pages, ConversionOptions(use_ocr=False), ConversionReport()
    )

    toc_titles = [
        entry.title
        for chapter in document.chapters
        for element in chapter.elements
        if isinstance(element, PrintedTocBlock)
        for entry in element.entries
    ]
    assert toc_titles == ["First", "Second", "Third", "Fourth", "Fifth"]


def test_dotted_prose_without_contents_heading_is_not_reclassified() -> None:
    page = ParsedPage(
        number=1,
        width=600,
        height=800,
        text_blocks=[
            source_block("Bir cümle... 12", y0=100, y1=112, identifier="line-1"),
            source_block("Başka bir cümle... 14", y0=125, y1=137, identifier="line-2"),
        ],
    )

    assert detect_printed_contents_pages([page]) == {}


def test_renders_printed_contents_as_responsive_epub_rows(tmp_path) -> None:
    document = SemanticDocument(
        metadata=DocumentMetadata(title="Test", language="tr"),
        chapters=[
            Chapter(
                title="İçindekiler",
                identifier="chapter-001",
                elements=[
                    Heading("İçindekiler", 1, page_number=2),
                    PrintedTocBlock(
                        [
                            PrintedTocEntry("Birinci Bölüm", "1"),
                            PrintedTocEntry("1.1 Alt Başlık", "7", level=1),
                        ],
                        page_number=2,
                    ),
                ],
            )
        ],
    )
    output = tmp_path / "contents.epub"

    EpubBuilder().build(document, output, ConversionOptions(use_ocr=False))

    assert validate_epub(output) == []
    with zipfile.ZipFile(output) as archive:
        chapter = archive.read("EPUB/chapters/chapter_001.xhtml").decode("utf-8")
        css = archive.read("EPUB/styles.css").decode("utf-8")
    assert 'class="printed-toc"' in chapter
    assert '<span class="printed-toc-title">Birinci Bölüm</span>' in chapter
    assert '<span class="printed-toc-page">&#160;1</span>' in chapter
    assert "printed-toc-level-1" in chapter
    assert ".printed-toc-leader" in css
    assert "display: flex" in css


def test_converter_reformats_a_printed_contents_page_from_pdf(tmp_path) -> None:
    source = tmp_path / "printed-contents.pdf"
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_text((54, 70), "Contents", fontsize=18, fontname="hebo")
    page.insert_text((54, 110), "First Story .................... 1", fontsize=11)
    page.insert_text((54, 135), "Second Story .................. 9", fontsize=11)
    page.insert_text((54, 160), "Third Story ................... 21", fontsize=11)
    pdf.save(source)
    pdf.close()
    output = tmp_path / "printed-contents.epub"

    report = PdfToEpubConverter().convert(
        source, output, ConversionOptions(use_ocr=False)
    )

    assert report.toc_entries_detected == 3
    assert validate_epub(output) == []
    with zipfile.ZipFile(output) as archive:
        chapter = archive.read("EPUB/chapters/chapter_001.xhtml").decode("utf-8")
    assert chapter.count('class="printed-toc-entry ') == 3
    assert "First Story" in chapter
    assert "...................." not in chapter


def test_conversion_report_keeps_existing_positional_field_order() -> None:
    report = ConversionReport(1, 2, 3, 4, 5, 6, 7, 8)

    assert report.footnotes_detected == 8
    assert report.toc_entries_detected == 0
