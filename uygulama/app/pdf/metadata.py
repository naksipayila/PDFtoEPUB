"""PDF metadata normalization."""

from __future__ import annotations

from typing import Any

from app.core.models import DocumentMetadata


def metadata_from_pdf(raw: dict[str, Any] | None) -> DocumentMetadata:
    """Map PyMuPDF metadata keys to the application metadata model."""
    raw = raw or {}
    return DocumentMetadata(
        title=(raw.get("title") or "Untitled").strip() or "Untitled",
        author=(raw.get("author") or "").strip(),
        subject=(raw.get("subject") or "").strip(),
        publisher=(raw.get("producer") or "").strip(),
        description=(raw.get("keywords") or "").strip(),
    )
