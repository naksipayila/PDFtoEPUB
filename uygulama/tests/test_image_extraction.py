from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from app.pdf.images import ImageExtractor


class FakeDocument:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def extract_image(self, xref: int) -> dict[str, bytes | str]:
        return {"image": self.data, "ext": "png"}


class FakePage:
    def __init__(self, data: bytes, bbox: tuple[float, float, float, float]) -> None:
        self.parent = FakeDocument(data)
        self._bbox = bbox

    def get_images(self, full: bool = True) -> list[tuple[int]]:
        return [(1,)]

    def get_image_rects(self, xref: int) -> list[SimpleNamespace]:
        return [SimpleNamespace(x0=self._bbox[0], y0=self._bbox[1], x1=self._bbox[2], y1=self._bbox[3])]


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _extract(tmp_path: Path, image: Image.Image, bbox: tuple[float, float, float, float]):
    extractor = ImageExtractor(tmp_path)
    return extractor.extract_page(FakePage(_png_bytes(image), bbox), 1)


def test_drops_low_ink_horizontal_raster_fragments(tmp_path: Path) -> None:
    image = Image.new("RGB", (424, 40), "white")
    ImageDraw.Draw(image).point((120, 20), fill="black")

    assert _extract(tmp_path, image, (20, 20, 122, 29.6)) == []


def test_drops_narrow_vertical_raster_fragments(tmp_path: Path) -> None:
    image = Image.new("RGB", (41, 113), "white")
    ImageDraw.Draw(image).line((20, 0, 20, 112), fill="black", width=3)

    assert _extract(tmp_path, image, (20, 20, 29.8, 47)) == []


def test_keeps_a_small_but_meaningful_logo(tmp_path: Path) -> None:
    image = Image.new("RGB", (133, 31), "white")
    ImageDraw.Draw(image).rectangle((4, 4, 128, 26), fill="black")

    extracted = _extract(tmp_path, image, (20, 20, 52, 27.4))

    assert len(extracted) == 1
