"""Command-line interface for the same conversion service used by the GUI."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.core.config import ConversionOptions
from app.core.converter import PdfToEpubConverter
from app.core.errors import ConversionError
from app.core.logging import configure_logging
from app.core.models import DocumentMetadata, ProgressEvent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a layout-aware PDF into EPUB 3.")
    parser.add_argument("input", type=Path, help="source PDF file")
    parser.add_argument("-o", "--output", type=Path, help="target EPUB file")
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="use local Tesseract OCR for textless or scanned pages",
    )
    parser.add_argument("--no-images", action="store_true", help="do not extract images")
    parser.add_argument("--keep-page-numbers", action="store_true", help="keep edge page numbers")
    parser.add_argument(
        "--keep-header-footer", action="store_true", help="keep repeated headers and footers"
    )
    parser.add_argument(
        "--no-table-detection", action="store_true", help="disable basic table recognition"
    )
    parser.add_argument(
        "--no-columns", action="store_true", help="disable multi-column reading order"
    )
    parser.add_argument("--no-cover", action="store_true", help="do not render a detected cover")
    parser.add_argument("--password", help="valid user password for an encrypted PDF")
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--publisher")
    parser.add_argument("--subject")
    parser.add_argument("--debug-dir", type=Path, help="write raw parsed page blocks as JSON")
    parser.add_argument("--verbose", action="store_true", help="show debug logging")
    return parser


def main(arguments: list[str] | None = None) -> int:
    """Execute a conversion and return a process status code."""
    args = build_parser().parse_args(arguments)
    output = args.output or args.input.with_suffix(".epub")
    if output.suffix.lower() != ".epub":
        output = output.with_suffix(".epub")
    configure_logging(output.parent / "pdf_to_epub.log", args.verbose)
    options = ConversionOptions(
        use_ocr=args.ocr,
        ocr_language="tur",
        include_images=not args.no_images,
        remove_page_numbers=not args.keep_page_numbers,
        remove_headers_footers=not args.keep_header_footer,
        detect_tables=not args.no_table_detection,
        detect_columns=not args.no_columns,
        extract_cover=not args.no_cover,
        pdf_password=args.password,
        metadata=DocumentMetadata(
            title=args.title or "",
            author=args.author or "",
            publisher=args.publisher or "",
            subject=args.subject or "",
        ),
        debug_output_dir=args.debug_dir,
    )
    try:
        report = PdfToEpubConverter().convert(args.input, output, options, _print_progress)
    except (ConversionError, FileNotFoundError, PermissionError, OSError) as error:
        logging.getLogger(__name__).error("Conversion failed: %s", error)
        return 2
    print(f"\nEPUB successfully created: {output}")
    print(report.summary())
    return 0


def _print_progress(event: ProgressEvent) -> None:
    suffix = f" ({event.current}/{event.total})" if event.total else ""
    print(f"{event.message}{suffix}")


if __name__ == "__main__":
    raise SystemExit(main())
