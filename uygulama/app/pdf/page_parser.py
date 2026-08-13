"""Coordinate-preserving extraction of text spans and images from PDF pages."""

from __future__ import annotations

import logging
import unicodedata
from statistics import median

import pymupdf as fitz

from app.core.errors import ConversionError
from app.core.models import (
    BoundingBox,
    ConversionIssue,
    ParsedPage,
    PositionedImage,
    SourceTextBlock,
)
from app.core.normalizer import normalize_text
from app.ocr.engine import OcrEngine, OcrPageResult
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
        preserve_unreadable_pages: bool = True,
        minimum_ocr_confidence: float = 70.0,
    ) -> ParsedPage:
        """Prefer trustworthy native text and OCR only missing or corrupt text layers."""
        rectangle = page.rect
        images = self._image_extractor.extract_page(page, page_number) if include_images else []
        blocks = self._extract_text(page, page_number)
        ocr_used = False
        ocr_confidence: float | None = None
        issues: list[ConversionIssue] = []
        text_source = "native" if blocks else "none"
        layout_width = rectangle.width
        layout_height = rectangle.height
        native_is_suspicious = _native_text_is_suspicious(blocks)
        has_background_image = _page_has_background_image(
            page, rectangle.width, rectangle.height
        )
        native_is_hidden = bool(
            blocks and has_background_image and not _has_meaningful_visible_text(page)
        )
        needs_ocr = use_ocr and (not blocks or native_is_suspicious or native_is_hidden)
        page_has_visual_content = _page_has_visual_content(page)
        ocr_available = bool(
            needs_ocr and self._ocr_engine and self._ocr_engine.available(ocr_language)
        )
        if needs_ocr:
            if not ocr_available:
                if (
                    page_has_visual_content
                    and preserve_unreadable_pages
                    and (not blocks or native_is_hidden)
                ):
                    images = self._retain_page_image(
                        page, page_number, images, rectangle.width, rectangle.height
                    )
                    blocks = []
                    text_source = "image"
                    issues.append(
                        ConversionIssue(
                            code="ocr_unavailable_page_image",
                            message=(
                                "OCR kullanılamadığı için içerik düzenlenebilir metin yerine "
                                "sayfa görseli olarak korundu."
                            ),
                            stage="ocr",
                            page_number=page_number,
                        )
                    )
                elif not blocks:
                    issues.append(
                        ConversionIssue(
                            code="ocr_unavailable",
                            message="Metin bulunamadı ve uygun OCR dil modeli kullanılamıyor.",
                            stage="ocr",
                            page_number=page_number,
                        )
                    )
                else:
                    issues.append(
                        ConversionIssue(
                            code="suspicious_native_text",
                            message=(
                                "PDF metin katmanı şüpheli görünüyor ancak OCR kullanılamadığı "
                                "için kayıp yaşamamak üzere yerel metin korundu."
                            ),
                            stage="extraction",
                            page_number=page_number,
                        )
                    )
                LOGGER.warning("Page %s has no usable OCR language data", page_number)
            else:
                try:
                    raw_result = self._ocr_engine.extract_page(page, page_number, ocr_language)
                    ocr_result = _coerce_ocr_result(raw_result)
                except (OSError, RuntimeError, TimeoutError) as error:
                    if (
                        page_has_visual_content
                        and preserve_unreadable_pages
                        and (not blocks or native_is_hidden)
                    ):
                        images = self._retain_page_image(
                            page, page_number, images, rectangle.width, rectangle.height
                        )
                        blocks = []
                        text_source = "image"
                        issues.append(
                            ConversionIssue(
                                code="ocr_failed_page_image",
                                message=f"OCR başarısız oldu; sayfa görseli korundu ({error}).",
                                stage="ocr",
                                page_number=page_number,
                            )
                        )
                    else:
                        issues.append(
                            ConversionIssue(
                                code="ocr_failed",
                                message=f"OCR başarısız oldu ({error}).",
                                stage="ocr",
                                page_number=page_number,
                            )
                        )
                    LOGGER.warning("OCR failed on page %s: %s", page_number, error)
                else:
                    if ocr_result.blocks:
                        ocr_confidence = ocr_result.mean_confidence
                        native_characters = sum(
                            len(block.text.replace(" ", "")) for block in blocks
                        )
                        ocr_characters = sum(
                            len(block.text.replace(" ", ""))
                            for block in ocr_result.blocks
                        )
                        retain_native = bool(
                            blocks
                            and not native_is_hidden
                            and (
                                ocr_confidence < minimum_ocr_confidence
                                or ocr_characters < native_characters * 0.7
                            )
                        )
                        if retain_native:
                            reason = (
                                "OCR metin kapsamı yetersiz"
                                if ocr_characters < native_characters * 0.7
                                else "OCR güveni düşük"
                            )
                            issues.append(
                                ConversionIssue(
                                    code="low_ocr_confidence_native_retained",
                                    message=(
                                        f"{reason} olduğu için PDF metin katmanı korundu "
                                        f"(güven {ocr_confidence:.1f}/100)."
                                    ),
                                    stage="ocr",
                                    page_number=page_number,
                                )
                            )
                        else:
                            blocks = ocr_result.blocks
                            ocr_used = True
                            text_source = "ocr"
                            layout_width = ocr_result.layout_width or rectangle.width
                            layout_height = ocr_result.layout_height or rectangle.height
                            if ocr_confidence < minimum_ocr_confidence:
                                issues.append(
                                    ConversionIssue(
                                        code="low_ocr_confidence",
                                        message=(
                                            "OCR güveni düşük; metnin gözden geçirilmesi önerilir "
                                            f"({ocr_confidence:.1f}/100)."
                                        ),
                                        stage="ocr",
                                        page_number=page_number,
                                    )
                                )
                    elif (
                        page_has_visual_content
                        and preserve_unreadable_pages
                        and (not blocks or native_is_hidden)
                    ):
                        images = self._retain_page_image(
                            page, page_number, images, rectangle.width, rectangle.height
                        )
                        blocks = []
                        text_source = "image"
                        issues.append(
                            ConversionIssue(
                                code="ocr_empty_page_image",
                                message="OCR metin üretmedi; sayfa görseli olarak korundu.",
                                stage="ocr",
                                page_number=page_number,
                            )
                        )
                    elif blocks:
                        issues.append(
                            ConversionIssue(
                                code="ocr_empty_native_retained",
                                message=(
                                    "OCR metin üretmedi; içerik kaybını önlemek için PDF metin "
                                    "katmanı korundu."
                                ),
                                stage="ocr",
                                page_number=page_number,
                            )
                        )

        if (
            not blocks
            and text_source == "none"
            and page_has_visual_content
            and preserve_unreadable_pages
        ):
            images = self._retain_page_image(
                page, page_number, images, rectangle.width, rectangle.height
            )
            text_source = "image"
            issues.append(
                ConversionIssue(
                    code="page_image_fallback",
                    message=(
                        "Düzenlenebilir metin bulunamadığı için içerik sayfa görseli olarak korundu."
                    ),
                    stage="extraction",
                    page_number=page_number,
                )
            )

        if blocks:
            images = [
                image
                for image in images
                if not _is_page_background(image, rectangle.width, rectangle.height)
            ]

        return ParsedPage(
            number=page_number,
            width=layout_width,
            height=layout_height,
            text_blocks=blocks,
            images=images,
            ocr_used=ocr_used,
            text_source=text_source,
            ocr_confidence=ocr_confidence,
            issues=issues,
        )

    def _retain_page_image(
        self,
        page: fitz.Page,
        page_number: int,
        images: list[PositionedImage],
        page_width: float,
        page_height: float,
    ) -> list[PositionedImage]:
        for image in images:
            if _is_page_background(image, page_width, page_height):
                return [
                    PositionedImage(
                        asset_id=image.asset_id,
                        bbox=image.bbox,
                        page_number=image.page_number,
                        role="page-fallback",
                    )
                ]
        store_bytes = getattr(self._image_extractor, "store_bytes", None)
        if not callable(store_bytes):
            raise ConversionError(
                f"Sayfa {page_number} için güvenilir metin veya korunabilir sayfa görseli bulunamadı."
            )
        scale = 180.0 / 72.0
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        asset = store_bytes(pixmap.tobytes("png"), "png")
        return [
            PositionedImage(
                asset_id=asset.id,
                bbox=BoundingBox(0, 0, page_width, page_height),
                page_number=page_number,
                role="page-fallback",
            )
        ]

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
                bbox = _page_bbox(page, line["bbox"])
                primary_span = max(spans, key=_span_length)
                font_name = str(primary_span.get("font", "Unknown"))
                total_length = sum(_span_length(span) for span in spans)
                bold_length = sum(
                    _span_length(span) for span in spans if _span_is_bold(span)
                )
                italic_length = sum(
                    _span_length(span) for span in spans if _span_is_italic(span)
                )
                font_size = sum(
                    float(span.get("size", 10.0)) * _span_length(span) for span in spans
                ) / max(1, total_length)
                result.append(
                    SourceTextBlock(
                        id=f"p{page_number}-b{block_index}-l{line_index}",
                        text=text,
                        bbox=bbox,
                        page_number=page_number,
                        font_size=font_size,
                        font_name=font_name,
                        bold=bold_length / max(1, total_length) >= 0.6,
                        italic=italic_length / max(1, total_length) >= 0.6,
                        color=int(primary_span.get("color", 0)),
                        block_index=block_index,
                        line_index=line_index,
                    )
                )
        return result


def _span_length(span: dict) -> int:
    return len(span.get("text", "")) or len(span.get("chars", []))


def _span_is_bold(span: dict) -> bool:
    font_name = str(span.get("font", "")).lower()
    return bool(int(span.get("flags", 0)) & 16) or "bold" in font_name


def _span_is_italic(span: dict) -> bool:
    font_name = str(span.get("font", "")).lower()
    return bool(int(span.get("flags", 0)) & 2) or "italic" in font_name


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
            rectangle = _fitz_rect(rectangle) * _rotation_matrix(page)
            if (
                rectangle.x0 <= horizontal_margin
                and rectangle.y0 <= vertical_margin
                and rectangle.x1 >= page_width - horizontal_margin
                and rectangle.y1 >= page_height - vertical_margin
            ):
                return True
    return False


def _page_has_visual_content(page: fitz.Page) -> bool:
    try:
        if page.get_images(full=True):
            return True
        get_drawings = getattr(page, "get_drawings", None)
        return bool(get_drawings()) if callable(get_drawings) else False
    except (AttributeError, RuntimeError, ValueError):
        return False


def _has_meaningful_visible_text(page: fitz.Page) -> bool:
    """Use the PyMuPDF 1.24 text trace to reject invisible hidden OCR layers."""
    get_texttrace = getattr(page, "get_texttrace", None)
    if not callable(get_texttrace):
        return True
    try:
        traces = get_texttrace()
        get_bboxlog = getattr(page, "get_bboxlog", None)
        bboxlog = get_bboxlog() if callable(get_bboxlog) else []
    except (AttributeError, RuntimeError, ValueError):
        return True
    visible_characters: set[tuple[int, tuple[float, ...]]] = set()
    for trace in traces:
        if int(trace.get("type", 0)) not in {0, 1} or float(trace.get("opacity", 1.0)) <= 0:
            continue
        sequence = int(trace.get("seqno", -1))
        for character in trace.get("chars", []):
            if not character:
                continue
            codepoint = int(character[0])
            bbox = tuple(float(value) for value in character[3]) if len(character) > 3 else ()
            if (
                codepoint > 0
                and bbox
                and bbox[2] > bbox[0]
                and bbox[3] > bbox[1]
                and not _covered_by_later_image(bbox, sequence, bboxlog)
            ):
                visible_characters.add((codepoint, bbox))
    return len(visible_characters) >= 4


def _covered_by_later_image(
    bbox: tuple[float, ...], sequence: int, bboxlog: list
) -> bool:
    character = fitz.Rect(bbox)
    if character.is_empty:
        return False
    for index, entry in enumerate(bboxlog):
        if index <= sequence or not entry or entry[0] != "fill-image":
            continue
        image = fitz.Rect(entry[1])
        overlap = character & image
        if not overlap.is_empty and overlap.get_area() >= character.get_area() * 0.9:
            return True
    return False


def _native_text_is_suspicious(blocks: list[SourceTextBlock]) -> bool:
    """Detect broken Unicode maps without guessing language-specific replacements."""
    text = "".join(block.text for block in blocks)
    meaningful = [character for character in text if not character.isspace()]
    if not meaningful:
        return bool(blocks)
    suspicious = 0
    for character in meaningful:
        codepoint = ord(character)
        category = unicodedata.category(character)
        if (
            character == "\ufffd"
            or 0xE000 <= codepoint <= 0xF8FF
            or 0xF0000 <= codepoint <= 0xFFFFD
            or 0x100000 <= codepoint <= 0x10FFFD
            or category in {"Cn", "Cs"}
        ):
            suspicious += 1
    return suspicious / len(meaningful) >= 0.01


def _coerce_ocr_result(
    result: OcrPageResult | list[SourceTextBlock],
) -> OcrPageResult:
    """Keep lightweight test/custom OCR adapters compatible with the richer result."""
    if isinstance(result, OcrPageResult):
        return result
    confidences = [block.confidence for block in result if block.confidence is not None]
    mean_confidence = sum(confidences) / len(confidences) if confidences else 100.0
    return OcrPageResult(result, mean_confidence, 3)


def _line_text(line: dict) -> str:
    """Rebuild native text from character geometry without inventing word gaps."""
    spans = line.get("spans", [])
    chars = [char for span in spans for char in span.get("chars", [])]
    if not chars:
        return normalize_text(
            "".join(span.get("text", "") for span in spans), preserve_soft_hyphen=True
        )

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
    return normalize_text("".join(result), preserve_soft_hyphen=True)


def _page_bbox(page: fitz.Page, value: tuple[float, float, float, float]) -> BoundingBox:
    rectangle = fitz.Rect(value) * _rotation_matrix(page)
    return BoundingBox(rectangle.x0, rectangle.y0, rectangle.x1, rectangle.y1)


def _rotation_matrix(page: fitz.Page) -> fitz.Matrix:
    return getattr(page, "rotation_matrix", fitz.Identity)


def _fitz_rect(value: object) -> fitz.Rect:
    if isinstance(value, fitz.Rect):
        return value
    return fitz.Rect(value.x0, value.y0, value.x1, value.y1)
