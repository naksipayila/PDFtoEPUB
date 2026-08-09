import zipfile

from app.core.config import ConversionOptions
from app.core.converter import PdfToEpubConverter
from app.epub.validator import validate_epub


def test_converts_synthetic_pdf_to_valid_epub(sample_pdf, tmp_path) -> None:
    output = tmp_path / "converted.epub"
    report = PdfToEpubConverter().convert(sample_pdf, output, ConversionOptions(use_ocr=False))

    assert output.is_file()
    assert report.pages_processed == 2
    assert report.chapters_detected == 2
    assert validate_epub(output) == []
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert names[0] == "mimetype"
        assert "META-INF/container.xml" in names
        assert "EPUB/content.opf" in names
        assert "EPUB/nav.xhtml" in names
        assert "EPUB/styles.css" in names
        assert "EPUB/chapters/chapter_001.xhtml" in names
        first_chapter = archive.read("EPUB/chapters/chapter_001.xhtml").decode("utf-8")
        assert "continues on the following line." in first_chapter
        assert "Synthetic Layout Book" not in first_chapter
