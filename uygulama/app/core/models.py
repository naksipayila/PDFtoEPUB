"""Format-neutral document model used between PDF parsing and EPUB creation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """A rectangle in PDF point coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2

    def union(self, other: BoundingBox) -> BoundingBox:
        return BoundingBox(
            min(self.x0, other.x0),
            min(self.y0, other.y0),
            max(self.x1, other.x1),
            max(self.y1, other.y1),
        )


@dataclass(slots=True)
class DocumentMetadata:
    """Normalized publication metadata."""

    title: str = "Untitled"
    author: str = ""
    language: str = "en"
    publisher: str = ""
    description: str = ""
    isbn: str = ""
    subject: str = ""


@dataclass(slots=True)
class SourceTextBlock:
    """A single visual text line extracted from a PDF page."""

    id: str
    text: str
    bbox: BoundingBox
    page_number: int
    font_size: float
    font_name: str
    bold: bool = False
    italic: bool = False
    color: int | None = None
    block_index: int = 0
    line_index: int = 0


@dataclass(slots=True)
class ImageAsset:
    """A deduplicated extracted image held on disk for streaming-friendly processing."""

    id: str
    file_path: Path
    media_type: str
    extension: str
    digest: str


@dataclass(slots=True)
class PositionedImage:
    """A reference to an image at one visual position."""

    asset_id: str
    bbox: BoundingBox
    page_number: int


@dataclass(slots=True)
class ParsedPage:
    """Raw, coordinate-preserving information from one PDF page."""

    number: int
    width: float
    height: float
    text_blocks: list[SourceTextBlock] = field(default_factory=list)
    images: list[PositionedImage] = field(default_factory=list)
    ocr_used: bool = False


@dataclass(slots=True)
class Paragraph:
    text: str
    bbox: BoundingBox | None = None
    page_number: int | None = None


@dataclass(slots=True)
class Heading:
    text: str
    level: int
    bbox: BoundingBox | None = None
    page_number: int | None = None


@dataclass(slots=True)
class ImageBlock:
    asset_id: str
    caption: str = ""
    alt_text: str = ""
    bbox: BoundingBox | None = None
    page_number: int | None = None


@dataclass(slots=True)
class ListBlock:
    items: list[str]
    ordered: bool
    bbox: BoundingBox | None = None
    page_number: int | None = None


@dataclass(slots=True)
class TableBlock:
    rows: list[list[str]]
    bbox: BoundingBox | None = None
    page_number: int | None = None


@dataclass(slots=True)
class Footnote:
    identifier: str
    text: str
    bbox: BoundingBox | None = None
    page_number: int | None = None
    label: str = ""


ContentElement: TypeAlias = Paragraph | Heading | ImageBlock | ListBlock | TableBlock | Footnote


@dataclass(slots=True)
class Chapter:
    title: str
    identifier: str
    elements: list[ContentElement] = field(default_factory=list)
    level: int = 1


@dataclass(slots=True)
class SemanticDocument:
    """The semantic, source-independent representation written as EPUB."""

    metadata: DocumentMetadata
    chapters: list[Chapter] = field(default_factory=list)
    assets: dict[str, ImageAsset] = field(default_factory=dict)
    cover_asset_id: str | None = None


@dataclass(slots=True)
class ConversionReport:
    pages_processed: int = 0
    pages_skipped: int = 0
    chapters_detected: int = 0
    paragraphs_detected: int = 0
    headings_detected: int = 0
    images_extracted: int = 0
    tables_detected: int = 0
    footnotes_detected: int = 0
    headers_removed: int = 0
    page_numbers_removed: int = 0
    ocr_pages: int = 0
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"İşlenen sayfa: {self.pages_processed}\n"
            f"Atlanan metinsiz sayfa: {self.pages_skipped}\n"
            f"Algılanan bölüm: {self.chapters_detected}\n"
            f"Algılanan paragraf: {self.paragraphs_detected}\n"
            f"Algılanan başlık: {self.headings_detected}\n"
            f"Ayıklanan görsel: {self.images_extracted}\n"
            f"Algılanan tablo: {self.tables_detected}\n"
            f"Algılanan dipnot: {self.footnotes_detected}\n"
            f"Kaldırılan üst/alt bilgi: {self.headers_removed}\n"
            f"Kaldırılan sayfa numarası: {self.page_numbers_removed}\n"
            f"OCR uygulanan sayfa: {self.ocr_pages}\n"
            f"Uyarı: {len(self.warnings)}"
        )


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    stage: str
    message: str
    current: int = 0
    total: int = 0

    @property
    def percentage(self) -> int:
        if self.total <= 0:
            return 0
        return min(100, int(self.current * 100 / self.total))
