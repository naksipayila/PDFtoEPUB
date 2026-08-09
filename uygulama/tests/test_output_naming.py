from app.gui.main_window import _downloads_directory, _epub_filename


def test_output_filename_uses_pdf_title(sample_pdf) -> None:
    assert _epub_filename(sample_pdf) == "Synthetic Layout Book-EPUB.epub"


def test_output_directory_is_downloads() -> None:
    assert _downloads_directory().name.casefold() == "downloads"
