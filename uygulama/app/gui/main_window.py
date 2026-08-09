"""Main PySide6 desktop interface for local PDF to EPUB conversion."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QGuiApplication
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
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


class MainWindow(QMainWindow):
    """Responsive desktop UI; all conversion work runs through ConversionWorker."""

    _NARROW_LAYOUT_BREAKPOINT = 760
    _NARROW_MINIMUM_HEIGHT = 620
    _DEFAULT_WIDTH = 720
    _DEFAULT_HEIGHT = 620

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings("PDFtoEPUB", "PDFtoEPUB")
        self._worker: ConversionWorker | None = None
        self._last_output: Path | None = None
        self.setWindowTitle("PDF to EPUB Converter")
        self.setMinimumSize(720, 460)
        self.resize(self._DEFAULT_WIDTH, self._DEFAULT_HEIGHT)
        self.setAcceptDrops(True)
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
        self._options_panel = self._create_options_panel()
        self._source_panel.setMinimumWidth(320)
        self._options_panel.setMinimumWidth(360)
        self._configuration_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._configuration_layout.setSpacing(12)
        self._configuration_layout.addWidget(self._source_panel, 1)
        self._configuration_layout.addWidget(self._options_panel, 1)
        layout.addLayout(self._configuration_layout)

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
        layout.addStretch(1)

        button_row = QHBoxLayout()
        self.open_epub_button = QPushButton("EPUB'ı Aç")
        self.open_folder_button = QPushButton("Klasörü Aç")
        self.open_epub_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.cancel_button = QPushButton("İptal")
        self.cancel_button.setEnabled(False)
        self.convert_button = QPushButton("EPUB'e Dönüştür")
        self.convert_button.setObjectName("convertButton")
        button_row.addWidget(self.open_epub_button)
        button_row.addWidget(self.open_folder_button)
        button_row.addStretch()
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.convert_button)
        layout.addLayout(button_row)

        self.convert_button.clicked.connect(self._start_conversion)
        self.cancel_button.clicked.connect(self._cancel_conversion)
        self.open_epub_button.clicked.connect(self._open_epub)
        self.open_folder_button.clicked.connect(self._open_folder)
        self._update_responsive_layout()

    def _create_source_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        input_group = QGroupBox("Girdi PDF")
        input_layout = QGridLayout(input_group)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("PDF dosyasını buraya bırakın veya seçin")
        browse_input = QPushButton("Gözat...")
        input_label = QLabel("PDF dosyası")
        input_layout.addWidget(input_label, 0, 0)
        input_layout.addWidget(self.input_edit, 0, 1)
        input_layout.addWidget(browse_input, 0, 2)
        layout.addWidget(input_group)

        browse_input.clicked.connect(self._browse_input)
        return panel

    def _create_options_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        options_group = QGroupBox("Dönüştürme Ayarları")
        options_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        options_layout = QGridLayout(options_group)
        options_layout.setContentsMargins(10, 8, 10, 8)
        options_layout.setHorizontalSpacing(12)
        options_layout.setVerticalSpacing(4)
        self.option_checks: dict[str, QCheckBox] = {}
        checkboxes = (
            ("use_ocr", "Metinsiz sayfalarda OCR kullan", True),
            ("include_images", "Görselleri ekle", True),
            ("optimize_images", "Görselleri optimize et", True),
            ("remove_page_numbers", "Sayfa numaralarını kaldır", True),
            ("remove_headers_footers", "Tekrarlanan üst/alt bilgileri kaldır", True),
            ("preserve_footnotes", "Algılanan dipnotları koru", True),
            ("detect_tables", "Temel tabloları algıla", True),
            ("detect_columns", "Çok sütunlu okuma sırasını algıla", True),
            ("detect_chapters", "Bölümleri algıla", True),
            ("extract_cover", "Kapağı ayıkla/oluştur", True),
        )
        for index, (key, label, checked) in enumerate(checkboxes):
            checkbox = QCheckBox(label)
            checkbox.setChecked(checked)
            checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.option_checks[key] = checkbox
            options_layout.addWidget(checkbox, index // 2, index % 2)
        options_layout.setColumnStretch(0, 1)
        options_layout.setColumnStretch(1, 1)
        layout.addWidget(options_group, 0, Qt.AlignmentFlag.AlignTop)

        return container

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls and any(url.toLocalFile().lower().endswith(".pdf") for url in urls):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() == ".pdf":
                self._set_input(path)
                event.acceptProposedAction()
                return

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._update_responsive_layout()

    def closeEvent(self, event: object) -> None:  # noqa: N802
        self._save_settings()
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)  # type: ignore[arg-type]

    def _browse_input(self) -> None:
        start = self._settings.value("last_input_dir", str(Path.home()))
        selected, _ = QFileDialog.getOpenFileName(
            self, "PDF Seç", str(start), "PDF dosyaları (*.pdf)"
        )
        if selected:
            self._set_input(Path(selected))

    def _set_input(self, path: Path) -> None:
        self.input_edit.setText(str(path))

    def _start_conversion(self) -> None:
        input_path = Path(self.input_edit.text().strip())
        if not input_path.is_file() or input_path.suffix.lower() != ".pdf":
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
        return ConversionOptions(
            **{name: checkbox.isChecked() for name, checkbox in self.option_checks.items()},
            ocr_language="tur",
            css_style_mode="reader",
        )

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
        self.convert_button.setEnabled(not running)
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
        for name, checkbox in self.option_checks.items():
            saved = self._settings.value(f"option/{name}")
            if saved is not None:
                checkbox.setChecked(str(saved).lower() in {"true", "1"})
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
        input_path = Path(self.input_edit.text())
        if input_path.is_file():
            self._settings.setValue("last_input_dir", str(input_path.parent))
        for name, checkbox in self.option_checks.items():
            self._settings.setValue(f"option/{name}", checkbox.isChecked())
        self._settings.setValue("geometry", self.saveGeometry())

    def _apply_theme(self) -> None:
        self.setStyleSheet(_DARK_STYLE)

    def _update_responsive_layout(self) -> None:
        direction = (
            QBoxLayout.Direction.TopToBottom
            if self.width() < self._NARROW_LAYOUT_BREAKPOINT
            else QBoxLayout.Direction.LeftToRight
        )
        if self._configuration_layout.direction() != direction:
            self._configuration_layout.setDirection(direction)
        self.setMinimumHeight(
            self._NARROW_MINIMUM_HEIGHT
            if direction == QBoxLayout.Direction.TopToBottom
            else 460
        )


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


_COMMON_STYLE = """
QPushButton#convertButton { font-weight: 700; padding: 7px 16px; }
"""
_DARK_STYLE = (
    _COMMON_STYLE
    + """
QMainWindow, QWidget { background: #20242a; color: #e8eaed; }
QGroupBox { border: 1px solid #4e5661; border-radius: 6px; margin-top: 7px; padding: 6px; }
QLineEdit, QPlainTextEdit { background: #2b3038; border: 1px solid #58616d; border-radius: 4px; padding: 3px 5px; color: #f2f4f7; }
QPushButton { background: #333a44; border: 1px solid #58616d; border-radius: 5px; padding: 5px; }
QPushButton#convertButton { background: #2f81c1; color: white; border: 0; border-radius: 6px; }
"""
)
