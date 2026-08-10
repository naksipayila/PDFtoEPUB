from types import SimpleNamespace

from PIL import Image

from app.ocr.engine import OcrEngine
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


def test_ocr_preprocessing_preserves_a_grayscale_image() -> None:
    processed = OcrEngine._preprocess(Image.new("RGB", (4, 4), "#808080"))

    assert processed.mode == "L"
