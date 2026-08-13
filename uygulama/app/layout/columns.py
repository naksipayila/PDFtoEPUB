"""Column detection and reading-order resolution for visual text lines."""

from __future__ import annotations

from statistics import median

from app.core.config import ColumnDetectionConfig
from app.core.models import ParsedPage, SourceTextBlock


class ReadingOrderResolver:
    """Resolve one-to-three column pages without relying on PDF stream order."""

    def __init__(self, config: ColumnDetectionConfig | None = None) -> None:
        self._config = config or ColumnDetectionConfig()

    def resolve(self, page: ParsedPage) -> list[SourceTextBlock]:
        """Return text in human reading order, keeping full-width bands in place."""
        blocks = list(page.text_blocks)
        if len(blocks) < self._config.minimum_blocks_per_column * 2:
            return self._sort_vertically(blocks)

        clusters = self.detect_columns(blocks, page.width)
        if len(clusters) < 2:
            return self._sort_vertically(blocks)

        boundary = (
            max(block.bbox.x0 for block in clusters[0])
            + min(block.bbox.x0 for block in clusters[1])
        ) / 2
        full_width = [
            block
            for block in blocks
            if block.bbox.x0 < boundary < block.bbox.x1 and block.bbox.width >= page.width * 0.35
        ]
        column_blocks = [block for block in blocks if block not in full_width]
        if not full_width:
            return self._sort_columns(column_blocks, page.width)

        # Full-width titles/rules delimit independent column regions on mixed-layout pages.
        ordered: list[SourceTextBlock] = []
        delimiters = self._sort_vertically(full_width)
        cursor = float("-inf")
        for delimiter in delimiters:
            region = [
                block for block in column_blocks if cursor <= block.bbox.y0 < delimiter.bbox.y0
            ]
            ordered.extend(self._sort_columns(region, page.width))
            ordered.append(delimiter)
            cursor = delimiter.bbox.y1
        ordered.extend(
            self._sort_columns(
                [block for block in column_blocks if block.bbox.y0 >= cursor], page.width
            )
        )
        return ordered

    def detect_columns(
        self, blocks: list[SourceTextBlock], page_width: float
    ) -> list[list[SourceTextBlock]]:
        """Cluster left edges where their separation represents a meaningful gutter."""
        if not blocks:
            return []
        tolerance = page_width * self._config.x_cluster_distance_ratio
        ordered = sorted(blocks, key=lambda block: block.bbox.x0)
        clusters: list[list[SourceTextBlock]] = [[ordered[0]]]
        for block in ordered[1:]:
            current = clusters[-1]
            if block.bbox.x0 - median(item.bbox.x0 for item in current) > tolerance:
                clusters.append([block])
            else:
                current.append(block)

        candidates = [
            cluster
            for cluster in clusters
            if len(cluster) >= self._config.minimum_blocks_per_column
        ]
        if not 2 <= len(candidates) <= self._config.maximum_columns:
            return []
        starts = [median(item.bbox.x0 for item in cluster) for cluster in candidates]
        if min(right - left for left, right in zip(starts, starts[1:], strict=False)) < (
            page_width * self._config.minimum_column_gap_ratio
        ):
            return []
        return candidates

    @staticmethod
    def _sort_vertically(blocks: list[SourceTextBlock]) -> list[SourceTextBlock]:
        return sorted(blocks, key=lambda block: (round(block.bbox.y0, 1), block.bbox.x0))

    def _sort_columns(
        self, blocks: list[SourceTextBlock], page_width: float
    ) -> list[SourceTextBlock]:
        clusters = self.detect_columns(blocks, page_width)
        if not clusters:
            return self._sort_vertically(blocks)
        clustered_ids = {block.id for cluster in clusters for block in cluster}
        unmatched = [block for block in blocks if block.id not in clustered_ids]
        if not unmatched:
            return [block for cluster in clusters for block in self._sort_vertically(cluster)]

        starts = [median(block.bbox.x0 for block in cluster) for cluster in clusters]
        assigned = [list(cluster) for cluster in clusters]
        for block in unmatched:
            index = min(
                range(len(starts)),
                key=lambda candidate: abs(block.bbox.x0 - starts[candidate]),
            )
            assigned[index].append(block)
        return [block for cluster in assigned for block in self._sort_vertically(cluster)]
