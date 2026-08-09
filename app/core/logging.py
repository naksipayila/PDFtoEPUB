"""Shared file and console logging setup."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_file: Path | None = None, verbose: bool = False) -> None:
    """Configure application logging once without duplicating handlers."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    if root.handlers:
        return
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(formatter)
    root.addHandler(console)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
