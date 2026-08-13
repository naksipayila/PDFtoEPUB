import zipfile
from xml.etree import ElementTree

import pymupdf as fitz
import pytest
from PIL import Image

from app.core.config import ConversionOptions
from app.core.converter import PdfToEpubConverter
from app.core.errors import ConversionError, ValidationError
from app.core.models import DocumentMetadata
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


def test_skips_blank_page_but_preserves_image_only_page_and_cover(tmp_path) -> None:
    image_path = tmp_path / "cover-source.png"
    Image.new("RGB", (240, 120), "#c58f32").save(image_path)
    source = tmp_path / "filtered.pdf"
    document = fitz.open()

    cover = document.new_page(width=595, height=842)
    cover.insert_image(fitz.Rect(0, 0, 595, 842), filename=str(image_path))
    cover.insert_text((72, 100), "Kitap Kapagi", fontsize=24)

    text_page = document.new_page(width=595, height=842)
    text_page.insert_text((72, 100), "Metin Sayfasi", fontsize=20)
    text_page.insert_text((72, 140), "Bu metin EPUB icinde kalmalidir.", fontsize=11)

    document.new_page(width=595, height=842)

    image_only = document.new_page(width=595, height=842)
    image_only.insert_image(fitz.Rect(100, 100, 495, 300), filename=str(image_path))
    document.save(source)
    document.close()

    output = tmp_path / "filtered.epub"
    report = PdfToEpubConverter().convert(
        source, output, ConversionOptions(use_ocr=False)
    )

    assert report.pages_processed == 4
    assert report.pages_skipped == 1
    assert report.image_fallback_pages == 1
    assert validate_epub(output) == []
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        image_names = [name for name in names if name.startswith("EPUB/images/")]
        assert len(image_names) == 2
        opf = archive.read("EPUB/content.opf").decode("utf-8")
        assert 'properties="cover-image"' in opf
        chapter_names = [name for name in names if name.startswith("EPUB/chapters/")]
        chapter_text = "\n".join(
            archive.read(name).decode("utf-8") for name in chapter_names
        )
        assert "Bu metin EPUB icinde kalmalidir." in chapter_text
        assert "<img " in chapter_text


def test_preserves_turkish_unicode_and_language_in_epub(tmp_path) -> None:
    source = tmp_path / "turkce.pdf"
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    expected = "ÇĞİÖŞÜ çğıöşü Iİiı"
    page.insert_htmlbox(
        fitz.Rect(54, 80, 500, 150),
        f"<p style='font-size: 16px'>{expected}</p>",
    )
    document.save(source)
    document.close()

    output = tmp_path / "turkce.epub"
    PdfToEpubConverter().convert(source, output, ConversionOptions(use_ocr=False))

    with zipfile.ZipFile(output) as archive:
        chapter = ElementTree.fromstring(archive.read("EPUB/chapters/chapter_001.xhtml"))
        text = " ".join("".join(chapter.itertext()).split())
        opf = archive.read("EPUB/content.opf").decode("utf-8")
        raw_chapter = archive.read("EPUB/chapters/chapter_001.xhtml").decode("utf-8")

    assert expected in text
    assert "<dc:language>tr</dc:language>" in opf
    assert 'xml:lang="tr"' in raw_chapter
    assert 'lang="tr"' in raw_chapter


def test_validation_failure_does_not_replace_existing_epub(
    sample_pdf, tmp_path, monkeypatch
) -> None:
    output = tmp_path / "existing.epub"
    original = b"existing valid publication"
    output.write_bytes(original)

    def reject_candidate(path, run_epubcheck=False):
        raise ValidationError("candidate rejected")

    monkeypatch.setattr("app.core.converter.validate_epub", reject_candidate)

    try:
        PdfToEpubConverter().convert(
            sample_pdf, output, ConversionOptions(use_ocr=False)
        )
    except ValidationError:
        pass

    assert output.read_bytes() == original


def test_rejects_invalid_publication_language(sample_pdf, tmp_path) -> None:
    output = tmp_path / "invalid-language.epub"

    with pytest.raises(ConversionError, match="Geçersiz EPUB dil etiketi"):
        PdfToEpubConverter().convert(
            sample_pdf,
            output,
            ConversionOptions(
                use_ocr=False,
                metadata=DocumentMetadata(language="not_a_language"),
            ),
        )

    assert not output.exists()
