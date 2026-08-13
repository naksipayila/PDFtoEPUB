"""Command-line interface for the same conversion service used by the GUI."""

from __future__ import annotations

import argparse
import logging
import sys
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
    ocr_group = parser.add_mutually_exclusive_group()
    ocr_group.add_argument(
        "--ocr",
        dest="ocr",
        action="store_true",
        default=True,
        help="use local Tesseract OCR for textless or scanned pages (default)",
    )
    ocr_group.add_argument(
        "--no-ocr",
        dest="ocr",
        action="store_false",
        help="keep the PDF text layer instead of using OCR",
    )
    parser.add_argument(
        "--ocr-language",
        default="tur",
        help="Tesseract language code or combination such as tur+eng (default: tur)",
    )
    parser.add_argument(
        "--language",
        default="tr",
        help="EPUB publication language (default: tr)",
    )
    image_group = parser.add_mutually_exclusive_group()
    image_group.add_argument(
        "--include-images", action="store_true", help="include images on text pages"
    )
    image_group.add_argument(
        "--no-images", action="store_true", help="do not extract inline images (default)"
    )
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
    parser.add_argument(
        "--epubcheck", action="store_true", help="run external epubcheck when installed"
    )
    parser.add_argument("--verbose", action="store_true", help="show debug logging")
    return parser


def main(arguments: list[str] | None = None) -> int:
    """Execute a conversion and return a process status code."""
    args = build_parser().parse_args(arguments)
    _configure_console_encoding()
    output = args.output or args.input.with_suffix(".epub")
    if output.suffix.lower() != ".epub":
        output = output.with_suffix(".epub")
    configure_logging(output.parent / "pdf_to_epub.log", args.verbose)
    options = ConversionOptions(
        use_ocr=args.ocr,
        ocr_language=args.ocr_language,
        include_images=args.include_images and not args.no_images,
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
            language=args.language,
        ),
        debug_output_dir=args.debug_dir,
        run_epubcheck=args.epubcheck,
    )
    try:
        report = PdfToEpubConverter().convert(args.input, output, options, _print_progress)
    except (ConversionError, FileNotFoundError, PermissionError, OSError) as error:
        logging.getLogger(__name__).error("Conversion failed: %s", error)
        return 2
    print(f"\nEPUB successfully created: {output}")
    print(report.summary())
    for warning in report.warnings:
        print(f"- {warning}")
    return 0


def _print_progress(event: ProgressEvent) -> None:
    suffix = f" ({event.current}/{event.total})" if event.total else ""
    print(f"{event.message}{suffix}")


def _configure_console_encoding() -> None:
    """Prevent Turkish progress messages from aborting on legacy Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            continue


if __name__ == "__main__":
    raise SystemExit(main())
