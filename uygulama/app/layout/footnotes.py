"""Conservative bottom-of-page footnote recognition."""

from __future__ import annotations

import re

from app.core.models import Footnote, ParsedPage, SourceTextBlock
from app.core.normalizer import normalize_text

_NOTE_START = re.compile(r"^\s*(\d+|[†‡*])(?:[.)])?\s+")


def as_footnote(block: SourceTextBlock, page: ParsedPage, body_size: float) -> Footnote | None:
    """Recognize small, numbered edge notes while leaving uncertain text intact."""
    if block.bbox.y0 < page.height * 0.73 or block.font_size > body_size * 0.95:
        return None
    if block.bbox.x0 <= page.width * 0.12 and block.bbox.width >= page.width * 0.6:
        return None
    match = _NOTE_START.match(block.text)
    if not match:
        return None
    return Footnote(
        identifier=f"note-{block.page_number}-{match.group(1)}",
        text=normalize_text(block.text[match.end() :]),
        bbox=block.bbox,
        page_number=block.page_number,
    )
