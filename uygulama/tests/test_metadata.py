from app.pdf.metadata import metadata_from_pdf
from app.pdf.reader import PdfReader


def test_normalizes_pdf_metadata() -> None:
    metadata = metadata_from_pdf(
        {
            "title": "  A Book ",
            "author": " A. Author ",
            "keywords": "History",
            "producer": "PDF Software",
        }
    )

    assert metadata.title == "A Book"
    assert metadata.author == "A. Author"
    assert metadata.description == "History"
    assert metadata.publisher == ""


def test_reads_metadata_from_synthetic_pdf(sample_pdf) -> None:
    with PdfReader(sample_pdf) as reader:
        metadata = reader.metadata

    assert metadata.title == "Synthetic Layout Book"
    assert metadata.author == "Test Author"
