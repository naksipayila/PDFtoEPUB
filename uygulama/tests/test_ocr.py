from types import SimpleNamespace

import pytest
from PIL import Image

from app.core.errors import ConversionError
from app.core.models import BoundingBox, PositionedImage
from app.ocr.engine import OcrEngine, _parse_ocr_tsv
from app.pdf.page_parser import PageParser
from tests.conftest import source_block


class StubImageExtractor:
    def extract_page(self, page, page_number):
        return []


class StubOcrEngine:
    def __init__(self) -> None:
        self.languages: list[str] = []
        self.pages: list[int] = []

    def available(self, language: str) -> bool:
        self.languages.append(language)
        return True

    def extract_page(self, page, page_number: int, language: str):
        self.pages.append(page_number)
        return [source_block("OCR text", page=page_number, identifier="ocr-result")]


class UnavailableOcrEngine:
    def available(self, language: str) -> bool:
        return False


class BackgroundImageExtractor:
    def extract_page(self, page, page_number):
        return [
            PositionedImage(
                asset_id="page-image",
                bbox=BoundingBox(0, 0, page.rect.width, page.rect.height),
                page_number=page_number,
            )
        ]


class FakePage:
    rect = SimpleNamespace(width=600, height=800)

    def __init__(self, has_background: bool) -> None:
        self._has_background = has_background

    def get_images(self, full: bool = True):
        return [(7,)] if self._has_background else []

    def get_image_rects(self, xref: int):
        return [SimpleNamespace(x0=0, y0=0, x1=600, y1=800)]


def test_replaces_hidden_text_layer_on_scanned_page(monkeypatch) -> None:
    native = source_block("Bozuk gizli metin", page=1, identifier="native")
    ocr = StubOcrEngine()
    parser = PageParser(StubImageExtractor(), ocr)
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: [native]))

    parsed = parser.parse(FakePage(has_background=True), 1, True, "tur")

    assert [block.text for block in parsed.text_blocks] == ["OCR text"]
    assert parsed.ocr_used
    assert ocr.languages == ["tur"]
    assert ocr.pages == [1]


def test_keeps_native_text_on_vector_page(monkeypatch) -> None:
    native = source_block("Native text", page=1, identifier="native")
    ocr = StubOcrEngine()
    parser = PageParser(StubImageExtractor(), ocr)
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: [native]))

    parsed = parser.parse(FakePage(has_background=False), 1, True, "tur")

    assert [block.text for block in parsed.text_blocks] == ["Native text"]
    assert not parsed.ocr_used
    assert ocr.pages == []


def test_scanned_page_detection_does_not_require_image_extraction(monkeypatch) -> None:
    ocr = StubOcrEngine()
    parser = PageParser(StubImageExtractor(), ocr)
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: []))

    parsed = parser.parse(FakePage(has_background=True), 1, True, "tur", include_images=False)

    assert parsed.ocr_used
    assert ocr.pages == [1]


def test_scanned_page_fails_instead_of_preserving_unreliable_text(monkeypatch) -> None:
    native = source_block("Bozuk gizli metin", page=1, identifier="native")
    parser = PageParser(StubImageExtractor(), UnavailableOcrEngine())
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: [native]))

    with pytest.raises(ConversionError, match="taranmış.*OCR"):
        parser.parse(FakePage(has_background=True), 1, True, "tur")


def test_scanned_page_keeps_the_page_image_when_ocr_has_no_text(monkeypatch) -> None:
    native = source_block("Bozuk gizli metin", page=1, identifier="native")

    class EmptyOcrEngine(StubOcrEngine):
        def extract_page(self, page, page_number: int, language: str):
            self.pages.append(page_number)
            return []

    parser = PageParser(BackgroundImageExtractor(), EmptyOcrEngine())
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: [native]))

    parsed = parser.parse(FakePage(has_background=True), 1, True, "tur")

    assert parsed.text_blocks == []
    assert len(parsed.images) == 1


def test_ocr_is_disabled_only_when_requested() -> None:
    from app.cli import build_parser

    assert build_parser().parse_args(["book.pdf"]).ocr
    assert not build_parser().parse_args(["book.pdf", "--no-ocr"]).ocr


def test_ocr_preprocessing_preserves_a_grayscale_image() -> None:
    processed = OcrEngine._preprocess(Image.new("RGB", (4, 4), "#808080"))

    assert processed.mode == "L"


def test_ocr_availability_is_cached(monkeypatch, tmp_path) -> None:
    tessdata = tmp_path / "tessdata"
    tessdata.mkdir()
    (tessdata / "tur.traineddata").write_bytes(b"model")
    calls: list[bool] = []

    monkeypatch.setattr(OcrEngine, "_tesseract", staticmethod(lambda: calls.append(True)))
    monkeypatch.setattr("app.ocr.engine._find_tesseract", lambda: "tesseract.exe")
    monkeypatch.setattr("app.ocr.engine._find_tessdata", lambda: tessdata)

    engine = OcrEngine()

    assert engine.available("tur")
    assert engine.available("tur")
    assert len(calls) == 1


def test_ocr_tsv_parser_preserves_text_geometry() -> None:
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight"
        "\tconf\ttext\n"
        "5\t1\t2\t3\t4\t1\t10\t20\t30\t40\t95.0\tMerhaba\n"
    )

    parsed = _parse_ocr_tsv(tsv)

    assert parsed["text"] == ["Merhaba"]
    assert parsed["block_num"] == [2]
    assert parsed["left"] == [10]
    assert parsed["height"] == [40]
