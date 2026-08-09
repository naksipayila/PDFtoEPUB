"""Conservative bottom-of-page footnote recognition."""

from __future__ import annotations

import re

from app.core.models import Footnote, ParsedPage, SourceTextBlock

_NOTE_START = re.compile(r"^\s*(\d+|[†‡*])(?:[.)])?\s+")


def as_footnote(block: SourceTextBlock, page: ParsedPage, body_size: float) -> Footnote | None:
    """Recognize small, numbered edge notes while leaving uncertain text intact."""
    if block.bbox.y0 < page.height * 0.73 or block.font_size > body_size * 0.95:
        return None
    match = _NOTE_START.match(block.text)
    if not match:
        return None
    return Footnote(
        identifier=f"note-{block.page_number}-{match.group(1)}",
        text=block.text[match.end() :].strip(),
        bbox=block.bbox,
        page_number=block.page_number,
    )
