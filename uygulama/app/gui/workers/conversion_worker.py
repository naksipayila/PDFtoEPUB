"""Qt worker that keeps conversion work outside the GUI thread."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.core.config import ConversionOptions
from app.core.converter import PdfToEpubConverter
from app.core.errors import ConversionCancelled, ConversionError
from app.core.models import ProgressEvent

LOGGER = logging.getLogger(__name__)


class ConversionWorker(QThread):
    """Run a single conversion with cooperative page-level cancellation."""

    progress_changed = Signal(object)
    conversion_succeeded = Signal(object)
    conversion_failed = Signal(str)
    conversion_cancelled = Signal()

    def __init__(self, input_path: Path, output_path: Path, options: ConversionOptions) -> None:
        super().__init__()
        self._input_path = input_path
        self._output_path = output_path
        self._options = options
        self._cancel_requested = threading.Event()

    def cancel(self) -> None:
        self._cancel_requested.set()

    def run(self) -> None:
        try:
            report = PdfToEpubConverter().convert(
                self._input_path,
                self._output_path,
                self._options,
                self._on_progress,
                self._cancel_requested.is_set,
            )
        except ConversionCancelled:
            self.conversion_cancelled.emit()
        except (ConversionError, FileNotFoundError, PermissionError, OSError) as error:
            LOGGER.exception("Conversion failed")
            self.conversion_failed.emit(str(error))
        except Exception:
            LOGGER.exception("Unexpected conversion failure")
            self.conversion_failed.emit(
                "Beklenmeyen bir hata oluştu. Ayrıntılar için uygulama günlüğünü inceleyin."
            )
        else:
            self.conversion_succeeded.emit(report)

    def _on_progress(self, event: ProgressEvent) -> None:
        self.progress_changed.emit(event)
