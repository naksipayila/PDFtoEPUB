"""GUI application bootstrap."""

from __future__ import annotations

import argparse
import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyleFactory

from app.core.logging import configure_logging
from app.gui.main_window import MainWindow

_WINDOWS_APP_USER_MODEL_ID = "PDFtoEPUB.PDFtoEPUB"
_ICON_PATHS = (
    Path(__file__).resolve().parents[1] / "assets" / "pdf-to-epub.ico",
    Path(sys.prefix) / "share" / "pdf-to-epub" / "assets" / "pdf-to-epub.ico",
)


def _set_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            _WINDOWS_APP_USER_MODEL_ID
        )
    except (AttributeError, OSError):
        pass


def main() -> int:
    """Create and run the desktop application."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--smoke-test", action="store_true")
    arguments, _ = parser.parse_known_args()
    configure_logging(Path.home() / ".pdf_to_epub" / "pdf_to_epub.log")
    _set_windows_app_user_model_id()
    application = QApplication(sys.argv)
    application.setApplicationName("PDF to EPUB")
    application.setOrganizationName("PDFtoEPUB")
    application.setStyle(QStyleFactory.create("Fusion"))
    icon_path = next((path for path in _ICON_PATHS if path.is_file()), _ICON_PATHS[0])
    application_icon = QIcon(str(icon_path))
    if not application_icon.isNull():
        application.setWindowIcon(application_icon)
    window = MainWindow()
    if not application_icon.isNull():
        window.setWindowIcon(application_icon)
    if arguments.smoke_test:
        QTimer.singleShot(0, application.quit)
    else:
        window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
