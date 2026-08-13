"""Heuristic source-page to semantic-document analyzer."""

from __future__ import annotations

from collections.abc import Iterable

from app.core.config import ConversionOptions
from app.core.models import (
    Chapter,
    ContentElement,
    ConversionReport,
    DocumentMetadata,
    Footnote,
    Heading,
    ImageAsset,
    ImageBlock,
    ListBlock,
    Paragraph,
    ParsedPage,
    PrintedTocBlock,
    SemanticDocument,
    SourceTextBlock,
    TableBlock,
)
from app.core.normalizer import normalize_text
from app.layout.captions import associate_captions
from app.layout.columns import ReadingOrderResolver
from app.layout.contents import PrintedContentsPage, detect_printed_contents_pages
from app.layout.footnotes import extract_footnotes
from app.layout.headers_footers import is_page_number, repeated_header_footer_ids
from app.layout.headings import HeadingDetector
from app.layout.paragraphs import (
    ParagraphBuilder,
    is_dialogue_start,
    list_item,
    merge_page_continuations,
    table_from_line,
)


class HeuristicLayoutAnalyzer:
    """Offline, deterministic layout interpretation with loss-averse fallbacks."""

    def __init__(self, metadata: DocumentMetadata, assets: dict[str, ImageAsset]) -> None:
        self._metadata = metadata
        self._assets = assets
        self._resolver = ReadingOrderResolver()
        self._paragraphs = ParagraphBuilder()

    def analyze(
        self,
        pages: list[ParsedPage],
        options: ConversionOptions,
        report: ConversionReport,
    ) -> SemanticDocument:
        """Convert coordinate-rich pages into ordered EPUB-ready content."""
        raw_removed_headers = (
            repeated_header_footer_ids(pages) if options.remove_headers_footers else set()
        )
        footer_ids = {
            block.id
            for page in pages
            for block in page.text_blocks
            if block.id in raw_removed_headers and block.bbox.y1 >= page.height * 0.855
        }
        contents_pages = detect_printed_contents_pages(
            pages,
            footer_ids,
            raw_removed_headers - footer_ids,
        )
        protected_ids = {
            block_id
            for contents in contents_pages.values()
            for block_id in contents.protected_block_ids
        }
        removed_headers = (
            raw_removed_headers - protected_ids if options.remove_headers_footers else set()
        )
        report.headers_removed = len(removed_headers)
        header_pages: list[tuple[ParsedPage, list[SourceTextBlock]]] = [
            (
                page,
                [
                    block
                    for block in page.text_blocks
                    if block.id not in removed_headers
                ],
            )
            for page in pages
        ]
        note_body_blocks = [
            block
            for _, page_blocks in header_pages
            for block in page_blocks
            if block.id not in protected_ids
        ]
        note_body_size = HeadingDetector(note_body_blocks).body_size
        content_pages: list[
            tuple[ParsedPage, list[SourceTextBlock], list[Footnote]]
        ] = []
        for page, header_blocks in header_pages:
            if options.preserve_footnotes:
                protected_blocks = [
                    block for block in header_blocks if block.id in protected_ids
                ]
                page_blocks, footnotes = extract_footnotes(
                    page,
                    [block for block in header_blocks if block.id not in protected_ids],
                    note_body_size,
                )
                page_blocks.extend(protected_blocks)
            else:
                page_blocks, footnotes = header_blocks, []
            page_blocks = [
                block
                for block in page_blocks
                if not (
                    options.remove_page_numbers
                    and block.id not in protected_ids
                    and is_page_number(block, page)
                )
            ]
            if page_blocks or footnotes or _page_fallback_images(page):
                content_pages.append((page, page_blocks, footnotes))
            else:
                report.pages_skipped += 1
        active_blocks = [
            block for _, page_blocks, _ in content_pages for block in page_blocks
            if block.id not in protected_ids
        ]
        if options.remove_page_numbers:
            report.page_numbers_removed = sum(
                1
                for page, page_blocks in header_pages
                for block in page_blocks
                if block.id not in protected_ids and is_page_number(block, page)
            )
        heading_detector = HeadingDetector(active_blocks)
        elements: list[ContentElement] = []
        for page, page_blocks, footnotes in content_pages:
            if options.detect_columns:
                order_page = ParsedPage(
                    number=page.number,
                    width=page.width,
                    height=page.height,
                    text_blocks=page_blocks,
                    images=page.images,
                    ocr_used=page.ocr_used,
                    text_source=page.text_source,
                    ocr_confidence=page.ocr_confidence,
                    issues=page.issues,
                )
                ordered = self._resolver.resolve(order_page)
            else:
                ordered = sorted(page_blocks, key=lambda block: (block.bbox.y0, block.bbox.x0))
            page_elements = self._build_page_elements(
                page,
                ordered,
                heading_detector,
                options,
                report,
                contents_pages.get(page.number),
            )
            elements.extend(self._insert_images(page_elements, page, options))
            elements.extend(footnotes)
            report.footnotes_detected += len(footnotes)

        elements, merged_paragraphs = merge_page_continuations(
            elements, {page.number: page.width for page, _, _ in content_pages}
        )
        report.paragraphs_detected = max(0, report.paragraphs_detected - merged_paragraphs)
        elements = [
            element
            for element in associate_captions(elements)
            if isinstance(element, _element_types())
        ]
        document = SemanticDocument(metadata=self._metadata, assets=self._assets)
        document.chapters = build_chapters(elements, options.detect_chapters)
        report.chapters_detected = len(document.chapters)
        return document

    def _build_page_elements(
        self,
        page: ParsedPage,
        blocks: list[SourceTextBlock],
        detector: HeadingDetector,
        options: ConversionOptions,
        report: ConversionReport,
        contents: PrintedContentsPage | None = None,
    ) -> list[ContentElement]:
        result: list[ContentElement] = []
        pending: list[SourceTextBlock] = []

        if contents is not None and contents.heading is not None and contents.show_heading:
            result.append(
                Heading(
                    normalize_text(contents.heading.text),
                    1,
                    contents.heading.bbox,
                    contents.heading.page_number,
                )
            )
            report.headings_detected += 1

        def flush_paragraphs() -> None:
            if not pending:
                return
            paragraphs = self._paragraphs.build(pending)
            result.extend(paragraphs)
            report.paragraphs_detected += len(paragraphs)
            pending.clear()

        index = 0
        while index < len(blocks):
            block = blocks[index]
            if contents is not None and contents.heading is not None and block.id == contents.heading.id:
                flush_paragraphs()
                index += 1
                continue
            if contents is not None and block.id in contents.entry_block_ids:
                flush_paragraphs()
                entries = []
                bbox = block.bbox
                while index < len(blocks):
                    current = blocks[index]
                    if (
                        contents.heading is not None
                        and current.id == contents.heading.id
                    ):
                        index += 1
                        continue
                    if current.id not in contents.entry_block_ids:
                        break
                    entries.extend(contents.entries_by_block_id.get(current.id, ()))
                    bbox = bbox.union(current.bbox)
                    index += 1
                if entries:
                    result.append(
                        PrintedTocBlock(
                            list(entries),
                            bbox,
                            page.number,
                        )
                    )
                    report.toc_entries_detected += len(entries)
                continue
            if is_dialogue_start(block.text):
                flush_paragraphs()
                pending.append(block)
                index += 1
                continue

            item = list_item(block)
            next_item = list_item(blocks[index + 1]) if index + 1 < len(blocks) else None
            is_list = item is not None and (
                not item[0] or (next_item is not None and next_item[0] == item[0])
            )
            if is_list and item is not None:
                flush_paragraphs()
                ordered, first_text = item
                items = [first_text]
                bbox = block.bbox
                cursor = index + 1
                while cursor < len(blocks):
                    next_item = list_item(blocks[cursor])
                    if next_item is None or next_item[0] != ordered:
                        break
                    items.append(next_item[1])
                    bbox = bbox.union(blocks[cursor].bbox)
                    cursor += 1
                result.append(ListBlock(items, ordered, bbox, block.page_number))
                index = cursor
                continue

            if detector.is_heading(block):
                flush_paragraphs()
                level = max(2, detector.level(block)) if contents is not None else detector.level(block)
                result.append(
                    Heading(normalize_text(block.text), level, block.bbox, block.page_number)
                )
                report.headings_detected += 1
                index += 1
                continue

            table = table_from_line(block) if options.detect_tables else None
            if table is not None:
                flush_paragraphs()
                result.append(table)
                report.tables_detected += 1
                index += 1
                continue

            pending.append(block)
            index += 1
        flush_paragraphs()
        return result

    @staticmethod
    def _insert_images(
        text_elements: list[ContentElement],
        page: ParsedPage,
        options: ConversionOptions,
    ) -> list[ContentElement]:
        images = [
            image
            for image in page.images
            if options.include_images or image.role == "page-fallback"
        ]
        if not images:
            return text_elements
        images = sorted(images, key=lambda image: image.bbox.y0)
        result: list[ContentElement] = []
        image_index = 0
        for element in text_elements:
            element_y = element.bbox.y0 if getattr(element, "bbox", None) else float("inf")
            while image_index < len(images) and images[image_index].bbox.y0 <= element_y:
                image = images[image_index]
                result.append(
                    ImageBlock(
                        asset_id=image.asset_id,
                        bbox=image.bbox,
                        page_number=image.page_number,
                    )
                )
                image_index += 1
            result.append(element)
        for image in images[image_index:]:
            result.append(
                ImageBlock(image.asset_id, bbox=image.bbox, page_number=image.page_number)
            )
        return result


def build_chapters(elements: Iterable[ContentElement], detect_chapters: bool) -> list[Chapter]:
    """Create separate spine documents at primary heading boundaries."""
    chapters: list[Chapter] = []
    current = Chapter(title="Start", identifier="chapter-001")
    for element in elements:
        is_start = detect_chapters and isinstance(element, Heading) and element.level == 1
        if is_start:
            if current.elements:
                chapters.append(current)
            current = Chapter(title=element.text, identifier=f"chapter-{len(chapters) + 1:03d}")
            current.elements.append(element)
            continue
        current.elements.append(element)
    if current.elements or not chapters:
        chapters.append(current)
    return chapters


def _element_types() -> tuple[type[ContentElement], ...]:
    # Kept in one location for the runtime filter used after caption association.
    from app.core.models import Footnote

    return (Paragraph, Heading, ImageBlock, ListBlock, TableBlock, PrintedTocBlock, Footnote)


def _page_fallback_images(page: ParsedPage) -> list:
    return [image for image in page.images if image.role == "page-fallback"]
