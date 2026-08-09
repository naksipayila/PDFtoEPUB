"""Optional local Tesseract OCR adapter."""

from __future__ import annotations

import io
import logging

import pymupdf as fitz
from PIL import Image, ImageEnhance, ImageOps

from app.core.models import BoundingBox, SourceTextBlock
from app.core.normalizer import normalize_text

LOGGER = logging.getLogger(__name__)


class OcrEngine:
    """Performs OCR only when Tesseract is installed and a page lacks text."""

    def available(self) -> bool:
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
        except (ImportError, OSError, RuntimeError):
            return False
        return True

    def extract_page(
        self, page: fitz.Page, page_number: int, language: str
    ) -> list[SourceTextBlock]:
        """Render and OCR a page, returning conservative line-level blocks."""
        import pytesseract

        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        image = self._preprocess(image)
        ocr_data = pytesseract.image_to_data(
            image,
            lang=language,
            output_type=pytesseract.Output.DICT,
            config="--psm 3",
        )
        scale = 2.0
        lines: dict[tuple[int, int, int], list[int]] = {}
        for index, text in enumerate(ocr_data["text"]):
            if normalize_text(text):
                key = (
                    ocr_data["block_num"][index],
                    ocr_data["par_num"][index],
                    ocr_data["line_num"][index],
                )
                lines.setdefault(key, []).append(index)

        result: list[SourceTextBlock] = []
        for line_index, indexes in enumerate(lines.values()):
            text = normalize_text(" ".join(ocr_data["text"][index] for index in indexes))
            if not text:
                continue
            x0 = min(ocr_data["left"][index] for index in indexes) / scale
            y0 = min(ocr_data["top"][index] for index in indexes) / scale
            x1 = (
                max(ocr_data["left"][index] + ocr_data["width"][index] for index in indexes) / scale
            )
            y1 = (
                max(ocr_data["top"][index] + ocr_data["height"][index] for index in indexes) / scale
            )
            result.append(
                SourceTextBlock(
                    id=f"ocr-{page_number}-{line_index}",
                    text=text,
                    bbox=BoundingBox(x0, y0, x1, y1),
                    page_number=page_number,
                    font_size=max(8.0, y1 - y0),
                    font_name="OCR",
                    block_index=line_index,
                )
            )
        LOGGER.info("OCR extracted %s lines from page %s", len(result), page_number)
        return result

    @staticmethod
    def _preprocess(image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        return ImageEnhance.Contrast(grayscale).enhance(1.5)
