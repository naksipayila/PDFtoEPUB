"""GUI application bootstrap."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QStyleFactory

from app.core.logging import configure_logging
from app.gui.main_window import MainWindow


def main() -> int:
    """Create and run the desktop application."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--smoke-test", action="store_true")
    arguments, _ = parser.parse_known_args()
    configure_logging(Path.home() / ".pdf_to_epub" / "pdf_to_epub.log")
    application = QApplication(sys.argv)
    application.setApplicationName("PDF to EPUB")
    application.setOrganizationName("PDFtoEPUB")
    application.setStyle(QStyleFactory.create("Fusion"))
    window = MainWindow()
    if arguments.smoke_test:
        QTimer.singleShot(0, application.quit)
    else:
        window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
