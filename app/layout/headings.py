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
        sizes = [round(block.font_size * 2) / 2 for block in blocks if block.font_size > 0]
        self.body_size = Counter(sizes).most_common(1)[0][0] if sizes else 10.0
        self._heading_sizes = sorted(
            {size for size in sizes if size >= self.body_size * self._config.minimum_relative_size},
            reverse=True,
        )

    def is_heading(self, block: SourceTextBlock) -> bool:
        """Favor false negatives over turning ordinary body text into headings."""
        text = block.text.strip()
        if not text or len(text) > self._config.maximum_length or text.endswith((".", ";", ",")):
            return False
        numbered = bool(_NUMBERED.match(text))
        upper_case = len(text) > 3 and text.isupper()
        size_signal = block.font_size >= self.body_size * self._config.minimum_relative_size
        score = int(size_signal) * 2 + int(block.bold) + int(numbered) * 2 + int(upper_case)
        if block.font_size >= self.body_size * 1.45:
            score += 1
        return score >= 2 and (size_signal or numbered or (block.bold and upper_case))

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
