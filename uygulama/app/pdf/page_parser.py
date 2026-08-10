"""Coordinate-preserving extraction of text spans and images from PDF pages."""

from __future__ import annotations

import logging
from statistics import median

import pymupdf as fitz

from app.core.errors import ConversionError
from app.core.models import BoundingBox, ParsedPage, PositionedImage, SourceTextBlock
from app.core.normalizer import normalize_text
from app.ocr.engine import OcrEngine
from app.pdf.images import ImageExtractor

LOGGER = logging.getLogger(__name__)


class PageParser:
    """Convert PyMuPDF page dictionaries into source-independent raw blocks."""

    def __init__(
        self, image_extractor: ImageExtractor, ocr_engine: OcrEngine | None = None
    ) -> None:
        self._image_extractor = image_extractor
        self._ocr_engine = ocr_engine

    def parse(
        self,
        page: fitz.Page,
        page_number: int,
        use_ocr: bool,
        ocr_language: str,
        include_images: bool = True,
    ) -> ParsedPage:
        """Extract text and replace unreliable hidden OCR on scanned pages."""
        rectangle = page.rect
        images = self._image_extractor.extract_page(page, page_number) if include_images else []
        blocks = self._extract_text(page, page_number)
        ocr_used = False
        is_scanned_page = _page_has_background_image(page, rectangle.width, rectangle.height)
        ocr_available = bool(
            use_ocr and self._ocr_engine and self._ocr_engine.available(ocr_language)
        )
        if use_ocr and (not blocks or is_scanned_page):
            if not ocr_available:
                if is_scanned_page:
                    raise ConversionError(
                        f"Sayfa {page_number} taranmış ancak Türkçe OCR kullanılamıyor. "
                        "Tesseract ve tur.traineddata kurulumunu kontrol edin."
                    )
                LOGGER.warning("Page %s has no usable OCR language data", page_number)
            else:
                try:
                    ocr_blocks = self._ocr_engine.extract_page(page, page_number, ocr_language)
                except (OSError, RuntimeError) as error:
                    if is_scanned_page:
                        _fallback_to_page_image(
                            images, rectangle.width, rectangle.height, page_number
                        )
                        blocks = []
                        LOGGER.warning(
                            "OCR failed on page %s; retaining the page image: %s",
                            page_number,
                            error,
                        )
                    else:
                        LOGGER.warning("OCR failed on page %s: %s", page_number, error)
                else:
                    if ocr_blocks:
                        blocks = ocr_blocks
                        ocr_used = True
                    elif is_scanned_page:
                        _fallback_to_page_image(
                            images, rectangle.width, rectangle.height, page_number
                        )
                        blocks = []
                        LOGGER.warning(
                            "OCR produced no text on page %s; retaining the page image",
                            page_number,
                        )

        if blocks:
            images = [
                image
                for image in images
                if not _is_page_background(image, rectangle.width, rectangle.height)
            ]

        return ParsedPage(
            number=page_number,
            width=rectangle.width,
            height=rectangle.height,
            text_blocks=blocks,
            images=images,
            ocr_used=ocr_used,
        )

    @staticmethod
    def _extract_text(page: fitz.Page, page_number: int) -> list[SourceTextBlock]:
        result: list[SourceTextBlock] = []
        page_dict = page.get_text("rawdict", flags=fitz.TEXTFLAGS_RAWDICT)
        for block_index, block in enumerate(page_dict.get("blocks", [])):
            if block.get("type") != 0:
                continue
            for line_index, line in enumerate(block.get("lines", [])):
                spans = line.get("spans", [])
                text = _line_text(line)
                if not text or not spans:
                    continue
                bbox = BoundingBox(*line["bbox"])
                primary_span = max(spans, key=_span_length)
                font_name = str(primary_span.get("font", "Unknown"))
                flags = int(primary_span.get("flags", 0))
                result.append(
                    SourceTextBlock(
                        id=f"p{page_number}-b{block_index}-l{line_index}",
                        text=text,
                        bbox=bbox,
                        page_number=page_number,
                        font_size=float(primary_span.get("size", 10.0)),
                        font_name=font_name,
                        bold="bold" in font_name.lower() or bool(flags & 16),
                        italic="italic" in font_name.lower() or bool(flags & 2),
                        color=int(primary_span.get("color", 0)),
                        block_index=block_index,
                        line_index=line_index,
                    )
                )
        return result


def _span_length(span: dict) -> int:
    return len(span.get("text", "")) or len(span.get("chars", []))


def _is_page_background(image: PositionedImage, page_width: float, page_height: float) -> bool:
    """Ignore rasterized page backgrounds when a text layer is available."""
    bbox = image.bbox
    horizontal_margin = max(2.0, page_width * 0.02)
    vertical_margin = max(2.0, page_height * 0.02)
    return (
        bbox.x0 <= horizontal_margin
        and bbox.y0 <= vertical_margin
        and bbox.x1 >= page_width - horizontal_margin
        and bbox.y1 >= page_height - vertical_margin
    )


def _page_has_background_image(page: fitz.Page, page_width: float, page_height: float) -> bool:
    """Identify scanned pages that may contain a low-quality hidden text layer."""
    horizontal_margin = max(2.0, page_width * 0.02)
    vertical_margin = max(2.0, page_height * 0.02)
    for image_info in page.get_images(full=True):
        for rectangle in page.get_image_rects(image_info[0]):
            if (
                rectangle.x0 <= horizontal_margin
                and rectangle.y0 <= vertical_margin
                and rectangle.x1 >= page_width - horizontal_margin
                and rectangle.y1 >= page_height - vertical_margin
            ):
                return True
    return False


def _fallback_to_page_image(
    images: list[PositionedImage],
    page_width: float,
    page_height: float,
    page_number: int,
) -> None:
    """Drop an unreliable text layer only when the scanned page image is available."""
    if any(_is_page_background(image, page_width, page_height) for image in images):
        return
    raise ConversionError(
        f"Sayfa {page_number} taranmış; OCR kullanılamıyor ve güvenilir sayfa görseli bulunamadı."
    )


def _line_text(line: dict) -> str:
    """Rebuild native text from character geometry without inventing word gaps."""
    spans = line.get("spans", [])
    chars = [char for span in spans for char in span.get("chars", [])]
    if not chars:
        return normalize_text("".join(span.get("text", "") for span in spans))

    space_widths = [
        char["bbox"][2] - char["bbox"][0]
        for char in chars
        if char.get("c", "").isspace() and "bbox" in char
    ]
    font_size = max((float(span.get("size", 10.0)) for span in spans), default=10.0)
    space_width = median(space_widths) if space_widths else font_size * 0.25
    gap_threshold = max(0.5, space_width * 0.6)

    result: list[str] = []
    previous = None
    for char in chars:
        value = str(char.get("c", ""))
        if not value:
            continue
        bbox = char.get("bbox")
        if value.isspace():
            result.append(" ")
        elif previous is not None and bbox is not None:
            gap = bbox[0] - previous[2]
            if gap > gap_threshold:
                result.append(" ")
        result.append(value)
        if bbox is not None:
            previous = bbox
    return normalize_text("".join(result))
