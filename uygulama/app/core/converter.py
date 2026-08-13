"""High-level conversion facade shared by CLI and GUI."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

from app.core.config import ConversionOptions
from app.core.errors import ConversionCancelled, ConversionError
from app.core.models import ConversionReport, ProgressEvent
from app.core.normalizer import is_language_tag
from app.core.pipeline import CancelCallback, ConversionPipeline, ProgressCallback
from app.epub.builder import EpubBuilder
from app.epub.validator import validate_epub

LOGGER = logging.getLogger(__name__)


class PdfToEpubConverter:
    """Application service that produces a validated EPUB output file."""

    def __init__(self) -> None:
        self._pipeline = ConversionPipeline()
        self._builder = EpubBuilder()

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        options: ConversionOptions | None = None,
        progress: ProgressCallback | None = None,
        is_cancelled: CancelCallback | None = None,
    ) -> ConversionReport:
        """Run the full pipeline and return its conversion report."""
        options = options or ConversionOptions()
        input_path = input_path.expanduser().resolve()
        output_path = output_path.expanduser().resolve()
        if not input_path.is_file():
            raise FileNotFoundError(f"PDF dosyası bulunamadı: {input_path}")
        if output_path.suffix.lower() != ".epub":
            output_path = output_path.with_suffix(".epub")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="pdf_to_epub_conversion_") as temporary:
            document, report = self._pipeline.build_document(
                input_path, options, Path(temporary), progress, is_cancelled
            )
            if not is_language_tag(document.metadata.language):
                raise ConversionError(
                    f"Geçersiz EPUB dil etiketi: {document.metadata.language}"
                )
            self._emit(progress, "building", "EPUB 3 paketi oluşturuluyor...", 0, 1)
            candidate = Path(temporary) / "candidate.epub"
            self._builder.build(document, candidate, options)
            self._emit(progress, "validating", "EPUB paketi doğrulanıyor...", 0, 1)
            warnings = validate_epub(candidate, run_epubcheck=options.run_epubcheck)
            report.warnings.extend(warnings)
            self._check_cancelled(is_cancelled)
            self._publish(candidate, output_path)
        self._emit(progress, "complete", "EPUB başarıyla oluşturuldu.", 1, 1)
        LOGGER.info("EPUB oluşturuldu: %s", output_path)
        return report

    @staticmethod
    def _publish(candidate: Path, output_path: Path) -> None:
        """Replace the destination only after the candidate has passed validation."""
        staged_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{output_path.stem}-",
                suffix=".epub.tmp",
                dir=output_path.parent,
                delete=False,
            ) as staged:
                staged_path = Path(staged.name)
                with candidate.open("rb") as source:
                    shutil.copyfileobj(source, staged)
                staged.flush()
                os.fsync(staged.fileno())
            staged_path.replace(output_path)
        finally:
            if staged_path is not None and staged_path.exists():
                staged_path.unlink()

    @staticmethod
    def _check_cancelled(is_cancelled: CancelCallback | None) -> None:
        if is_cancelled is not None and is_cancelled():
            raise ConversionCancelled("Dönüştürme iptal edildi.")

    @staticmethod
    def _emit(
        callback: ProgressCallback | None,
        stage: str,
        message: str,
        current: int = 0,
        total: int = 0,
    ) -> None:
        LOGGER.info(message)
        if callback is not None:
            callback(ProgressEvent(stage, message, current, total))
