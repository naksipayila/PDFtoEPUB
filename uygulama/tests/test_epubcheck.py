import pytest

from app.core.config import ConversionOptions
from app.core.converter import PdfToEpubConverter
from app.epub.validator import epubcheck_available, validate_epub


@pytest.mark.skipif(not epubcheck_available(), reason="EPUBCheck is not installed")
def test_external_epubcheck_accepts_generated_epub(sample_pdf, tmp_path) -> None:
    output = tmp_path / "epubcheck.epub"
    PdfToEpubConverter().convert(sample_pdf, output, ConversionOptions(use_ocr=False))

    assert validate_epub(output, run_epubcheck=True) == []
