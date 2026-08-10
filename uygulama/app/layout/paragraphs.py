"""Paragraph, list, and lightweight table reconstruction."""

from __future__ import annotations

import re

from app.core.config import ParagraphMergeConfig
from app.core.models import ContentElement, Footnote, Paragraph, SourceTextBlock, TableBlock
from app.core.normalizer import join_line_text, normalize_text

_BULLET = re.compile(r"^[•\u2022\u25e6\u25aa\-–]\s+(.*)$")
_ORDERED = re.compile(r"^\s*(\d+|[a-zA-Z])[.)]\s+(.*)$")


def list_item(block: SourceTextBlock) -> tuple[bool, str] | None:
    """Return ordered state and content for a conventional visual list item."""
    bullet = _BULLET.match(block.text)
    if bullet:
        return False, normalize_text(bullet.group(1))
    ordered = _ORDERED.match(block.text)
    if ordered:
        return True, normalize_text(ordered.group(2))
    return None


def table_from_line(block: SourceTextBlock) -> TableBlock | None:
    """Preserve clearly delimiter-based tables rather than dropping their cells."""
    if block.text.count("|") >= 2:
        cells = [normalize_text(cell) for cell in block.text.strip("|").split("|")]
        return TableBlock(rows=[cells], bbox=block.bbox, page_number=block.page_number)
    return None


class ParagraphBuilder:
    """Merge adjacent visual lines into reflowable prose paragraphs."""

    def __init__(self, config: ParagraphMergeConfig | None = None) -> None:
        self._config = config or ParagraphMergeConfig()

    def build(self, lines: list[SourceTextBlock]) -> list[Paragraph]:
        if not lines:
            return []
        paragraphs: list[Paragraph] = []
        current: list[SourceTextBlock] = [lines[0]]
        for line in lines[1:]:
            if self._continues(current[-1], line):
                current.append(line)
            else:
                paragraphs.append(self._paragraph(current))
                current = [line]
        paragraphs.append(self._paragraph(current))
        return paragraphs

    def _continues(self, previous: SourceTextBlock, current: SourceTextBlock) -> bool:
        if current.bbox.y0 < previous.bbox.y0 - previous.font_size * 0.25:
            return False
        gap = current.bbox.y0 - previous.bbox.y1
        maximum_gap = max(previous.font_size, current.font_size) * self._config.max_line_gap_factor
        if gap > maximum_gap:
            return False
        indentation = abs(current.bbox.x0 - previous.bbox.x0)
        return (
            indentation
            <= max(previous.font_size, current.font_size)
            * self._config.indentation_tolerance_factor
        )

    @staticmethod
    def _paragraph(lines: list[SourceTextBlock]) -> Paragraph:
        text = lines[0].text
        bbox = lines[0].bbox
        for line in lines[1:]:
            text = join_line_text(text, line.text)
            bbox = bbox.union(line.bbox)
        return Paragraph(
            text=normalize_text(text), bbox=bbox, page_number=lines[0].page_number
        )


def merge_page_continuations(
    elements: list[ContentElement], page_widths: dict[int, float]
) -> tuple[list[ContentElement], int]:
    """Join prose that continues across a source-page boundary."""
    merged: list[ContentElement] = []
    merge_count = 0
    for element in elements:
        if isinstance(element, Paragraph):
            candidate_index = _previous_paragraph_index(merged, page_widths)
            if candidate_index is not None:
                previous = merged[candidate_index]
                if isinstance(previous, Paragraph) and _page_continues(
                    previous, element, page_widths
                ):
                    previous.text = join_line_text(previous.text, element.text)
                    if previous.bbox and element.bbox:
                        previous.bbox = previous.bbox.union(element.bbox)
                    previous.page_number = element.page_number
                    merge_count += 1
                    continue
        merged.append(element)
    return merged, merge_count


def _previous_paragraph_index(
    elements: list[ContentElement], page_widths: dict[int, float]
) -> int | None:
    if not elements:
        return None
    if isinstance(elements[-1], Paragraph):
        return len(elements) - 1
    if elements and _is_small_image(elements[-1], page_widths):
        if len(elements) > 1 and isinstance(elements[-2], Paragraph):
            return len(elements) - 2
    if isinstance(elements[-1], Footnote) and len(elements) > 1:
        if isinstance(elements[-2], Paragraph):
            return len(elements) - 2
    return None


def _is_small_image(element: ContentElement, page_widths: dict[int, float]) -> bool:
    from app.core.models import ImageBlock

    if not isinstance(element, ImageBlock) or not element.bbox or element.page_number is None:
        return False
    page_width = page_widths.get(element.page_number, 600.0)
    return max(element.bbox.width, element.bbox.height) <= page_width * 0.05


def _page_continues(
    previous: Paragraph, current: Paragraph, page_widths: dict[int, float]
) -> bool:
    if previous.page_number is None or current.page_number is None:
        return False
    if current.page_number != previous.page_number + 1:
        return False
    if not previous.bbox or not current.bbox:
        return False
    page_width = page_widths.get(previous.page_number, 600.0)
    if abs(previous.bbox.x0 - current.bbox.x0) > max(20.0, page_width * 0.12):
        return False

    current_text = current.text.lstrip()
    if not current_text or not current_text[0].islower():
        return False
    previous_text = previous.text.rstrip()
    if previous_text.endswith(("-", "\u00ad")):
        return True
    return not _ends_sentence(previous_text)


def _ends_sentence(value: str) -> bool:
    value = value.rstrip()
    while value and value[-1] in "\"'\u201d\u2019\xbb)]}":
        value = value[:-1].rstrip()
    return value.endswith((".", "!", "?", "\u2026"))


def merge_table_rows(tables: list[TableBlock]) -> list[TableBlock]:
    """Merge adjacent delimiter rows into a single semantic table."""
    merged: list[TableBlock] = []
    for table in tables:
        if merged and len(merged[-1].rows[0]) == len(table.rows[0]):
            merged[-1].rows.extend(table.rows)
            if merged[-1].bbox and table.bbox:
                merged[-1].bbox = merged[-1].bbox.union(table.bbox)
        else:
            merged.append(table)
    return merged
