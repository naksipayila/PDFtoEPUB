"""Main PySide6 desktop interface for local PDF to EPUB conversion."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QGuiApplication,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFrame,
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

LOGGER = logging.getLogger(__name__)
_COMPLETION_SOUND_PATH = Path(__file__).resolve().parents[2] / "assets" / "ses.mp3"


class PdfDropZone(QFrame):
    """Visual PDF target that reports a dropped local PDF path."""

    pdf_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("pdfDropZone")
        self.setMinimumHeight(206)
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

        layout.addWidget(self._icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._name_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hint_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_pdf(self, path: Path) -> None:
        self._icon_label.setText("PDF")
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

    _DEFAULT_WIDTH = 680
    _DEFAULT_HEIGHT = 440

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self._settings = QSettings("PDFtoEPUB", "PDFtoEPUB")
        self._worker: ConversionWorker | None = None
        self._input_path: Path | None = None
        self._last_output: Path | None = None
        self._audio_output = QAudioOutput(self)
        self._completion_player = QMediaPlayer(self)
        self._completion_player.setAudioOutput(self._audio_output)
        self._completion_player.errorOccurred.connect(self._on_audio_error)
        self.setWindowTitle("PDF to EPUB Converter")
        self.setMinimumSize(640, 400)
        self.resize(self._DEFAULT_WIDTH, self._DEFAULT_HEIGHT)
        self._build_interface()
        self._restore_settings()
        self.setFixedSize(self._DEFAULT_WIDTH, self._DEFAULT_HEIGHT)

    def _build_interface(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)

        self._source_panel = self._create_source_panel()
        self._source_panel.setMinimumWidth(320)
        layout.addWidget(self._source_panel)

        self.progress_group = QWidget()
        self.progress_group.setObjectName("progressGroup")
        self.progress_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        progress_layout = QVBoxLayout(self.progress_group)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(7)
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        self.status_label.setVisible(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setTextVisible(True)
        self.log_title = QLabel("İşlem günlüğü")
        self.log_title.setObjectName("logTitle")
        self.log_title.setVisible(False)
        self.log_panel = QPlainTextEdit()
        self.log_panel.setObjectName("logPanel")
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumBlockCount(500)
        self.log_panel.setFixedHeight(92)
        self.log_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.log_title)
        progress_layout.addWidget(self.log_panel)
        self.progress_group.setVisible(False)
        layout.addWidget(self.progress_group)

        self.action_bar = QWidget()
        self.action_bar.setObjectName("actionBar")
        button_row = QHBoxLayout(self.action_bar)
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        self.open_epub_button = QPushButton("EPUB'ı Aç")
        self.open_epub_button.setObjectName("openEpubButton")
        self.open_folder_button = QPushButton("Klasörü Aç")
        self.open_folder_button.setObjectName("openFolderButton")
        self.open_epub_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.open_epub_button.setVisible(False)
        self.open_folder_button.setVisible(False)
        self.cancel_button = QPushButton("İptal")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setVisible(False)
        button_row.addWidget(self.open_epub_button)
        button_row.addWidget(self.open_folder_button)
        button_row.addStretch()
        button_row.addWidget(self.cancel_button)
        self.action_bar.setVisible(False)
        layout.addWidget(self.action_bar)

        self.cancel_button.clicked.connect(self._cancel_conversion)
        self.open_epub_button.clicked.connect(self._open_epub)
        self.open_folder_button.clicked.connect(self._open_folder)

    def _create_source_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        input_group = QWidget()
        input_layout = QVBoxLayout(input_group)
        input_layout.setContentsMargins(0, 0, 0, 0)
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
        self.log_title.setVisible(False)
        self.log_panel.setVisible(False)
        self.open_epub_button.setVisible(False)
        self.open_folder_button.setVisible(False)
        self.open_epub_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.progress_group.setVisible(True)
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
        return ConversionOptions(
            ocr_language="tur",
            include_images=False,
            extract_cover=True,
            css_style_mode="reader",
        )

    def _cancel_conversion(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.status_label.setText("İptal istendi. Geçerli sayfa tamamlanıyor...")
            self.cancel_button.setEnabled(False)

    def _on_progress(self, event: ProgressEvent) -> None:
        self.status_label.setVisible(True)
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
        self._play_completion_sound()
        self._set_running(False)
        self.progress_bar.setValue(100)
        self.status_label.setVisible(True)
        self.status_label.setText("EPUB başarıyla oluşturuldu.")
        self.open_epub_button.setEnabled(self._last_output is not None)
        self.open_folder_button.setEnabled(self._last_output is not None)
        self.open_epub_button.setVisible(True)
        self.open_folder_button.setVisible(True)
        self.action_bar.setVisible(True)
        summary = report.summary() if hasattr(report, "summary") else ""
        self._append_log(summary)

    def _play_completion_sound(self) -> None:
        sound_path = _COMPLETION_SOUND_PATH
        if not sound_path.is_file():
            LOGGER.warning("Conversion completion sound not found: %s", sound_path)
            return
        self._completion_player.stop()
        self._completion_player.setSource(QUrl.fromLocalFile(str(sound_path)))
        self._completion_player.play()

    def _on_audio_error(self, _error: object, error_string: str) -> None:
        LOGGER.warning("Conversion completion sound could not be played: %s", error_string)

    def _on_failure(self, message: str) -> None:
        self._set_running(False)
        self.status_label.setVisible(True)
        self.status_label.setText("Dönüştürme başarısız oldu.")
        self._append_log(f"HATA: {message}")
        self._show_error(message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self.status_label.setVisible(True)
        self.status_label.setText("Dönüştürme iptal edildi.")
        self._append_log("Dönüştürme kullanıcı tarafından iptal edildi.")

    def _set_running(self, running: bool) -> None:
        self.cancel_button.setEnabled(running)
        self.cancel_button.setVisible(running)
        if running:
            self.action_bar.setVisible(True)
        elif not self.open_epub_button.isVisible():
            self.action_bar.setVisible(False)

    def _open_epub(self) -> None:
        if self._last_output and self._last_output.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output)))

    def _open_folder(self) -> None:
        if self._last_output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output.parent)))

    def _append_log(self, message: str) -> None:
        self.log_title.setVisible(True)
        self.log_panel.setVisible(True)
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
QLabel#statusLabel { color: #b7c5d0; font-size: 12px; font-weight: 600; }
QProgressBar { background: #0f161d; border: 1px solid #2b3947; border-radius: 8px; text-align: center; color: #dce7ed; font-size: 10px; }
QProgressBar::chunk { background: #3dbec0; border-radius: 7px; }
QLabel#logTitle { color: #7f93a4; font-size: 11px; font-weight: 700; }
QPlainTextEdit { background: #10171f; border: 1px solid #2b3947; border-radius: 10px; padding: 7px 9px; color: #cbd7df; font-size: 11px; }
QPushButton { background: #263442; color: #e7f0f4; border: 1px solid #3c5060; border-radius: 9px; min-height: 34px; padding: 0 14px; font-weight: 600; }
QPushButton:hover { background: #304553; border-color: #5bd6d2; }
QPushButton:pressed { background: #1f2b36; }
QPushButton:disabled { background: #1b242d; color: #60717f; border-color: #27333f; }
QPushButton#openEpubButton { background: #5bd6d2; color: #0d2227; border-color: #5bd6d2; font-weight: 800; }
QPushButton#openEpubButton:hover { background: #79e3de; border-color: #79e3de; }
QPushButton#cancelButton { background: transparent; color: #9eb0bd; border-color: #334452; }
QPushButton#cancelButton:hover { color: #e7f0f4; border-color: #718694; }
"""
