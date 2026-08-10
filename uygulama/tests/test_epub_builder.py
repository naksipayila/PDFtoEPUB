import zipfile

import pymupdf as fitz
from PIL import Image

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


def test_skips_blank_and_image_only_pages_but_keeps_the_cover(tmp_path) -> None:
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
    assert report.pages_skipped == 2
    assert validate_epub(output) == []
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        image_names = [name for name in names if name.startswith("EPUB/images/")]
        assert len(image_names) == 1
        opf = archive.read("EPUB/content.opf").decode("utf-8")
        assert 'properties="cover-image"' in opf
        chapter_names = [name for name in names if name.startswith("EPUB/chapters/")]
        chapter_text = "\n".join(
            archive.read(name).decode("utf-8") for name in chapter_names
        )
        assert "Bu metin EPUB icinde kalmalidir." in chapter_text
        assert "<img " not in chapter_text
