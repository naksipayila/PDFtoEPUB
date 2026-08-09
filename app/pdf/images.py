"""Embedded image extraction with on-disk deduplication."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pymupdf as fitz

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
                    locations.append(
                        PositionedImage(
                            asset_id=asset.id,
                            bbox=BoundingBox(
                                rectangle.x0, rectangle.y0, rectangle.x1, rectangle.y1
                            ),
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
