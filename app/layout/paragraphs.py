"""Paragraph, list, and lightweight table reconstruction."""

from __future__ import annotations

import re

from app.core.config import ParagraphMergeConfig
from app.core.models import Paragraph, SourceTextBlock, TableBlock
from app.core.normalizer import join_line_text

_BULLET = re.compile(r"^[•\u2022\u25e6\u25aa\-–]\s+(.*)$")
_ORDERED = re.compile(r"^\s*(\d+|[a-zA-Z])[.)]\s+(.*)$")


def list_item(block: SourceTextBlock) -> tuple[bool, str] | None:
    """Return ordered state and content for a conventional visual list item."""
    bullet = _BULLET.match(block.text)
    if bullet:
        return False, bullet.group(1).strip()
    ordered = _ORDERED.match(block.text)
    if ordered:
        return True, ordered.group(2).strip()
    return None


def table_from_line(block: SourceTextBlock) -> TableBlock | None:
    """Preserve clearly delimiter-based tables rather than dropping their cells."""
    if block.text.count("|") >= 2:
        cells = [cell.strip() for cell in block.text.strip("|").split("|")]
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
        return Paragraph(text=text, bbox=bbox, page_number=lines[0].page_number)


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
