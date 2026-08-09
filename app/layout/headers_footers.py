"""Repeated header, footer, and page number detection."""

from __future__ import annotations

import re
from collections import defaultdict

from app.core.config import HeaderFooterConfig
from app.core.models import ParsedPage, SourceTextBlock

_PAGE_NUMBER = re.compile(r"^(?:page\s*)?[-–—]?\s*\d+\s*[-–—]?$", re.IGNORECASE)


def repeated_header_footer_ids(
    pages: list[ParsedPage], config: HeaderFooterConfig | None = None
) -> set[str]:
    """Find repeated edge text by normalized text and positional frequency."""
    config = config or HeaderFooterConfig()
    if len(pages) < config.minimum_repeated_pages:
        return set()
    occurrences: dict[str, list[SourceTextBlock]] = defaultdict(list)
    for page in pages:
        for block in page.text_blocks:
            if block.bbox.y0 <= page.height * config.edge_ratio or block.bbox.y1 >= page.height * (
                1 - config.edge_ratio
            ):
                normalized = re.sub(r"\s+", " ", block.text).strip().casefold()
                if normalized and not _PAGE_NUMBER.match(normalized):
                    occurrences[normalized].append(block)

    threshold = max(config.minimum_repeated_pages, int(len(pages) * config.minimum_frequency))
    return {
        block.id for blocks in occurrences.values() if len(blocks) >= threshold for block in blocks
    }


def is_page_number(block: SourceTextBlock, page: ParsedPage) -> bool:
    """Restrict page-number removal to conventional edge-positioned labels."""
    at_edge = block.bbox.y0 <= page.height * 0.14 or block.bbox.y1 >= page.height * 0.86
    return at_edge and bool(_PAGE_NUMBER.match(block.text.strip()))
