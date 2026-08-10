"""Main PySide6 desktop interface for local PDF to EPUB conversion."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QGuiApplication,
)
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from app.core.config import ConversionOptions
from app.core.errors import ConversionError
from app.core.models import ProgressEvent
from app.gui.workers.conversion_worker import ConversionWorker
from app.pdf.reader import PdfReader


class PdfDropZone(QFrame):
    """Visual PDF target that reports a dropped local PDF path."""

    pdf_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("pdfDropZone")
        self.setFixedHeight(206)
        self.setProperty("dragActive", False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_label = QLabel("PDF")
        self._icon_label.setObjectName("pdfDropIcon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedSize(72, 44)

        self._name_label = QLabel("PDF dosyasını bırakın")
        self._name_label.setObjectName("pdfDropTitle")
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setWordWrap(True)

        self._hint_label = QLabel("Bıraktığınızda dönüşüm otomatik başlar")
        self._hint_label.setObjectName("pdfDropHint")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setWordWrap(True)

        layout.addWidget(self._icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._name_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hint_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_pdf(self, path: Path) -> None:
        self._icon_label.setText("PDF")
        self._name_label.setText(path.name)
        self._hint_label.setText("Dönüşüm başlatılıyor...")

    def set_status(self, message: str) -> None:
        self._hint_label.setText(message)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if self._pdf_path(event) is not None:
            event.acceptProposedAction()
            self._set_drag_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self._set_drag_active(False)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self._set_drag_active(False)
        path = self._pdf_path(event)
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.pdf_dropped.emit(path)

    @staticmethod
    def _pdf_path(event: QDragEnterEvent | QDropEvent) -> Path | None:
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() == ".pdf":
                return path
        return None

    def _set_drag_active(self, active: bool) -> None:
        if self.property("dragActive") == active:
            return
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class MainWindow(QMainWindow):
    """Responsive desktop UI; all conversion work runs through ConversionWorker."""

    _DEFAULT_WIDTH = 650
    _DEFAULT_HEIGHT = 250

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self._settings = QSettings("PDFtoEPUB", "PDFtoEPUB")
        self._worker: ConversionWorker | None = None
        self._input_path: Path | None = None
        self.setWindowTitle("PDF to EPUB Converter")
        self.setMinimumSize(self._DEFAULT_WIDTH, self._DEFAULT_HEIGHT)
        self.resize(self._DEFAULT_WIDTH, self._DEFAULT_HEIGHT)
        self._build_interface()
        self._restore_settings()
        self.setFixedSize(self._DEFAULT_WIDTH, self._DEFAULT_HEIGHT)

    def _build_interface(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 22, 8, 22)
        self.drop_zone = PdfDropZone()
        layout.addWidget(self.drop_zone)
        self.drop_zone.pdf_dropped.connect(self._set_input)

    def closeEvent(self, event: object) -> None:  # noqa: N802
        self._save_settings()
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)  # type: ignore[arg-type]

    def _set_input(self, path: Path) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._input_path = path
        self.drop_zone.set_pdf(path)
        self._start_conversion()

    def _start_conversion(self) -> None:
        input_path = self._input_path
        if input_path is None or not input_path.is_file() or input_path.suffix.lower() != ".pdf":
            self._show_error("Geçerli bir PDF dosyası seçin.")
            return
        output_dir = _downloads_directory()
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self._show_error(f"İndirilenler klasörü kullanılamadı: {error}")
            return
        output_path = output_dir / _epub_filename(input_path)
        self.drop_zone.set_status("Dönüştürülüyor...")
        self._worker = ConversionWorker(input_path, output_path, self._options())
        self._worker.progress_changed.connect(self._on_progress)
        self._worker.conversion_succeeded.connect(self._on_success)
        self._worker.conversion_failed.connect(self._on_failure)
        self._worker.conversion_cancelled.connect(self._on_cancelled)
        self._worker.start()

    def _options(self) -> ConversionOptions:
        return ConversionOptions(
            ocr_language="tur",
            include_images=False,
            extract_cover=True,
            css_style_mode="reader",
        )

    def _on_progress(self, event: ProgressEvent) -> None:
        self.drop_zone.set_status(event.message)

    def _on_success(self, _report: object) -> None:
        self.drop_zone.set_status("EPUB başarıyla oluşturuldu.")

    def _on_failure(self, message: str) -> None:
        self.drop_zone.set_status(f"Dönüştürme başarısız oldu: {message}")

    def _on_cancelled(self) -> None:
        self.drop_zone.set_status("Dönüştürme iptal edildi.")

    def _show_error(self, message: str) -> None:
        self.drop_zone.set_status(message)

    def _restore_settings(self) -> None:
        geometry = self._settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        if self.isMaximized():
            self.showNormal()
        self.resize(
            max(self.minimumWidth(), min(self.width(), self._DEFAULT_WIDTH)),
            max(self.minimumHeight(), min(self.height(), self._DEFAULT_HEIGHT)),
        )
        self._apply_theme()
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry().adjusted(12, 12, -12, -12)
        self.resize(
            min(self.width(), available.width()),
            min(self.height(), available.height()),
        )
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _save_settings(self) -> None:
        if self._input_path and self._input_path.is_file():
            self._settings.setValue("last_input_dir", str(self._input_path.parent))
        self._settings.setValue("geometry", self.saveGeometry())

    def _apply_theme(self) -> None:
        self.setStyleSheet(_DARK_STYLE)

def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", value).strip(" .")
    return cleaned or "book"


def _downloads_directory() -> Path:
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DownloadLocation
    )
    return Path(location) if location else Path.home() / "Downloads"


def _epub_filename(input_path: Path) -> str:
    title = ""
    try:
        with PdfReader(input_path) as reader:
            title = reader.metadata.title.strip()
    except ConversionError:
        pass
    if not title or title.casefold() == "untitled":
        title = input_path.stem
    return f"{_safe_filename(title)}-EPUB.epub"


_DARK_STYLE = """
QMainWindow { background: #0e141b; }
QWidget { background: transparent; color: #edf3f7; }
QWidget#centralWidget { background: #151d26; }
QLabel { background: transparent; }
QFrame#pdfDropZone { background: #1b2530; border: 1px dashed #526273; border-radius: 16px; }
QFrame#pdfDropZone:hover { border-color: #708496; }
QFrame#pdfDropZone[dragActive="true"] { background: #17323a; border-color: #5bd6d2; }
QLabel#pdfDropIcon { background: #5bd6d2; color: #0d2227; border-radius: 12px; font-size: 17px; font-weight: 800; }
QLabel#pdfDropTitle { color: #f4f8fa; font-size: 17px; font-weight: 700; }
QLabel#pdfDropHint { color: #96a8b8; font-size: 12px; }
"""
