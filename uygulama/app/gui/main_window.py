"""Main PySide6 desktop interface for local PDF to EPUB conversion."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QFileInfo, QSettings, QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QGuiApplication,
)
from PySide6.QtWidgets import (
    QFileIconProvider,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
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
        self.setMinimumHeight(170)
        self.setProperty("dragActive", False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_label = QLabel("PDF")
        self._icon_label.setObjectName("pdfDropIcon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedSize(72, 72)

        self._name_label = QLabel("PDF dosyasını buraya sürükleyin")
        self._name_label.setObjectName("pdfDropTitle")
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setWordWrap(True)

        self._hint_label = QLabel("Bıraktığınızda dönüşüm otomatik başlar")
        self._hint_label.setObjectName("pdfDropHint")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._name_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hint_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_pdf(self, path: Path) -> None:
        icon = QFileIconProvider().icon(QFileInfo(str(path)))
        pixmap = icon.pixmap(64, 64)
        if pixmap.isNull():
            self._icon_label.setText("PDF")
        else:
            self._icon_label.setText("")
            self._icon_label.setPixmap(pixmap)
        self._name_label.setText(path.name)
        self._hint_label.setText("Dönüşüm başlatılıyor...")

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

    _DEFAULT_WIDTH = 720
    _DEFAULT_HEIGHT = 460

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings("PDFtoEPUB", "PDFtoEPUB")
        self._worker: ConversionWorker | None = None
        self._input_path: Path | None = None
        self._last_output: Path | None = None
        self.setWindowTitle("PDF to EPUB Converter")
        self.setMinimumSize(720, 460)
        self.resize(self._DEFAULT_WIDTH, self._DEFAULT_HEIGHT)
        self._build_interface()
        self._restore_settings()

    def _build_interface(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)

        self._source_panel = self._create_source_panel()
        self._source_panel.setMinimumWidth(320)
        layout.addWidget(self._source_panel)

        progress_group = QGroupBox("Dönüştürme")
        progress_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        progress_layout = QVBoxLayout(progress_group)
        self.status_label = QLabel("Başlamak için bir PDF seçin.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.log_panel = QPlainTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumBlockCount(500)
        self.log_panel.setFixedHeight(140)
        self.log_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.log_panel)
        layout.addWidget(progress_group)

        button_row = QHBoxLayout()
        self.open_epub_button = QPushButton("EPUB'ı Aç")
        self.open_folder_button = QPushButton("Klasörü Aç")
        self.open_epub_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.cancel_button = QPushButton("İptal")
        self.cancel_button.setEnabled(False)
        button_row.addWidget(self.open_epub_button)
        button_row.addWidget(self.open_folder_button)
        button_row.addStretch()
        button_row.addWidget(self.cancel_button)
        layout.addLayout(button_row)

        self.cancel_button.clicked.connect(self._cancel_conversion)
        self.open_epub_button.clicked.connect(self._open_epub)
        self.open_folder_button.clicked.connect(self._open_folder)

    def _create_source_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        input_group = QGroupBox("PDF Seçimi")
        input_layout = QVBoxLayout(input_group)
        self.drop_zone = PdfDropZone()
        input_layout.addWidget(self.drop_zone)
        layout.addWidget(input_group)
        self.drop_zone.pdf_dropped.connect(self._set_input)
        return panel

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
        self._last_output = output_path
        self.progress_bar.setValue(0)
        self.log_panel.clear()
        self._set_running(True)
        self._append_log(f"Dönüştürme başlatılıyor: {input_path.name}")
        self._append_log(f"Çıktı: {output_path}")
        self._worker = ConversionWorker(input_path, output_path, self._options())
        self._worker.progress_changed.connect(self._on_progress)
        self._worker.conversion_succeeded.connect(self._on_success)
        self._worker.conversion_failed.connect(self._on_failure)
        self._worker.conversion_cancelled.connect(self._on_cancelled)
        self._worker.start()

    def _options(self) -> ConversionOptions:
        return ConversionOptions(ocr_language="tur", css_style_mode="reader")

    def _cancel_conversion(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.status_label.setText("İptal istendi. Geçerli sayfa tamamlanıyor...")
            self.cancel_button.setEnabled(False)

    def _on_progress(self, event: ProgressEvent) -> None:
        self.status_label.setText(event.message)
        self._append_log(event.message)
        if event.total:
            if event.stage == "extracting":
                self.progress_bar.setValue(min(85, event.percentage * 85 // 100))
            elif event.stage == "layout":
                self.progress_bar.setValue(90)
            elif event.stage == "building":
                self.progress_bar.setValue(94)
            elif event.stage == "validating":
                self.progress_bar.setValue(98)
            elif event.stage == "complete":
                self.progress_bar.setValue(100)

    def _on_success(self, report: object) -> None:
        self._set_running(False)
        self.progress_bar.setValue(100)
        self.status_label.setText("EPUB başarıyla oluşturuldu.")
        self.open_epub_button.setEnabled(self._last_output is not None)
        self.open_folder_button.setEnabled(self._last_output is not None)
        summary = report.summary() if hasattr(report, "summary") else ""
        self._append_log(summary)
        QMessageBox.information(self, "Dönüştürme tamamlandı", "EPUB başarıyla oluşturuldu.")

    def _on_failure(self, message: str) -> None:
        self._set_running(False)
        self.status_label.setText("Dönüştürme başarısız oldu.")
        self._append_log(f"HATA: {message}")
        self._show_error(message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self.status_label.setText("Dönüştürme iptal edildi.")
        self._append_log("Dönüştürme kullanıcı tarafından iptal edildi.")

    def _set_running(self, running: bool) -> None:
        self.cancel_button.setEnabled(running)

    def _open_epub(self) -> None:
        if self._last_output and self._last_output.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output)))

    def _open_folder(self) -> None:
        if self._last_output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output.parent)))

    def _append_log(self, message: str) -> None:
        self.log_panel.appendPlainText(message)

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Dönüştürme hatası", message)

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
QMainWindow, QWidget { background: #20242a; color: #e8eaed; }
QGroupBox { border: 1px solid #4e5661; border-radius: 6px; margin-top: 7px; padding: 6px; }
QPlainTextEdit { background: #2b3038; border: 1px solid #58616d; border-radius: 4px; padding: 3px 5px; color: #f2f4f7; }
QFrame#pdfDropZone { background: #2b3038; border: 2px dashed #58616d; border-radius: 10px; }
QFrame#pdfDropZone[dragActive="true"] { background: #263849; border-color: #2f81c1; }
QLabel#pdfDropIcon { color: #8fa4b8; font-size: 20px; font-weight: 700; }
QLabel#pdfDropTitle { color: #f2f4f7; font-size: 15px; font-weight: 700; }
QLabel#pdfDropHint { color: #aab3bf; }
QPushButton { background: #333a44; border: 1px solid #58616d; border-radius: 5px; padding: 5px; }
"""
