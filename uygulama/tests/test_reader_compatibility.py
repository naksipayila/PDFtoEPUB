import shutil
import subprocess

import pytest

from app.core.config import ConversionOptions
from app.core.converter import PdfToEpubConverter


@pytest.mark.skipif(not shutil.which("ebook-convert"), reason="Calibre is not installed")
def test_calibre_can_round_trip_generated_epub(sample_pdf, tmp_path) -> None:
    source = tmp_path / "source.epub"
    round_trip = tmp_path / "calibre.epub"
    PdfToEpubConverter().convert(sample_pdf, source, ConversionOptions(use_ocr=False))

    completed = subprocess.run(
        ["ebook-convert", str(source), str(round_trip)],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert round_trip.is_file()
