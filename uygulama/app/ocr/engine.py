"""Optional local Tesseract OCR adapter."""

from __future__ import annotations

import io
import logging
import os

import pymupdf as fitz
from PIL import Image, ImageOps

from app.core.models import BoundingBox, SourceTextBlock
from app.core.normalizer import normalize_text

LOGGER = logging.getLogger(__name__)
OCR_DPI = 300.0


class OcrEngine:
    """Run local Tesseract OCR for textless and scanned pages."""

    def available(self, language: str | None = None) -> bool:
        try:
            pytesseract = self._tesseract()
            pytesseract.get_tesseract_version()
        except (ImportError, OSError, RuntimeError):
            return False
        if not language:
            return True
        try:
            return language in pytesseract.get_languages(config="")
        except pytesseract.TesseractError:
            return False

    def extract_page(
        self, page: fitz.Page, page_number: int, language: str
    ) -> list[SourceTextBlock]:
        """Render and OCR a page, returning conservative line-level blocks."""
        pytesseract = self._tesseract()

        scale = OCR_DPI / 72.0
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        image = self._preprocess(image)
        ocr_data = pytesseract.image_to_data(
            image,
            lang=language,
            output_type=pytesseract.Output.DICT,
            config=f"--oem 1 --psm 3 --dpi {int(OCR_DPI)}",
        )
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
            text = _join_ocr_words(ocr_data, indexes)
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
    def _tesseract():
        import pytesseract

        command = os.environ.get("PDFTOEPUB_TESSERACT")
        if command:
            pytesseract.pytesseract.tesseract_cmd = command
        return pytesseract

    @staticmethod
    def _preprocess(image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        return ImageOps.autocontrast(grayscale)


def _join_ocr_words(ocr_data: dict[str, list], indexes: list[int]) -> str:
    """Join OCR tokens using their visual gap instead of forcing a space everywhere."""
    ordered = sorted(indexes, key=lambda index: (ocr_data["left"][index], index))
    tokens = [
        (
            normalize_text(ocr_data["text"][index]),
            float(ocr_data["left"][index]),
            float(ocr_data["left"][index] + ocr_data["width"][index]),
            float(ocr_data["height"][index]),
        )
        for index in ordered
    ]
    tokens = [token for token in tokens if token[0]]
    if not tokens:
        return ""

    line_height = max(token[3] for token in tokens)
    join_limit = max(1.0, line_height * 0.12)

    text = tokens[0][0]
    for previous, current in zip(tokens, tokens[1:], strict=False):
        previous_text = previous[0]
        current_text = current[0]
        gap = max(0.0, current[1] - previous[2])
        needs_space = gap > join_limit
        if previous_text[-1:] in "([{\"'“‘" or current_text[:1] in ".,;:!?)]}%»”’":
            needs_space = False
        text += (" " if needs_space else "") + current_text
    return normalize_text(text)
