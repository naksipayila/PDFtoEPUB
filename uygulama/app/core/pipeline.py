"""Event-driven, cancellation-aware PDF-to-semantic-document pipeline."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

from app.core.config import ConversionOptions
from app.core.errors import ConversionCancelled, ConversionError
from app.core.models import (
    ConversionReport,
    DocumentMetadata,
    ParsedPage,
    ProgressEvent,
    SemanticDocument,
)
from app.layout.analyzer import HeuristicLayoutAnalyzer
from app.ocr.engine import OcrEngine
from app.pdf.images import ImageExtractor
from app.pdf.page_parser import PageParser
from app.pdf.reader import PdfReader

LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[ProgressEvent], None]
CancelCallback = Callable[[], bool]


class ConversionPipeline:
    """Coordinates extraction and layout analysis without EPUB-specific dependencies."""

    def build_document(
        self,
        input_path: Path,
        options: ConversionOptions,
        workspace: Path,
        progress: ProgressCallback | None = None,
        is_cancelled: CancelCallback | None = None,
    ) -> tuple[SemanticDocument, ConversionReport]:
        """Extract and analyze a PDF, storing temporary image blobs outside application memory."""
        report = ConversionReport()
        self._emit(progress, "opening", "PDF açılıyor...")
        images_dir = workspace / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        image_extractor = ImageExtractor(images_dir)
        with PdfReader(input_path, options.pdf_password) as reader:
            metadata = _merged_metadata(reader.metadata, options.metadata)
            if not metadata.title or metadata.title.casefold() == "untitled":
                metadata.title = input_path.stem
            self._emit(
                progress, "analysis", f"{reader.page_count} sayfa algılandı.", 0, reader.page_count
            )
            parser = PageParser(
                image_extractor,
                OcrEngine(
                    timeout_seconds=options.ocr_timeout_seconds,
                    is_cancelled=is_cancelled,
                ),
            )
            pages: list[ParsedPage] = []
            cover_asset_id: str | None = None
            for page_index in range(reader.page_count):
                self._check_cancelled(is_cancelled)
                page_number = page_index + 1
                self._emit(
                    progress,
                    "extracting",
                    f"{page_number}/{reader.page_count}. sayfa ayıklanıyor...",
                    page_number - 1,
                    reader.page_count,
                )
                page = reader.document.load_page(page_index)
                parsed = parser.parse(
                    page,
                    page_number,
                    options.use_ocr,
                    options.ocr_language,
                    options.include_images,
                    options.preserve_unreadable_pages,
                    options.minimum_ocr_confidence,
                )
                pages.append(parsed)
                if parsed.ocr_used:
                    report.ocr_pages += 1
                    if (
                        parsed.ocr_confidence is not None
                        and parsed.ocr_confidence < options.minimum_ocr_confidence
                    ):
                        report.low_confidence_ocr_pages += 1
                elif parsed.text_source == "native":
                    report.native_text_pages += 1
                if parsed.text_source == "image":
                    report.image_fallback_pages += 1
                for issue in parsed.issues:
                    report.add_issue(issue)
                if page_number == 1 and options.extract_cover and self._looks_like_cover(page, parsed):
                    import pymupdf as fitz

                    cover = image_extractor.store_bytes(
                        page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png")
                    )
                    cover_asset_id = cover.id
                if options.debug_output_dir is not None:
                    self._write_debug_page(parsed, options.debug_output_dir)
                self._emit(
                    progress,
                    "extracting",
                    f"{page_number}/{reader.page_count}. sayfa ayıklandı.",
                    page_number,
                    reader.page_count,
                )

            self._check_cancelled(is_cancelled)
            self._emit(progress, "layout", "Görsel yerleşim analiz ediliyor...")
            all_assets = image_extractor.assets
            used_asset_ids = {
                image.asset_id for page in pages for image in page.images
            }
            assets = {
                asset_id: asset
                for asset_id, asset in all_assets.items()
                if asset_id in used_asset_ids
            }
            if cover_asset_id is not None and cover_asset_id in all_assets:
                assets[cover_asset_id] = all_assets[cover_asset_id]
            analyzer = HeuristicLayoutAnalyzer(metadata, assets)
            document = analyzer.analyze(pages, options, report)
            if not any(chapter.elements for chapter in document.chapters):
                raise ConversionError("PDF içinde metin içeren bir sayfa bulunamadı.")
            document.cover_asset_id = cover_asset_id
            report.pages_processed = len(pages)
            report.images_extracted = len(document.assets)
            self._emit(progress, "layout", "Belgenin anlamsal analizi tamamlandı.", 1, 1)
            return document, report

    @staticmethod
    def _looks_like_cover(page: object, parsed: ParsedPage) -> bool:
        has_images = bool(parsed.images)
        get_images = getattr(page, "get_images", None)
        if not has_images and callable(get_images):
            try:
                has_images = bool(get_images(full=True))
            except (AttributeError, RuntimeError):
                has_images = False
        return len(parsed.text_blocks) <= 4 and has_images

    @staticmethod
    def _write_debug_page(page: ParsedPage, debug_dir: Path) -> None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "page": page.number,
            "width": page.width,
            "height": page.height,
            "text_source": page.text_source,
            "ocr_confidence": page.ocr_confidence,
            "issues": [
                {
                    "code": issue.code,
                    "severity": issue.severity,
                    "stage": issue.stage,
                    "message": issue.message,
                }
                for issue in page.issues
            ],
            "blocks": [
                {
                    "type": "text",
                    "text": block.text,
                    "bbox": [block.bbox.x0, block.bbox.y0, block.bbox.x1, block.bbox.y1],
                    "font_size": block.font_size,
                    "font_name": block.font_name,
                    "bold": block.bold,
                    "italic": block.italic,
                    "confidence": block.confidence,
                }
                for block in page.text_blocks
            ],
        }
        (debug_dir / f"page_{page.number:03d}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

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

    @staticmethod
    def _check_cancelled(is_cancelled: CancelCallback | None) -> None:
        if is_cancelled is not None and is_cancelled():
            raise ConversionCancelled("Dönüştürme iptal edildi.")


def _merged_metadata(
    source: DocumentMetadata, supplied: DocumentMetadata | None
) -> DocumentMetadata:
    if supplied is None:
        return source
    return DocumentMetadata(
        title=supplied.title or source.title,
        author=supplied.author or source.author,
        language=supplied.language or source.language,
        publisher=supplied.publisher or source.publisher,
        description=supplied.description or source.description,
        isbn=supplied.isbn or source.isbn,
        subject=supplied.subject or source.subject,
    )
