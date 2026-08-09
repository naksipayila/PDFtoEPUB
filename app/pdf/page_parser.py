"""Coordinate-preserving extraction of text spans and images from PDF pages."""

from __future__ import annotations

import logging

import pymupdf as fitz

from app.core.models import BoundingBox, ParsedPage, SourceTextBlock
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
        """Extract text at line granularity, falling back to OCR for image-only pages."""
        rectangle = page.rect
        blocks = self._extract_text(page, page_number)
        ocr_used = False
        if not blocks and use_ocr and self._ocr_engine and self._ocr_engine.available():
            blocks = self._ocr_engine.extract_page(page, page_number, ocr_language)
            ocr_used = bool(blocks)
        elif not blocks and use_ocr:
            LOGGER.warning("Page %s has no text but Tesseract OCR is unavailable", page_number)

        return ParsedPage(
            number=page_number,
            width=rectangle.width,
            height=rectangle.height,
            text_blocks=blocks,
            images=self._image_extractor.extract_page(page, page_number) if include_images else [],
            ocr_used=ocr_used,
        )

    @staticmethod
    def _extract_text(page: fitz.Page, page_number: int) -> list[SourceTextBlock]:
        result: list[SourceTextBlock] = []
        page_dict = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT)
        for block_index, block in enumerate(page_dict.get("blocks", [])):
            if block.get("type") != 0:
                continue
            for line_index, line in enumerate(block.get("lines", [])):
                spans = line.get("spans", [])
                text = normalize_text("".join(span.get("text", "") for span in spans))
                if not text or not spans:
                    continue
                bbox = BoundingBox(*line["bbox"])
                primary_span = max(spans, key=lambda item: len(item.get("text", "")))
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
