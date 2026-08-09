"""Main PySide6 desktop interface for local PDF to EPUB conversion."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QSettings, QUrl
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
    _DEFAULT_WIDTH = 1120
    _DEFAULT_HEIGHT = 700

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings("PDFtoEPUB", "PDFtoEPUB")
        self._worker: ConversionWorker | None = None
        self._last_output: Path | None = None
        self.setWindowTitle("PDF'den EPUB'e Dönüştürücü")
        self.setMinimumSize(760, 600)
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

        title = QLabel("PDF to EPUB")
        title.setObjectName("appTitle")
        subtitle = QLabel("Çevrimdışı, yerleşim duyarlı EPUB 3 dönüşümü")
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

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
        progress_layout = QVBoxLayout(progress_group)
        self.status_label = QLabel("Başlamak için bir PDF seçin.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.log_panel = QPlainTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumBlockCount(500)
        self.log_panel.setMinimumHeight(100)
        self.log_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.log_panel)
        progress_layout.setStretch(2, 1)
        layout.addWidget(progress_group, 1)

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
        input_group = QGroupBox("Girdi PDF")
        input_layout = QGridLayout(input_group)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("PDF dosyasını buraya bırakın veya seçin")
        browse_input = QPushButton("Gözat...")
        input_layout.addWidget(QLabel("PDF dosyası"), 0, 0)
        input_layout.addWidget(self.input_edit, 0, 1)
        input_layout.addWidget(browse_input, 0, 2)
        layout.addWidget(input_group)

        output_group = QGroupBox("Çıktı")
        output_layout = QGridLayout(output_group)
        self.output_directory_edit = QLineEdit()
        self.output_name_edit = QLineEdit()
        output_browse = QPushButton("Gözat...")
        output_layout.addWidget(QLabel("Klasör"), 0, 0)
        output_layout.addWidget(self.output_directory_edit, 0, 1)
        output_layout.addWidget(output_browse, 0, 2)
        output_layout.addWidget(QLabel("Dosya adı"), 1, 0)
        output_layout.addWidget(self.output_name_edit, 1, 1, 1, 2)
        layout.addWidget(output_group)

        flow_group = QGroupBox("Kullanım")
        flow_layout = QVBoxLayout(flow_group)
        flow_layout.setSpacing(4)
        for step in (
            "1. PDF dosyasını seçin veya sürükleyin.",
            "2. Çıktı klasörünü ve dosya adını kontrol edin.",
            "3. Dönüşüm seçeneklerini gözden geçirin.",
            "4. EPUB'e Dönüştür düğmesine basın.",
        ):
            flow_step = QLabel(step)
            flow_step.setObjectName("flowStep")
            flow_layout.addWidget(flow_step)
        layout.addWidget(flow_group)
        browse_input.clicked.connect(self._browse_input)
        output_browse.clicked.connect(self._browse_output)
        self.input_edit.editingFinished.connect(self._populate_pdf_metadata)
        return panel

    def _create_options_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        options_group = QGroupBox("Dönüştürme Ayarları")
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
        layout.addWidget(options_group)

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

    def _browse_output(self) -> None:
        start = self._settings.value("last_output_dir", str(Path.home()))
        selected = QFileDialog.getExistingDirectory(self, "Çıktı klasörünü seçin", str(start))
        if selected:
            self.output_directory_edit.setText(selected)

    def _set_input(self, path: Path) -> None:
        self.input_edit.setText(str(path))
        self.output_directory_edit.setText(str(path.parent))
        self.output_name_edit.setText(f"{_safe_filename(path.stem)}.epub")
        self._populate_pdf_metadata()

    def _populate_pdf_metadata(self) -> None:
        path = Path(self.input_edit.text().strip())
        if not path.is_file() or path.suffix.lower() != ".pdf":
            return
        try:
            with PdfReader(path) as reader:
                metadata = reader.metadata
        except ConversionError:
            return
        if self.output_name_edit.text().strip() in {"", f"{path.stem}.epub"}:
            self.output_name_edit.setText(f"{_safe_filename(metadata.title)}.epub")

    def _start_conversion(self) -> None:
        input_path = Path(self.input_edit.text().strip())
        output_dir = Path(self.output_directory_edit.text().strip())
        filename = self.output_name_edit.text().strip()
        if not input_path.is_file() or input_path.suffix.lower() != ".pdf":
            self._show_error("Geçerli bir PDF dosyası seçin.")
            return
        if not output_dir.is_dir():
            self._show_error("Geçerli bir çıktı klasörü seçin.")
            return
        if not filename:
            self._show_error("Bir EPUB dosya adı girin.")
            return
        output_path = output_dir / (
            filename if filename.lower().endswith(".epub") else f"{filename}.epub"
        )
        self._last_output = output_path
        self.progress_bar.setValue(0)
        self.log_panel.clear()
        self._set_running(True)
        self._append_log(f"Dönüştürme başlatılıyor: {input_path.name}")
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
        self.output_directory_edit.setText(str(self._settings.value("last_output_dir", "")))
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
        self._settings.setValue("last_output_dir", self.output_directory_edit.text())
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


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", value).strip(" .")
    return cleaned or "book"


_COMMON_STYLE = """
QLabel#appTitle { font-size: 22px; font-weight: 700; }
QLabel#appSubtitle { color: palette(mid); margin-bottom: 2px; }
QLabel#flowStep { padding: 2px 0; }
QPushButton#convertButton { font-weight: 700; padding: 7px 16px; }
"""
_DARK_STYLE = (
    _COMMON_STYLE
    + """
QMainWindow, QWidget { background: #20242a; color: #e8eaed; }
QGroupBox { border: 1px solid #4e5661; border-radius: 6px; margin-top: 7px; padding: 6px; }
QLineEdit, QPlainTextEdit, QComboBox { background: #2b3038; border: 1px solid #58616d; border-radius: 4px; padding: 3px 5px; color: #f2f4f7; }
QPushButton { background: #333a44; border: 1px solid #58616d; border-radius: 5px; padding: 5px; }
QPushButton#convertButton { background: #2f81c1; color: white; border: 0; border-radius: 6px; }
"""
)
