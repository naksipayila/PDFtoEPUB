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
    language: str = "tr"
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
    confidence: float | None = None


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
    role: str = "inline"


@dataclass(frozen=True, slots=True)
class ConversionIssue:
    """A structured quality or content-retention event from conversion."""

    code: str
    message: str
    severity: str = "warning"
    stage: str = "conversion"
    page_number: int | None = None

    def display(self) -> str:
        page = f"Sayfa {self.page_number}: " if self.page_number is not None else ""
        return f"{page}{self.message}"


@dataclass(slots=True)
class ParsedPage:
    """Raw, coordinate-preserving information from one PDF page."""

    number: int
    width: float
    height: float
    text_blocks: list[SourceTextBlock] = field(default_factory=list)
    images: list[PositionedImage] = field(default_factory=list)
    ocr_used: bool = False
    text_source: str = "none"
    ocr_confidence: float | None = None
    issues: list[ConversionIssue] = field(default_factory=list)


@dataclass(slots=True)
class Paragraph:
    text: str
    bbox: BoundingBox | None = None
    page_number: int | None = None
    source_pages: tuple[int, ...] = ()


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


@dataclass(frozen=True, slots=True)
class PrintedTocEntry:
    title: str
    page_label: str
    level: int = 0


@dataclass(slots=True)
class PrintedTocBlock:
    entries: list[PrintedTocEntry]
    bbox: BoundingBox | None = None
    page_number: int | None = None


@dataclass(slots=True)
class Footnote:
    identifier: str
    text: str
    bbox: BoundingBox | None = None
    page_number: int | None = None
    label: str = ""


ContentElement: TypeAlias = (
    Paragraph | Heading | ImageBlock | ListBlock | TableBlock | PrintedTocBlock | Footnote
)


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
    native_text_pages: int = 0
    low_confidence_ocr_pages: int = 0
    image_fallback_pages: int = 0
    issues: list[ConversionIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    toc_entries_detected: int = 0

    def add_issue(self, issue: ConversionIssue) -> None:
        """Record structured quality information while preserving warning compatibility."""
        self.issues.append(issue)
        if issue.severity in {"warning", "error"}:
            self.warnings.append(issue.display())

    def summary(self) -> str:
        return (
            f"İşlenen sayfa: {self.pages_processed}\n"
            f"Atlanan metinsiz sayfa: {self.pages_skipped}\n"
            f"Algılanan bölüm: {self.chapters_detected}\n"
            f"Algılanan paragraf: {self.paragraphs_detected}\n"
            f"Algılanan başlık: {self.headings_detected}\n"
            f"Ayıklanan görsel: {self.images_extracted}\n"
            f"Algılanan tablo: {self.tables_detected}\n"
            f"Düzenlenen içindekiler kaydı: {self.toc_entries_detected}\n"
            f"Algılanan dipnot: {self.footnotes_detected}\n"
            f"Kaldırılan üst/alt bilgi: {self.headers_removed}\n"
            f"Kaldırılan sayfa numarası: {self.page_numbers_removed}\n"
            f"Yerel metni kullanılan sayfa: {self.native_text_pages}\n"
            f"OCR uygulanan sayfa: {self.ocr_pages}\n"
            f"Düşük güvenli OCR sayfası: {self.low_confidence_ocr_pages}\n"
            f"Görsel olarak korunan sayfa: {self.image_fallback_pages}\n"
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
