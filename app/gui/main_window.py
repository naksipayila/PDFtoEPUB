"""Main PySide6 desktop interface for local PDF to EPUB conversion."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QSettings, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
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
    QScrollArea,
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

    _NARROW_LAYOUT_BREAKPOINT = 1080

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings("PDFtoEPUB", "PDFtoEPUB")
        self._worker: ConversionWorker | None = None
        self._last_output: Path | None = None
        self.setWindowTitle("PDF'den EPUB'e Dönüştürücü")
        self.setMinimumSize(640, 540)
        self.setAcceptDrops(True)
        self._build_interface()
        self._restore_settings()

    def _build_interface(self) -> None:
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(self._scroll_area)

        central = QWidget()
        self._scroll_area.setWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        title = QLabel("PDF to EPUB")
        title.setObjectName("appTitle")
        subtitle = QLabel("Çevrimdışı, yerleşim duyarlı EPUB 3 dönüşümü")
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self._source_panel = self._create_source_panel()
        self._options_panel = self._create_options_panel()
        self._source_panel.setMinimumWidth(360)
        self._options_panel.setMinimumWidth(420)
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
        self.log_panel.setFixedHeight(140)
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
        input_layout.addWidget(QLabel("Parola"), 1, 0)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Yalnızca şifreli PDF'ler için")
        input_layout.addWidget(self.password_edit, 1, 1, 1, 2)
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

        layout.addStretch()
        browse_input.clicked.connect(self._browse_input)
        output_browse.clicked.connect(self._browse_output)
        self.input_edit.editingFinished.connect(self._populate_pdf_metadata)
        return panel

    def _create_options_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        options_group = QGroupBox("Dönüştürme Ayarları")
        options_layout = QVBoxLayout(options_group)
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
        for key, label, checked in checkboxes:
            checkbox = QCheckBox(label)
            checkbox.setChecked(checked)
            self.option_checks[key] = checkbox
            options_layout.addWidget(checkbox)
        language_row = QHBoxLayout()
        language_row.addWidget(QLabel("OCR dili"))
        self.ocr_language = QComboBox()
        self.ocr_language.addItem("Türkçe", "tur")
        language_row.addWidget(self.ocr_language)
        options_layout.addLayout(language_row)
        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("EPUB görünümü"))
        self.css_style = QComboBox()
        self.css_style.addItem("Okuyucu", "reader")
        self.css_style.addItem("Kompakt", "compact")
        style_row.addWidget(self.css_style)
        options_layout.addLayout(style_row)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Tema"))
        self.theme = QComboBox()
        self.theme.addItem("Sistem", "system")
        self.theme.addItem("Açık", "light")
        self.theme.addItem("Koyu", "dark")
        theme_row.addWidget(self.theme)
        options_layout.addLayout(theme_row)
        self.theme.currentIndexChanged.connect(self._on_theme_changed)
        layout.addWidget(options_group)

        help_box = QFrame()
        help_box.setObjectName("helpBox")
        help_layout = QVBoxLayout(help_box)
        help_layout.addWidget(QLabel("Yerleşim duyarlı dönüşüm"))
        help_layout.addWidget(
            _word_wrapped_label(
                "Metin, başlıklar, sütunlar, tekrarlanan kenar içerikleri, görseller, listeler, "
                "altyazılar ve basit tablolar EPUB oluşturulmadan önce yerel olarak yorumlanır."
            )
        )
        layout.addWidget(help_box)
        layout.addStretch()
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
            with PdfReader(path, self.password_edit.text() or None) as reader:
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
            ocr_language=str(self.ocr_language.currentData()),
            css_style_mode=str(self.css_style.currentData()),
            pdf_password=self.password_edit.text() or None,
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
        self.ocr_language.setCurrentIndex(0)
        for name, checkbox in self.option_checks.items():
            saved = self._settings.value(f"option/{name}")
            if saved is not None:
                checkbox.setChecked(str(saved).lower() in {"true", "1"})
        saved_theme = str(self._settings.value("theme", "system"))
        theme_key = {"System": "system", "Light": "light", "Dark": "dark"}.get(
            saved_theme, saved_theme
        )
        self.theme.setCurrentIndex(max(0, self.theme.findData(theme_key)))
        geometry = self._settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        self._apply_theme(str(self.theme.currentData()))

    def _save_settings(self) -> None:
        input_path = Path(self.input_edit.text())
        if input_path.is_file():
            self._settings.setValue("last_input_dir", str(input_path.parent))
        self._settings.setValue("last_output_dir", self.output_directory_edit.text())
        self._settings.setValue("ocr_language", self.ocr_language.currentData())
        for name, checkbox in self.option_checks.items():
            self._settings.setValue(f"option/{name}", checkbox.isChecked())
        self._settings.setValue("theme", self.theme.currentData())
        self._settings.setValue("geometry", self.saveGeometry())

    def _on_theme_changed(self, _index: int) -> None:
        self._apply_theme(str(self.theme.currentData()))

    def _apply_theme(self, name: str) -> None:
        if name == "dark":
            self.setStyleSheet(_DARK_STYLE)
        elif name == "light":
            self.setStyleSheet(_LIGHT_STYLE)
        else:
            self.setStyleSheet(_SYSTEM_STYLE)

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


def _word_wrapped_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    return label


_SYSTEM_STYLE = """
QLabel#appTitle { font-size: 22px; font-weight: 700; }
QLabel#appSubtitle { color: palette(mid); margin-bottom: 2px; }
QFrame#helpBox { border: 1px solid palette(midlight); border-radius: 6px; }
QPushButton#convertButton { font-weight: 700; padding: 7px 16px; }
"""
_LIGHT_STYLE = (
    _SYSTEM_STYLE
    + """
QMainWindow { background: #f6f7f9; }
QGroupBox { background: white; border: 1px solid #d6d9df; border-radius: 6px; margin-top: 7px; padding: 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; font-weight: 600; }
QPushButton#convertButton { background: #1769aa; color: white; border: 0; border-radius: 6px; }
"""
)
_DARK_STYLE = (
    _SYSTEM_STYLE
    + """
QMainWindow, QWidget { background: #20242a; color: #e8eaed; }
QGroupBox { border: 1px solid #4e5661; border-radius: 6px; margin-top: 7px; padding: 6px; }
QLineEdit, QPlainTextEdit, QComboBox { background: #2b3038; border: 1px solid #58616d; border-radius: 4px; padding: 3px 5px; color: #f2f4f7; }
QPushButton { background: #333a44; border: 1px solid #58616d; border-radius: 5px; padding: 5px; }
QPushButton#convertButton { background: #2f81c1; color: white; border: 0; border-radius: 6px; }
QFrame#helpBox { border-color: #58616d; }
"""
)
