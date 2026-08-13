from types import SimpleNamespace

import pytest
from PIL import Image

from app.core.errors import ConversionError
from app.core.models import BoundingBox, PositionedImage
from app.ocr.engine import (
    OcrEngine,
    OcrPageResult,
    _find_tessdata,
    _ImageRotation,
    _parse_ocr_tsv,
    _restore_bbox,
)
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

    def __init__(self, has_background: bool, visible_text: bool = True) -> None:
        self._has_background = has_background
        self._visible_text = visible_text

    def get_images(self, full: bool = True):
        return [(7,)] if self._has_background else []

    def get_image_rects(self, xref: int):
        return [SimpleNamespace(x0=0, y0=0, x1=600, y1=800)]

    def get_texttrace(self):
        text_type = 0 if self._visible_text else 3
        return [
            {
                "type": text_type,
                "opacity": 1.0,
                "chars": [
                    (ord(character), 0, (0, 0), (index * 5, 10, index * 5 + 5, 20))
                    for index, character in enumerate("Metin")
                ],
            }
        ]


def test_replaces_hidden_text_layer_on_scanned_page(monkeypatch) -> None:
    native = source_block("Bozuk gizli metin", page=1, identifier="native")
    ocr = StubOcrEngine()
    parser = PageParser(StubImageExtractor(), ocr)
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: [native]))

    parsed = parser.parse(
        FakePage(has_background=True, visible_text=False), 1, True, "tur"
    )

    assert [block.text for block in parsed.text_blocks] == ["OCR text"]
    assert parsed.ocr_used
    assert ocr.languages == ["tur"]
    assert ocr.pages == [1]


def test_keeps_visible_native_text_when_page_has_a_background_image(monkeypatch) -> None:
    native = source_block("Çünkü doğru metin seçilebilir", page=1, identifier="native")
    ocr = StubOcrEngine()
    parser = PageParser(BackgroundImageExtractor(), ocr)
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: [native]))

    parsed = parser.parse(FakePage(has_background=True), 1, True, "tur")

    assert [block.text for block in parsed.text_blocks] == ["Çünkü doğru metin seçilebilir"]
    assert parsed.text_source == "native"
    assert not parsed.ocr_used
    assert parsed.images == []
    assert ocr.pages == []


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


def test_visible_native_text_is_not_skipped_when_images_are_disabled(monkeypatch) -> None:
    native = source_block("Bozuk gizli metin", page=1, identifier="native")
    parser = PageParser(BackgroundImageExtractor(), UnavailableOcrEngine())
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: [native]))

    parsed = parser.parse(FakePage(has_background=True), 1, True, "tur", include_images=False)

    assert parsed.text_blocks == [native]
    assert parsed.images == []


def test_scanned_page_fails_instead_of_preserving_unreliable_text(monkeypatch) -> None:
    native = source_block("Bozuk gizli metin", page=1, identifier="native")
    parser = PageParser(StubImageExtractor(), UnavailableOcrEngine())
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: [native]))

    with pytest.raises(ConversionError, match="güvenilir metin.*sayfa görseli"):
        parser.parse(
            FakePage(has_background=True, visible_text=False), 1, True, "tur"
        )


def test_scanned_page_keeps_the_page_image_when_ocr_has_no_text(monkeypatch) -> None:
    native = source_block("Bozuk gizli metin", page=1, identifier="native")

    class EmptyOcrEngine(StubOcrEngine):
        def extract_page(self, page, page_number: int, language: str):
            self.pages.append(page_number)
            return []

    parser = PageParser(BackgroundImageExtractor(), EmptyOcrEngine())
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: [native]))

    parsed = parser.parse(
        FakePage(has_background=True, visible_text=False), 1, True, "tur"
    )

    assert parsed.text_blocks == []
    assert len(parsed.images) == 1
    assert parsed.images[0].role == "page-fallback"
    assert parsed.text_source == "image"


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

    monkeypatch.setattr(
        OcrEngine, "_tesseract", staticmethod(lambda language=None: calls.append(True))
    )
    monkeypatch.setattr("app.ocr.engine._find_tesseract", lambda: "tesseract.exe")
    monkeypatch.setattr("app.ocr.engine._find_tessdata", lambda language=None: tessdata)

    engine = OcrEngine()

    assert engine.available("tur")
    assert engine.available("tur")
    assert len(calls) == 1


def test_tessdata_lookup_requires_every_requested_language(monkeypatch, tmp_path) -> None:
    incomplete = tmp_path / "incomplete"
    complete = tmp_path / "complete"
    incomplete.mkdir()
    complete.mkdir()
    (incomplete / "tur.traineddata").write_bytes(b"tur")
    (complete / "tur.traineddata").write_bytes(b"tur")
    (complete / "eng.traineddata").write_bytes(b"eng")
    monkeypatch.setenv("TESSDATA_PREFIX", str(incomplete))
    monkeypatch.setattr("app.ocr.engine._RUNTIME_TESSDATA", complete)
    monkeypatch.setattr("app.ocr.engine._find_tesseract", lambda: None)

    assert _find_tessdata("tur+eng") == complete


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
    assert parsed["conf"] == [95.0]


def test_low_confidence_ocr_is_exposed_for_review(monkeypatch) -> None:
    class LowConfidenceOcr(StubOcrEngine):
        def extract_page(self, page, page_number: int, language: str):
            block = source_block("Şüpheli metin", page=page_number, identifier="ocr")
            block.confidence = 42.0
            return OcrPageResult([block], 42.0, 6)

    parser = PageParser(BackgroundImageExtractor(), LowConfidenceOcr())
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: []))

    parsed = parser.parse(FakePage(has_background=True), 1, True, "tur")

    assert parsed.ocr_used
    assert parsed.ocr_confidence == 42.0
    assert [issue.code for issue in parsed.issues] == ["low_ocr_confidence"]


def test_low_confidence_ocr_does_not_replace_visible_suspicious_native_text(
    monkeypatch,
) -> None:
    native = source_block("Metin\ufffd", page=1, identifier="native")

    class LowConfidenceOcr(StubOcrEngine):
        def extract_page(self, page, page_number: int, language: str):
            block = source_block("Tahmini metin", page=page_number, identifier="ocr")
            return OcrPageResult([block], 35.0, 6)

    parser = PageParser(StubImageExtractor(), LowConfidenceOcr())
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: [native]))

    parsed = parser.parse(FakePage(has_background=False), 1, True, "tur")

    assert parsed.text_blocks == [native]
    assert not parsed.ocr_used
    assert parsed.text_source == "native"
    assert [issue.code for issue in parsed.issues] == [
        "low_ocr_confidence_native_retained"
    ]


def test_high_confidence_short_ocr_does_not_replace_native_text(monkeypatch) -> None:
    native = source_block(
        "Uzun metin \ufffd kayıp olmadan PDF katmanında kalmalıdır.",
        page=1,
        identifier="native",
    )

    class ShortOcr(StubOcrEngine):
        def extract_page(self, page, page_number: int, language: str):
            block = source_block("Kısa", page=page_number, identifier="ocr")
            return OcrPageResult([block], 99.0, 6)

    parser = PageParser(StubImageExtractor(), ShortOcr())
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: [native]))

    parsed = parser.parse(FakePage(has_background=False), 1, True, "tur")

    assert parsed.text_blocks == [native]
    assert not parsed.ocr_used


def test_restores_boxes_after_image_rotation() -> None:
    rotation = _ImageRotation(-90, (100, 200), (200, 100))

    restored = _restore_bbox((20, 10, 60, 30), (rotation,))

    assert restored == pytest.approx((10, 140, 30, 180))


def test_oriented_ocr_uses_upright_layout_coordinates() -> None:
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight"
        "\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t20\t10\t40\t20\t95.0\tMerhaba\n"
    )
    pytesseract = SimpleNamespace(run_and_get_output=lambda *args, **kwargs: tsv)
    rotation = _ImageRotation(-90, (100, 200), (200, 100))

    result = OcrEngine()._extract_candidate(
        Image.new("L", (200, 100)),
        1,
        "tur",
        3,
        100,
        200,
        (100, 200),
        (rotation,),
        pytesseract,
        10,
    )

    assert result.layout_width == pytest.approx(200)
    assert result.layout_height == pytest.approx(100)
    assert result.blocks[0].bbox == BoundingBox(20, 10, 60, 30)
    assert result.blocks[0].font_size == pytest.approx(20)


def test_vector_only_page_is_preserved_as_a_page_image(monkeypatch) -> None:
    class RenderedAsset:
        id = "rendered-page"

    class RenderingExtractor(StubImageExtractor):
        def store_bytes(self, data, extension="png"):
            return RenderedAsset()

    page = FakePage(has_background=False)
    page.get_drawings = lambda: [{"rect": (10, 10, 50, 50)}]
    page.get_pixmap = lambda **kwargs: SimpleNamespace(tobytes=lambda extension: b"png")
    parser = PageParser(RenderingExtractor(), None)
    monkeypatch.setattr(PageParser, "_extract_text", staticmethod(lambda page, number: []))

    parsed = parser.parse(page, 1, False, "tur", include_images=False)

    assert parsed.text_source == "image"
    assert parsed.images[0].role == "page-fallback"
