"""Dynamic, multi-signal heading detection."""

from __future__ import annotations

import re
from collections import Counter

from app.core.config import HeadingDetectionConfig
from app.core.models import SourceTextBlock

_NUMBERED = re.compile(
    r"^(?:chapter|part|b[oö]l[üu]m)\s+[\divxlcdm]+\b|^\d+(?:\.\d+){0,3}\.?\s+", re.IGNORECASE
)


class HeadingDetector:
    """Classify headings using size, styling, text form, and document distribution."""

    def __init__(
        self, blocks: list[SourceTextBlock], config: HeadingDetectionConfig | None = None
    ) -> None:
        self._config = config or HeadingDetectionConfig()
        self._blocks_by_page: dict[int, list[SourceTextBlock]] = {}
        for block in blocks:
            self._blocks_by_page.setdefault(block.page_number, []).append(block)
        sizes = [round(block.font_size * 2) / 2 for block in blocks if block.font_size > 0]
        counts = Counter(sizes)
        maximum_count = max(counts.values(), default=0)
        self.body_size = (
            min(size for size, count in counts.items() if count == maximum_count)
            if maximum_count
            else 10.0
        )
        self._heading_sizes = sorted(
            {size for size in sizes if size >= self.body_size * self._config.minimum_relative_size},
            reverse=True,
        )

    def is_heading(self, block: SourceTextBlock) -> bool:
        """Favor false negatives over turning ordinary body text into headings."""
        text = block.text.strip()
        if (
            not text
            or len(text) > self._config.maximum_length
        ):
            return False
        numbered = bool(_NUMBERED.match(text))
        upper_case = len(text) > 3 and text.isupper()
        size_signal = block.font_size >= self.body_size * self._config.minimum_relative_size
        medium_size = block.font_size >= self.body_size * 1.25
        strong_size = block.font_size >= self.body_size * 1.3
        isolated = self._is_isolated(block)
        if numbered:
            return size_signal and (block.bold or strong_size or upper_case or isolated)
        if upper_case:
            return medium_size and (block.bold or strong_size or isolated)
        if block.bold:
            return medium_size and (strong_size or isolated)
        if not (strong_size or (medium_size and isolated)):
            return False
        return not text.endswith((".", ";", ",", "-", "\u00ad")) or strong_size

    def _is_isolated(self, block: SourceTextBlock) -> bool:
        page_blocks = sorted(
            self._blocks_by_page.get(block.page_number, []),
            key=lambda candidate: candidate.bbox.y0,
        )
        index = next(
            (index for index, candidate in enumerate(page_blocks) if candidate.id == block.id),
            None,
        )
        if index is None:
            return False
        minimum_gap = max(block.font_size, self.body_size) * 0.6
        previous_gap = (
            block.bbox.y0 - page_blocks[index - 1].bbox.y1 if index > 0 else minimum_gap
        )
        next_gap = (
            page_blocks[index + 1].bbox.y0 - block.bbox.y1
            if index + 1 < len(page_blocks)
            else minimum_gap
        )
        return previous_gap >= minimum_gap and next_gap >= minimum_gap

    def level(self, block: SourceTextBlock) -> int:
        """Map large styles to h1-h4 in descending document-relative order."""
        if not self._heading_sizes:
            return 2
        for index, size in enumerate(self._heading_sizes[: self._config.max_levels], start=1):
            if block.font_size >= size - 0.25:
                return index
        return min(self._config.max_levels, len(self._heading_sizes) + 1)


def is_chapter_heading(heading: SourceTextBlock, level: int) -> bool:
    """Recognize chapter starts while retaining a sensible h1 fallback."""
    return level == 1 or bool(_NUMBERED.match(heading.text.strip()))
