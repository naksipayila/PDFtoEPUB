"""Synthetic PDF and model helpers; no binary fixtures are committed."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
import pytest
from PIL import Image, ImageDraw

from app.core.models import BoundingBox, SourceTextBlock


def source_block(
    text: str,
    *,
    x0: float = 54,
    y0: float = 100,
    x1: float = 300,
    y1: float = 112,
    font_size: float = 10,
    bold: bool = False,
    page: int = 1,
    identifier: str | None = None,
) -> SourceTextBlock:
    return SourceTextBlock(
        id=identifier or f"{page}-{x0}-{y0}-{text[:8]}",
        text=text,
        bbox=BoundingBox(x0, y0, x1, y1),
        page_number=page,
        font_size=font_size,
        font_name="Helvetica-Bold" if bold else "Helvetica",
        bold=bold,
    )


def create_sample_pdf(destination: Path) -> Path:
    """Create a two-page PDF with repeated edge content, prose, headings, and an image."""
    image_path = destination.with_suffix(".png")
    image = Image.new("RGB", (240, 120), "#c58f32")
    ImageDraw.Draw(image).rectangle((15, 15, 225, 105), outline="#302010", width=6)
    image.save(image_path)

    document = fitz.open()
    document.set_metadata(
        {"title": "Synthetic Layout Book", "author": "Test Author", "subject": "Testing"}
    )
    for number, heading, body in (
        (1, "Chapter One", "This is an example paragraph that continues on the following line."),
        (2, "Chapter Two", "A second chapter confirms separate XHTML spine documents."),
    ):
        page = document.new_page(width=595, height=842)
        page.insert_text((54, 26), "Synthetic Layout Book", fontsize=9)
        page.insert_text((54, 80), heading, fontsize=20, fontname="hebo")
        if number == 1:
            page.insert_text((54, 116), "This is an example paragraph that", fontsize=11)
            page.insert_text((54, 130), "continues on the following line.", fontsize=11)
            page.insert_image(fitz.Rect(120, 180, 420, 330), filename=str(image_path))
            page.insert_text((120, 346), "Figure 1. A synthetic illustration.", fontsize=9)
        else:
            page.insert_text((54, 116), body, fontsize=11)
        page.insert_text((290, 815), str(number), fontsize=9)
    document.save(destination)
    document.close()
    return destination


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    return create_sample_pdf(tmp_path / "sample.pdf")
