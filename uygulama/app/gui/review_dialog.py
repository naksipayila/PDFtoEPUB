"""Side-by-side source page and editable EPUB text review dialog."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import ConversionError
from app.core.models import ConversionReport
from app.epub.review import EpubTextReview, ReviewEntry


class EpubReviewDialog(QDialog):
    """Review source-linked EPUB text without rerunning conversion."""

    def __init__(
        self,
        pdf_path: Path,
        epub_path: Path,
        report: ConversionReport | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._review = EpubTextReview(epub_path)
        self._document = fitz.open(pdf_path)
        self._report = report
        self._current_entries: list[ReviewEntry] = []
        self._current_key: str | None = None
        self.setWindowTitle("EPUB Metnini Gözden Geçir")
        self.resize(1120, 720)
        self.setMinimumSize(900, 600)
        self._build_interface()
        initial_page = self._recommended_page()
        self._page_spin.setValue(initial_page)
        self._load_page(initial_page)

    def done(self, result: int) -> None:
        if not self._document.is_closed:
            self._document.close()
        super().done(result)

    def _build_interface(self) -> None:
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Kaynak sayfa:"))
        self._page_spin = QSpinBox()
        self._page_spin.setRange(1, max(1, self._document.page_count))
        self._page_spin.valueChanged.connect(self._load_page)
        header.addWidget(self._page_spin)
        self._quality_label = QLabel()
        self._quality_label.setWordWrap(True)
        header.addWidget(self._quality_label, stretch=1)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        source_scroll = QScrollArea()
        source_scroll.setWidgetResizable(True)
        self._source_image = QLabel()
        self._source_image.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        source_scroll.setWidget(self._source_image)
        splitter.addWidget(source_scroll)

        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.addWidget(QLabel("EPUB metin öğeleri"))
        self._entry_list = QListWidget()
        self._entry_list.currentRowChanged.connect(self._select_entry)
        editor_layout.addWidget(self._entry_list, stretch=1)
        editor_layout.addWidget(QLabel("Seçili öğe"))
        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText("Bu sayfada düzenlenebilir metin bulunamadı.")
        editor_layout.addWidget(self._editor, stretch=1)
        splitter.addWidget(editor_panel)
        splitter.setSizes([540, 540])
        layout.addWidget(splitter, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            "Düzeltmeleri Kaydet"
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_page(self, page_number: int) -> None:
        self._commit_current_entry()
        page = self._document.load_page(page_number - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
        preview = QPixmap()
        preview.loadFromData(pixmap.tobytes("png"))
        self._source_image.setPixmap(preview)

        self._current_entries = self._review.entries_for_page(page_number)
        self._entry_list.clear()
        for entry in self._current_entries:
            summary = " ".join(entry.text.split())
            if len(summary) > 100:
                summary = f"{summary[:97]}..."
            self._entry_list.addItem(f"{entry.kind}: {summary}")
        self._quality_label.setText(self._quality_message(page_number))
        self._editor.clear()
        self._editor.setEnabled(bool(self._current_entries))
        self._current_key = None
        if self._current_entries:
            self._entry_list.setCurrentRow(0)

    def _select_entry(self, row: int) -> None:
        self._commit_current_entry()
        if not 0 <= row < len(self._current_entries):
            self._current_key = None
            self._editor.clear()
            return
        entry = self._current_entries[row]
        self._current_key = entry.key
        self._editor.setPlainText(entry.text)

    def _commit_current_entry(self) -> None:
        if self._current_key is not None:
            self._review.update(self._current_key, self._editor.toPlainText())

    def _save(self) -> None:
        self._commit_current_entry()
        try:
            self._review.save()
        except (ConversionError, OSError, ValueError, RuntimeError) as error:
            QMessageBox.critical(self, "Düzeltme kaydedilemedi", str(error))
            return
        QMessageBox.information(
            self,
            "Düzeltmeler kaydedildi",
            "EPUB yeniden doğrulandı ve düzeltmeler güvenle kaydedildi.",
        )
        self.accept()

    def _recommended_page(self) -> int:
        if self._report is not None:
            for issue in self._report.issues:
                if (
                    issue.page_number is not None
                    and issue.code.startswith("low_ocr_confidence")
                ):
                    return issue.page_number
        return self._review.pages[0] if self._review.pages else 1

    def _quality_message(self, page_number: int) -> str:
        if self._report is None:
            return ""
        messages = [
            issue.message
            for issue in self._report.issues
            if issue.page_number == page_number
        ]
        return " | ".join(messages)
