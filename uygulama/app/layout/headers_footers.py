"""Repeated header, footer, and page number detection."""

from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from math import ceil
from statistics import median

from app.core.config import HeaderFooterConfig
from app.core.models import ParsedPage, SourceTextBlock
from app.core.normalizer import normalize_text

_PAGE_NUMBER = re.compile(r"^(?:page\s*)?[-–—]?\s*\d+\s*[-–—]?$", re.IGNORECASE)
_VARIABLE_NUMBER = re.compile(r"(?<!\w)\d+(?!\w)")


def repeated_header_footer_ids(
    pages: list[ParsedPage], config: HeaderFooterConfig | None = None
) -> set[str]:
    """Find repeated edge text, including headers with changing page numbers."""
    config = config or HeaderFooterConfig()
    if len(pages) < config.minimum_repeated_pages:
        return set()

    body_font_size = _body_font_size(pages)
    groups: list[tuple[str, str, list[SourceTextBlock], set[int]]] = []
    style_groups: dict[
        tuple[str, int, int, str, bool, bool], tuple[list[SourceTextBlock], set[int]]
    ] = defaultdict(lambda: ([], set()))
    for page in pages:
        for block in page.text_blocks:
            zone = _edge_zone(block, page, config)
            normalized = normalize_text(block.text).casefold()
            if zone is None or not normalized or _PAGE_NUMBER.match(normalized):
                continue
            signature = _header_signature(normalized)
            if not signature:
                continue
            for group_zone, group_signature, blocks, page_numbers in groups:
                if group_zone == zone and _similar_signature(signature, group_signature):
                    blocks.append(block)
                    page_numbers.add(page.number)
                    break
            else:
                groups.append((zone, signature, [block], {page.number}))

            if (
                block.font_size < body_font_size
                and _is_in_style_detection_margin(block, page, zone, config)
            ):
                blocks, page_numbers = style_groups[_margin_style_key(block, page, zone)]
                blocks.append(block)
                page_numbers.add(page.number)

    threshold = max(
        config.minimum_repeated_pages,
        ceil(len(pages) * config.minimum_frequency),
    )
    repeated_ids = {
        block.id
        for _, _, blocks, page_numbers in groups
        if len(page_numbers) >= threshold
        for block in blocks
    }
    style_threshold = max(
        config.minimum_repeated_pages,
        ceil(len(pages) * config.style_detection_minimum_frequency),
    )
    repeated_ids.update(
        block.id
        for blocks, page_numbers in style_groups.values()
        if len(page_numbers) >= style_threshold
        for block in blocks
    )
    return repeated_ids


def _body_font_size(pages: list[ParsedPage]) -> float:
    font_sizes = [
        block.font_size
        for page in pages
        for block in page.text_blocks
        if normalize_text(block.text) and not _PAGE_NUMBER.match(normalize_text(block.text))
    ]
    return median(font_sizes) if font_sizes else 0


def _edge_zone(
    block: SourceTextBlock, page: ParsedPage, config: HeaderFooterConfig
) -> str | None:
    if block.bbox.y0 <= page.height * config.edge_ratio:
        return "top"
    if block.bbox.y1 >= page.height * (1 - config.edge_ratio):
        return "bottom"
    return None


def _is_in_style_detection_margin(
    block: SourceTextBlock, page: ParsedPage, zone: str, config: HeaderFooterConfig
) -> bool:
    if zone == "top":
        return block.bbox.y0 <= page.height * config.style_detection_edge_ratio
    return block.bbox.y1 >= page.height * (1 - config.style_detection_edge_ratio)


def _margin_style_key(
    block: SourceTextBlock, page: ParsedPage, zone: str
) -> tuple[str, int, int, str, bool, bool]:
    margin_offset = (
        block.bbox.y0 / page.height
        if zone == "top"
        else (page.height - block.bbox.y1) / page.height
    )
    return (
        zone,
        int(margin_offset / 0.02),
        round(block.font_size),
        block.font_name.casefold(),
        block.bold,
        block.italic,
    )


def _header_signature(value: str) -> str:
    """Normalize changing page numbers while retaining the header's text identity."""
    return _VARIABLE_NUMBER.sub("#", value).strip()


def _similar_signature(left: str, right: str) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < 8:
        return False
    return SequenceMatcher(None, left, right).ratio() >= 0.9


def is_page_number(block: SourceTextBlock, page: ParsedPage) -> bool:
    """Restrict page-number removal to conventional edge-positioned labels."""
    at_edge = block.bbox.y0 <= page.height * 0.14 or block.bbox.y1 >= page.height * 0.86
    return at_edge and bool(_PAGE_NUMBER.match(block.text.strip()))
