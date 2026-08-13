"""Embedded image extraction with on-disk deduplication."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pymupdf as fitz
from PIL import Image

from app.core.models import BoundingBox, ImageAsset, PositionedImage

LOGGER = logging.getLogger(__name__)

_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "jpx": "image/jp2",
    "png": "image/png",
    "gif": "image/gif",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
}
_ARTIFACT_MAX_WIDTH = 12.0
_ARTIFACT_MAX_HEIGHT = 4.0
_ARTIFACT_STRIP_MAX_HEIGHT = 12.0
_ARTIFACT_MAX_INK_RATIO = 0.15


class ImageExtractor:
    """Extract PDF image objects once and retain only file paths in memory."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        self._seen: dict[str, ImageAsset] = {}
        self._counter = 0

    @property
    def assets(self) -> dict[str, ImageAsset]:
        return {asset.id: asset for asset in self._seen.values()}

    def store_bytes(self, data: bytes, extension: str = "png") -> ImageAsset:
        """Store generated image data, such as a rendered PDF cover, with deduplication."""
        digest = hashlib.sha256(data).hexdigest()
        existing = self._seen.get(digest)
        if existing is not None:
            return existing
        extension = extension.lower().lstrip(".")
        if extension == "jpeg":
            extension = "jpg"
        self._counter += 1
        destination = self._output_dir / f"image_{self._counter:04d}.{extension}"
        destination.write_bytes(data)
        asset = ImageAsset(
            id=f"image-{self._counter:04d}",
            file_path=destination,
            media_type=_CONTENT_TYPES.get(extension, "image/png"),
            extension=extension,
            digest=digest,
        )
        self._seen[digest] = asset
        return asset

    def extract_page(self, page: fitz.Page, page_number: int) -> list[PositionedImage]:
        """Return the visual locations of successfully extracted page images."""
        locations: list[PositionedImage] = []
        for image_info in page.get_images(full=True):
            xref = image_info[0]
            try:
                asset = self._extract_asset(page.parent, xref)
                for rectangle in page.get_image_rects(xref):
                    rectangle = fitz.Rect(
                        rectangle.x0, rectangle.y0, rectangle.x1, rectangle.y1
                    ) * getattr(page, "rotation_matrix", fitz.Identity)
                    bbox = BoundingBox(rectangle.x0, rectangle.y0, rectangle.x1, rectangle.y1)
                    if _is_raster_artifact(asset, bbox):
                        LOGGER.debug("Ignoring raster artifact xref %s on page %s", xref, page_number)
                        continue
                    locations.append(
                        PositionedImage(
                            asset_id=asset.id,
                            bbox=bbox,
                            page_number=page_number,
                        )
                    )
            except (RuntimeError, ValueError, OSError) as error:
                LOGGER.warning("Could not extract PDF image xref %s: %s", xref, error)
        return locations

    def _extract_asset(self, document: fitz.Document, xref: int) -> ImageAsset:
        extracted = document.extract_image(xref)
        data = extracted["image"]
        digest = hashlib.sha256(data).hexdigest()
        existing = self._seen.get(digest)
        if existing is not None:
            return existing

        return self.store_bytes(data, str(extracted.get("ext") or "png"))


def _is_raster_artifact(asset: ImageAsset, bbox: BoundingBox) -> bool:
    """Ignore ClearScan fragments that render as stray white boxes in EPUB readers."""
    if bbox.width <= _ARTIFACT_MAX_WIDTH or bbox.height <= _ARTIFACT_MAX_HEIGHT:
        return True
    if bbox.height > _ARTIFACT_STRIP_MAX_HEIGHT:
        return False
    ink_ratio = _ink_ratio(asset.file_path)
    return ink_ratio is not None and ink_ratio < _ARTIFACT_MAX_INK_RATIO


def _ink_ratio(path: Path) -> float | None:
    """Estimate whether a short raster strip contains meaningful visible content."""
    try:
        with Image.open(path) as source:
            grayscale = source.convert("L")
            histogram = grayscale.histogram()
            grayscale.close()
    except (OSError, ValueError):
        return None
    total = sum(histogram)
    if not total:
        return 0.0
    return sum(histogram[:245]) / total
