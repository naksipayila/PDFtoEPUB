"""Bottom-of-page footnote recognition and grouping."""

from __future__ import annotations

import re

from app.core.models import Footnote, ParsedPage, SourceTextBlock
from app.core.normalizer import join_line_text, normalize_text

_NOTE_START = re.compile(
    r"^\s*(?P<label>(?:\[\s*\d+\s*\]|\d+|[†‡*]+|[⁰¹²³⁴⁵⁶⁷⁸⁹]+|[A-Za-z])"
    r"(?:[.)])?)(?:\s+|$)"
)
_NOTE_ZONE = 0.68


def extract_footnotes(
    page: ParsedPage,
    blocks: list[SourceTextBlock],
    body_size: float,
) -> tuple[list[SourceTextBlock], list[Footnote]]:
    """Separate ordered, multi-line notes from the page's body blocks."""
    ordered = sorted(
        blocks,
        key=lambda block: (block.bbox.y0, block.bbox.x0, block.block_index, block.line_index),
    )
    starts = [
        (index, match)
        for index, block in enumerate(ordered)
        if (match := _note_match(block, page, body_size)) is not None
    ]
    if not starts:
        return blocks, []

    consumed: set[str] = set()
    notes: list[Footnote] = []
    for ordinal, (start_index, match) in enumerate(starts, start=1):
        end_index = starts[ordinal][0] if ordinal < len(starts) else len(ordered)
        first = ordered[start_index]
        group = [first]
        for candidate in ordered[start_index + 1 : end_index]:
            if _continues_note(candidate, group[-1], page):
                group.append(candidate)
        consumed.update(block.id for block in group)
        notes.append(_build_footnote(group, match.group("label"), page.number, ordinal, match))

    body_blocks = [block for block in blocks if block.id not in consumed]
    return body_blocks, notes


def as_footnote(block: SourceTextBlock, page: ParsedPage, body_size: float) -> Footnote | None:
    """Recognize one small, labeled bottom-of-page note."""
    match = _note_match(block, page, body_size)
    if match is None:
        return None
    return _build_footnote([block], match.group("label"), page.number, 1, match)


def _note_match(
    block: SourceTextBlock, page: ParsedPage, body_size: float
) -> re.Match[str] | None:
    if block.bbox.y0 < page.height * _NOTE_ZONE:
        return None
    if body_size > 0 and block.font_size > body_size:
        return None
    match = _NOTE_START.match(block.text)
    if match is None or not normalize_text(block.text[match.end() :]):
        return None
    return match


def _continues_note(
    block: SourceTextBlock, previous: SourceTextBlock, page: ParsedPage
) -> bool:
    if block.bbox.y0 < page.height * _NOTE_ZONE:
        return False
    gap = block.bbox.y0 - previous.bbox.y1
    maximum_gap = max(previous.font_size, block.font_size) * 1.9
    if gap < -previous.font_size * 0.25 or gap > maximum_gap:
        return False
    return abs(block.bbox.x0 - previous.bbox.x0) <= max(30.0, page.width * 0.12)


def _build_footnote(
    blocks: list[SourceTextBlock],
    label: str,
    page_number: int,
    ordinal: int,
    match: re.Match[str],
) -> Footnote:
    text = blocks[0].text[match.end() :]
    bbox = blocks[0].bbox
    for block in blocks[1:]:
        text = join_line_text(text, block.text)
        bbox = bbox.union(block.bbox)
    return Footnote(
        identifier=f"note-{page_number}-{ordinal}",
        text=normalize_text(text),
        bbox=bbox,
        page_number=page_number,
        label=label,
    )
