"""Optional local Tesseract OCR adapter."""

from __future__ import annotations

import csv
import io
import logging
import math
import os
import re
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageOps

from app.core.errors import ConversionCancelled
from app.core.models import BoundingBox, SourceTextBlock
from app.core.normalizer import normalize_text

LOGGER = logging.getLogger(__name__)
OCR_DPI = 300.0
_OCR_PAGE_SEGMENTATION_MODES = (3, 6)
_RUNTIME_TESSDATA = Path(__file__).resolve().parents[2] / ".runtime" / "tesseract" / "tessdata"


@dataclass(slots=True)
class OcrPageResult:
    """The strongest OCR candidate and its page-level quality signals."""

    blocks: list[SourceTextBlock]
    mean_confidence: float
    page_segmentation_mode: int
    layout_width: float | None = None
    layout_height: float | None = None


@dataclass(frozen=True, slots=True)
class _ImageRotation:
    angle: float
    input_size: tuple[int, int]
    output_size: tuple[int, int]


class OcrEngine:
    """Run local Tesseract OCR for textless and scanned pages."""

    def __init__(
        self,
        timeout_seconds: float = 120.0,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self._available_languages: dict[str, bool] = {}
        self._timeout_seconds = timeout_seconds
        self._is_cancelled = is_cancelled

    def available(self, language: str | None = None) -> bool:
        cache_key = language or ""
        cached = self._available_languages.get(cache_key)
        if cached is not None:
            return cached
        try:
            self._tesseract(language)
            command = _find_tesseract()
            if not command:
                available = False
            elif not language:
                available = True
            else:
                tessdata = _find_tessdata(language)
                language_files = [f"{part}.traineddata" for part in language.split("+") if part]
                available = bool(tessdata and language_files) and all(
                    (tessdata / filename).is_file() for filename in language_files
                )
        except (ImportError, OSError, RuntimeError):
            available = False
        self._available_languages[cache_key] = available
        return available

    def extract_page(
        self, page: fitz.Page, page_number: int, language: str
    ) -> OcrPageResult:
        """Render a page and choose the strongest confidence-scored OCR candidate."""
        pytesseract = self._tesseract(language)
        deadline = time.monotonic() + self._timeout_seconds
        self._check_cancelled()

        scale = OCR_DPI / 72.0
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        original_size = image.size
        image, rotations = self._prepare_image(image, pytesseract, deadline)
        candidates: list[OcrPageResult] = []
        errors: list[Exception] = []
        for index, mode in enumerate(_OCR_PAGE_SEGMENTATION_MODES):
            self._check_cancelled()
            try:
                candidates.append(
                    self._extract_candidate(
                        image,
                        page_number,
                        language,
                        mode,
                        page.rect.width,
                        page.rect.height,
                        original_size,
                        rotations,
                        pytesseract,
                        _stage_timeout(deadline, len(_OCR_PAGE_SEGMENTATION_MODES) - index),
                    )
                )
            except (OSError, RuntimeError, TimeoutError, ValueError) as error:
                errors.append(error)
                LOGGER.warning("OCR PSM %s failed on page %s: %s", mode, page_number, error)
        if not candidates:
            raise RuntimeError(str(errors[-1]) if errors else "OCR produced no candidates")
        maximum_characters = max(_candidate_character_count(candidate) for candidate in candidates)
        minimum_characters = maximum_characters * 0.7
        eligible = [
            candidate
            for candidate in candidates
            if _candidate_character_count(candidate) >= minimum_characters
        ]
        result = max(eligible, key=_ocr_candidate_score)
        LOGGER.info(
            "OCR extracted %s lines from page %s with PSM %s (mean confidence %.1f)",
            len(result.blocks),
            page_number,
            result.page_segmentation_mode,
            result.mean_confidence,
        )
        return result

    def _extract_candidate(
        self,
        image: Image.Image,
        page_number: int,
        language: str,
        page_segmentation_mode: int,
        page_width: float,
        page_height: float,
        original_size: tuple[int, int],
        rotations: tuple[_ImageRotation, ...],
        pytesseract: object,
        timeout: float,
    ) -> OcrPageResult:
        ocr_tsv = pytesseract.run_and_get_output(
            image,
            extension="tsv",
            lang=language,
            config=(
                "-c tessedit_create_tsv=1 --oem 1 "
                f"--psm {page_segmentation_mode} --dpi {int(OCR_DPI)}"
            ),
            timeout=timeout,
        )
        ocr_data = _parse_ocr_tsv(ocr_tsv)
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
        accepted_confidences: list[tuple[float, int]] = []
        for line_index, indexes in enumerate(lines.values()):
            text = _join_ocr_words(ocr_data, indexes)
            if not text:
                continue
            word_confidences = [ocr_data["conf"][index] for index in indexes]
            valid_confidences = [value for value in word_confidences if value >= 0]
            confidence = (
                sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0
            )
            transformed_bbox = (
                min(ocr_data["left"][index] for index in indexes),
                min(ocr_data["top"][index] for index in indexes),
                max(ocr_data["left"][index] + ocr_data["width"][index] for index in indexes),
                max(ocr_data["top"][index] + ocr_data["height"][index] for index in indexes),
            )
            x_scale = page_width / max(1, original_size[0])
            y_scale = page_height / max(1, original_size[1])
            x0, y0, x1, y1 = (
                transformed_bbox[0] * x_scale,
                transformed_bbox[1] * y_scale,
                transformed_bbox[2] * x_scale,
                transformed_bbox[3] * y_scale,
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
                    confidence=confidence,
                )
            )
            accepted_confidences.append((confidence, len(text)))
        total_weight = sum(weight for _, weight in accepted_confidences)
        mean_confidence = (
            sum(confidence * weight for confidence, weight in accepted_confidences) / total_weight
            if total_weight
            else 0.0
        )
        return OcrPageResult(
            result,
            mean_confidence,
            page_segmentation_mode,
            image.width * page_width / max(1, original_size[0]),
            image.height * page_height / max(1, original_size[1]),
        )

    @staticmethod
    def _tesseract(language: str | None = None):
        import pytesseract

        command = os.environ.get("PDFTOEPUB_TESSERACT") or _find_tesseract()
        if command:
            pytesseract.pytesseract.tesseract_cmd = command
        tessdata = _find_tessdata(language)
        if tessdata is not None:
            # Keep the model path out of pytesseract's command-string parsing on Windows.
            os.environ["TESSDATA_PREFIX"] = str(tessdata)
        return pytesseract

    @staticmethod
    def _preprocess(image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        return ImageOps.autocontrast(grayscale)

    def _prepare_image(
        self, image: Image.Image, pytesseract: object, deadline: float
    ) -> tuple[Image.Image, tuple[_ImageRotation, ...]]:
        prepared = self._preprocess(image)
        prepared, orientation = self._correct_orientation(prepared, pytesseract, deadline)
        prepared, deskew = _deskew(prepared)
        rotations = tuple(
            rotation for rotation in (orientation, deskew) if rotation is not None
        )
        return prepared, rotations

    def _correct_orientation(
        self, image: Image.Image, pytesseract: object, deadline: float
    ) -> tuple[Image.Image, _ImageRotation | None]:
        image_to_osd = getattr(pytesseract, "image_to_osd", None)
        if image_to_osd is None or _find_tessdata("osd") is None:
            return image, None
        self._check_cancelled()
        try:
            output = image_to_osd(
                image,
                config=f"--dpi {int(OCR_DPI)}",
                timeout=min(20.0, _stage_timeout(deadline, 3)),
            )
        except (OSError, RuntimeError, ValueError):
            LOGGER.debug("Tesseract orientation detection failed", exc_info=True)
            return image, None
        match = re.search(r"^Rotate:\s*(\d+)", str(output), flags=re.MULTILINE)
        rotation = int(match.group(1)) % 360 if match else 0
        if rotation not in {90, 180, 270}:
            return image, None
        angle = float(-rotation)
        corrected = image.rotate(angle, expand=True, fillcolor=255)
        return corrected, _ImageRotation(angle, image.size, corrected.size)

    def _check_cancelled(self) -> None:
        if self._is_cancelled is not None and self._is_cancelled():
            raise ConversionCancelled("Dönüştürme iptal edildi.")


def _join_ocr_words(ocr_data: dict[str, list], indexes: list[int]) -> str:
    """Join OCR tokens using their visual gap instead of forcing a space everywhere."""
    ordered = sorted(indexes, key=lambda index: (ocr_data["left"][index], index))
    tokens = [
        (
            normalize_text(ocr_data["text"][index], preserve_soft_hyphen=True),
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
    return normalize_text(text, preserve_soft_hyphen=True)


def _parse_ocr_tsv(tsv: str) -> dict[str, list]:
    """Parse Tesseract TSV without invoking its version probe for each page."""
    numeric_columns = ("block_num", "par_num", "line_num", "left", "top", "width", "height")
    result: dict[str, list] = {
        column: [] for column in (*numeric_columns, "conf", "text")
    }
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        for column in numeric_columns:
            result[column].append(_tsv_integer(row.get(column)))
        result["conf"].append(_tsv_float(row.get("conf"), default=-1.0))
        result["text"].append(row.get("text") or "")
    return result


def _tsv_integer(value: str | None) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _tsv_float(value: str | None, *, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _ocr_candidate_score(candidate: OcrPageResult) -> tuple[float, int]:
    character_count = _candidate_character_count(candidate)
    coverage_bonus = min(8.0, math.log2(character_count + 1))
    return candidate.mean_confidence + coverage_bonus, character_count


def _candidate_character_count(candidate: OcrPageResult) -> int:
    return sum(len(block.text) for block in candidate.blocks)


def _deskew(image: Image.Image) -> tuple[Image.Image, _ImageRotation | None]:
    """Correct small scan skew using a bounded horizontal projection search."""
    sample = image.copy()
    sample.thumbnail((900, 900))
    binary = sample.point(lambda value: 0 if value < 190 else 255, mode="1").convert("L")
    angles = (-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0)
    scores = {angle: _projection_score(binary, angle) for angle in angles}
    best_angle = max(angles, key=scores.__getitem__)
    baseline = scores[0.0]
    if best_angle == 0.0 or not baseline or scores[best_angle] < baseline * 1.08:
        return image, None
    corrected = image.rotate(best_angle, expand=False, fillcolor=255)
    return corrected, _ImageRotation(best_angle, image.size, corrected.size)


def _projection_score(image: Image.Image, angle: float) -> float:
    rotated = image if angle == 0.0 else image.rotate(angle, expand=True, fillcolor=255)
    width, height = rotated.size
    if not width or not height:
        return 0.0
    projection = ImageOps.invert(rotated).resize((1, height), Image.Resampling.BOX)
    rows = list(projection.getdata())
    mean = sum(rows) / len(rows)
    return sum((value - mean) ** 2 for value in rows) / len(rows)


def _restore_bbox(
    bbox: tuple[float, float, float, float],
    rotations: tuple[_ImageRotation, ...],
) -> tuple[float, float, float, float]:
    points = [
        (bbox[0], bbox[1]),
        (bbox[2], bbox[1]),
        (bbox[2], bbox[3]),
        (bbox[0], bbox[3]),
    ]
    for rotation in reversed(rotations):
        angle = math.radians(rotation.angle)
        cosine = math.cos(angle)
        sine = math.sin(angle)
        input_center = (rotation.input_size[0] / 2, rotation.input_size[1] / 2)
        output_center = (rotation.output_size[0] / 2, rotation.output_size[1] / 2)
        points = [
            (
                cosine * (x - output_center[0])
                - sine * (y - output_center[1])
                + input_center[0],
                sine * (x - output_center[0])
                + cosine * (y - output_center[1])
                + input_center[1],
            )
            for x, y in points
        ]
    return (
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )


def _stage_timeout(deadline: float, remaining_stages: int) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeError("OCR page time limit exceeded")
    return max(1.0, remaining / max(1, remaining_stages))


def _find_tesseract() -> str | None:
    candidates = [
        os.environ.get("PDFTOEPUB_TESSERACT"),
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        str(_RUNTIME_TESSDATA.parent / "tesseract.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _find_tessdata(language: str | None = None) -> Path | None:
    prefix = os.environ.get("TESSDATA_PREFIX")
    candidates: list[Path] = []
    if prefix:
        prefix_path = Path(prefix)
        candidates.extend((prefix_path, prefix_path / "tessdata"))
    candidates.append(_RUNTIME_TESSDATA)

    command = _find_tesseract()
    if command:
        executable_dir = Path(command).parent
        candidates.extend((executable_dir / "tessdata", executable_dir.parent / "share" / "tessdata"))

    required = [f"{part}.traineddata" for part in (language or "").split("+") if part]
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        if required and all((candidate / filename).is_file() for filename in required):
            return candidate
        if not required and any(candidate.glob("*.traineddata")):
            return candidate
    return None
