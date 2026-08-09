"""Heuristic source-page to semantic-document analyzer."""

from __future__ import annotations

from collections.abc import Iterable

from app.core.config import ConversionOptions
from app.core.models import (
    Chapter,
    ContentElement,
    ConversionReport,
    DocumentMetadata,
    Heading,
    ImageAsset,
    ImageBlock,
    ListBlock,
    Paragraph,
    ParsedPage,
    SemanticDocument,
    SourceTextBlock,
    TableBlock,
)
from app.layout.captions import associate_captions
from app.layout.columns import ReadingOrderResolver
from app.layout.footnotes import as_footnote
from app.layout.headers_footers import is_page_number, repeated_header_footer_ids
from app.layout.headings import HeadingDetector
from app.layout.paragraphs import ParagraphBuilder, list_item, table_from_line


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
        removed_headers = (
            repeated_header_footer_ids(pages) if options.remove_headers_footers else set()
        )
        report.headers_removed = len(removed_headers)
        active_blocks = [
            block
            for page in pages
            for block in page.text_blocks
            if block.id not in removed_headers
            and not (options.remove_page_numbers and is_page_number(block, page))
        ]
        if options.remove_page_numbers:
            report.page_numbers_removed = sum(
                1 for page in pages for block in page.text_blocks if is_page_number(block, page)
            )
        heading_detector = HeadingDetector(active_blocks)
        elements: list[ContentElement] = []
        for page in pages:
            page_blocks = [
                block
                for block in page.text_blocks
                if block.id not in removed_headers
                and not (options.remove_page_numbers and is_page_number(block, page))
            ]
            if options.detect_columns:
                order_page = ParsedPage(
                    number=page.number,
                    width=page.width,
                    height=page.height,
                    text_blocks=page_blocks,
                    images=page.images,
                    ocr_used=page.ocr_used,
                )
                ordered = self._resolver.resolve(order_page)
            else:
                ordered = sorted(page_blocks, key=lambda block: (block.bbox.y0, block.bbox.x0))
            page_elements = self._build_page_elements(
                page, ordered, heading_detector, options, report
            )
            elements.extend(self._insert_images(page_elements, page, options))

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
    ) -> list[ContentElement]:
        result: list[ContentElement] = []
        pending: list[SourceTextBlock] = []

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
            footnote = (
                as_footnote(block, page, detector.body_size) if options.preserve_footnotes else None
            )
            if footnote is not None:
                flush_paragraphs()
                result.append(footnote)
                report.footnotes_detected += 1
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
                level = detector.level(block)
                result.append(Heading(block.text, level, block.bbox, block.page_number))
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
        if not options.include_images or not page.images:
            return text_elements
        images = sorted(page.images, key=lambda image: image.bbox.y0)
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

    return (Paragraph, Heading, ImageBlock, ListBlock, TableBlock, Footnote)
