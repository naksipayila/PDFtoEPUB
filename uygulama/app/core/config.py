"""Central conversion options and deterministic heuristic thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.models import DocumentMetadata


@dataclass(slots=True)
class ConversionOptions:
    use_ocr: bool = True
    ocr_language: str = "tur"
    include_images: bool = True
    optimize_images: bool = True
    remove_page_numbers: bool = True
    remove_headers_footers: bool = True
    detect_tables: bool = True
    detect_columns: bool = True
    detect_chapters: bool = True
    preserve_footnotes: bool = True
    extract_cover: bool = True
    css_style_mode: str = "reader"
    metadata: DocumentMetadata | None = None
    pdf_password: str | None = None
    debug_output_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class HeadingDetectionConfig:
    minimum_relative_size: float = 1.15
    maximum_length: int = 130
    max_levels: int = 4


@dataclass(frozen=True, slots=True)
class ColumnDetectionConfig:
    minimum_blocks_per_column: int = 2
    x_cluster_distance_ratio: float = 0.12
    minimum_column_gap_ratio: float = 0.14
    maximum_columns: int = 3


@dataclass(frozen=True, slots=True)
class ParagraphMergeConfig:
    max_line_gap_factor: float = 1.85
    indentation_tolerance_factor: float = 2.5


@dataclass(frozen=True, slots=True)
class HeaderFooterConfig:
    edge_ratio: float = 0.145
    style_detection_edge_ratio: float = 0.075
    minimum_repeated_pages: int = 2
    minimum_frequency: float = 0.2
    style_detection_minimum_frequency: float = 0.2
