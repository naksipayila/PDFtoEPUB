"""Safe PDF opening and document-level metadata access."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz

from app.core.errors import ConversionError, PasswordRequiredError
from app.core.models import DocumentMetadata
from app.pdf.metadata import metadata_from_pdf


class PdfReader:
    """Owns a PyMuPDF document and translates library failures to app errors."""

    def __init__(self, path: Path, password: str | None = None) -> None:
        self.path = path
        try:
            self.document = fitz.open(path)
        except (fitz.FileDataError, RuntimeError, OSError) as error:
            raise ConversionError(f"PDF açılamadı: {error}") from error

        if self.document.needs_pass and not self.document.authenticate(password or ""):
            self.document.close()
            raise PasswordRequiredError(
                "Bu PDF parola korumalı. Geçerli kullanıcı parolasını girin."
            )
        if self.document.page_count == 0:
            self.document.close()
            raise ConversionError("PDF hiçbir sayfa içermiyor.")

    @property
    def page_count(self) -> int:
        return self.document.page_count

    @property
    def metadata(self) -> DocumentMetadata:
        return metadata_from_pdf(self.document.metadata)

    def close(self) -> None:
        self.document.close()

    def __enter__(self) -> PdfReader:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()
