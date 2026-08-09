# PDF to EPUB Converter

Offline, layout-aware desktop application that converts PDFs to reflowable EPUB 3 books. It uses PyMuPDF coordinates and deterministic heuristics instead of flattening extracted text into one HTML file.

## Features

- PySide6 desktop UI with drag and drop, progress, logs, cancellation, saved settings, and System/Light/Dark themes.
- CLI and GUI share the same conversion service.
- Coordinate-preserving PyMuPDF extraction for text spans, font information, page geometry, metadata, and embedded images.
- Semantic intermediate document model, independent of PDF and EPUB layers.
- Paragraph reconstruction and discretionary hyphen repair.
- Dynamic heading and chapter detection.
- One-to-three column reading-order resolver.
- Repeated header/footer and edge page-number removal.
- Images, nearby captions, conventional lists, delimiter-based table fallback, and conservative bottom-of-page footnotes.
- Optional local Tesseract OCR only for textless pages. No source file is uploaded.
- Validated EPUB 3 archive with XHTML chapters, navigation, stylesheet, metadata, cover support, and manifest/spine checks.
- Debug export of page block data as JSON.

## Requirements (development)

- Python 3.12 or later
- Windows, macOS, or Linux
- Tesseract is optional and only needed for OCR

The development environment must also have a working Qt platform plugin. PySide6 installs the required plugin automatically in normal virtual environments.

## Setup

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run the desktop application:

```powershell
python run.py
```

Drag a PDF into the input field or choose one, set an output folder, review options, then select **Convert to EPUB**.

## CLI

```powershell
python -m app.cli book.pdf -o output\book.epub
python run.py book.pdf --output output\book.epub
```

Useful options:

```text
--ocr
--no-images
--keep-header-footer
--keep-page-numbers
--no-table-detection
--no-columns
--no-cover
--password YOUR_PASSWORD
--debug-dir debug
```

Use `python -m app.cli --help` for all CLI options.

## Tesseract OCR

Install Tesseract separately, then ensure its executable is on `PATH`.

Windows installation example:

1. Install the official Windows Tesseract build or a trusted distribution.
2. Add its installation directory, commonly `C:\Program Files\Tesseract-OCR`, to `PATH`.
3. Install language data such as `tur.traineddata` when needed.
4. Restart the application.

If Tesseract is absent, normal text-layer PDFs continue to convert. Textless/scanned pages are reported in the log instead of crashing the application.

## Tests And Quality Checks

Tests create their PDF fixtures at runtime, so no binary sample files are stored in the repository.

```powershell
pytest
ruff check .
python run.py --smoke-test
```

The integration test creates a multi-page PDF containing headings, a paragraph split over visual lines, repeated headers, page numbers, and an image. It converts it and verifies the EPUB archive structure plus internal validation.

## Packaging For Windows

The repository includes a one-folder Windows build flow. It bundles Python, Qt,
PyMuPDF, Pillow, pytesseract, and the application, so the resulting folder can
be copied to another Windows computer without installing Python or any
application dependency there.

On the build computer, double-click `build_portable.cmd` or run:

```powershell
.\build_portable.ps1
```

The script installs the build dependencies automatically, creates
`portable\PDFtoEPUB`, and includes Tesseract when it is available on the build
computer. Copy that complete folder and double-click `PDFtoEPUB.exe` on the
other computer. The application is designed so PDF parsing, layout analysis,
and EPUB construction do not depend on the GUI.

## Architecture

```text
GUI / CLI
    -> PdfToEpubConverter
        -> PDF extraction + layout analysis
        -> semantic Document model
        -> EPUB 3 builder + validator
```

`app/pdf` never depends on `app/epub`; both communicate through `app/core/models.py`.

## Known Limitations

- PDF layout has no universal semantic standard. Heuristics prioritize retaining text over reproducing pages exactly.
- Table detection is intentionally conservative; reliably detected delimiter rows become HTML tables while ambiguous table text remains readable prose.
- Footnotes are preserved as semantic EPUB footnotes when detected, but automatic marker-to-note linking is not exhaustive.
- OCR quality depends on Tesseract language data and source scan quality. The current preprocessing is conservative.
- Complex mixed-width magazine layouts, rotated text, mathematical notation, and image-only tables may require future specialized analyzers.

## Recommended Next Improvements

- Add a page-level visual/semantic preview panel.
- Improve footnote reference linking and table grid reconstruction with PyMuPDF drawing analysis.
- Add per-document heuristic tuning and bookmark/Table-of-Contents reconciliation.
- Implement a pluggable AI-enhanced `LayoutAnalyzer` while retaining the offline heuristic fallback.
