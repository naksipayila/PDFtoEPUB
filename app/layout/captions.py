"""Image caption detection and association."""

from __future__ import annotations

import re

from app.core.models import ImageBlock, Paragraph

_CAPTION = re.compile(r"^(?:figure|fig\.?|image|şekil|resim|table|tablo)\s*\d+\b", re.IGNORECASE)


def is_caption(paragraph: Paragraph) -> bool:
    return bool(_CAPTION.match(paragraph.text.strip()))


def associate_captions(elements: list[object]) -> list[object]:
    """Fold an immediately following caption into its nearby image element."""
    associated: list[object] = []
    for element in elements:
        if isinstance(element, Paragraph) and is_caption(element) and associated:
            previous = associated[-1]
            if isinstance(previous, ImageBlock) and _nearby(previous, element):
                previous.caption = element.text
                continue
        associated.append(element)
    return associated


def _nearby(image: ImageBlock, caption: Paragraph) -> bool:
    if not image.bbox or not caption.bbox or image.page_number != caption.page_number:
        return False
    return 0 <= caption.bbox.y0 - image.bbox.y1 <= max(90, image.bbox.height * 0.5)
