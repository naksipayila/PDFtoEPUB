import zipfile
from xml.etree import ElementTree

from app.core.config import ConversionOptions
from app.core.converter import PdfToEpubConverter
from app.epub.review import EpubTextReview
from app.epub.validator import validate_epub


def test_edits_epub_text_and_navigation_transactionally(sample_pdf, tmp_path) -> None:
    output = tmp_path / "review.epub"
    PdfToEpubConverter().convert(sample_pdf, output, ConversionOptions(use_ocr=False))
    review = EpubTextReview(output)
    heading = next(entry for entry in review.entries_for_page(1) if entry.kind == "h1")

    review.update(heading.key, "Düzeltilmiş Bölüm")
    review.save()

    assert validate_epub(output) == []
    with zipfile.ZipFile(output) as archive:
        chapter = ElementTree.fromstring(archive.read("EPUB/chapters/chapter_001.xhtml"))
        navigation = ElementTree.fromstring(archive.read("EPUB/nav.xhtml"))
    assert "Düzeltilmiş Bölüm" in "".join(chapter.itertext())
    assert "Düzeltilmiş Bölüm" in "".join(navigation.itertext())


def test_failed_review_validation_preserves_existing_epub(sample_pdf, tmp_path, monkeypatch) -> None:
    output = tmp_path / "review.epub"
    PdfToEpubConverter().convert(sample_pdf, output, ConversionOptions(use_ocr=False))
    original = output.read_bytes()
    review = EpubTextReview(output)

    def fail_validation(path):
        raise ValueError("invalid correction")

    monkeypatch.setattr("app.epub.review.validate_epub", fail_validation)

    try:
        review.save()
    except ValueError:
        pass

    assert output.read_bytes() == original
