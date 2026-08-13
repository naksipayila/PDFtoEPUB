from types import SimpleNamespace

from app.gui.main_window import MainWindow


class FakeWorker:
    def __init__(self, running: bool = True) -> None:
        self.running = running
        self.cancelled = False

    def isRunning(self) -> bool:
        return self.running

    def cancel(self) -> None:
        self.cancelled = True


def test_close_waits_for_running_conversion() -> None:
    worker = FakeWorker()
    event = SimpleNamespace(ignored=False)
    event.ignore = lambda: setattr(event, "ignored", True)
    window = SimpleNamespace(
        _worker=worker,
        _close_when_worker_finishes=False,
        _save_settings=lambda: None,
    )

    MainWindow.closeEvent(window, event)

    assert worker.cancelled
    assert event.ignored
    assert window._close_when_worker_finishes


def test_window_closes_after_conversion_thread_finishes() -> None:
    window = SimpleNamespace(
        _close_when_worker_finishes=True,
        closed=False,
    )
    window.close = lambda: setattr(window, "closed", True)

    MainWindow._on_worker_finished(window)

    assert window.closed
    assert not window._close_when_worker_finishes


def test_terminal_worker_signals_do_not_reopen_ui_during_deferred_close() -> None:
    window = SimpleNamespace(_close_when_worker_finishes=True)

    MainWindow._on_success(window, object())
    MainWindow._on_failure(window, "error")
    MainWindow._on_cancelled(window)
