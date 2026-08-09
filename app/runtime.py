"""Runtime paths for source and PyInstaller executions."""

from __future__ import annotations

import sys
from pathlib import Path


def application_root() -> Path:
    """Return the repository root in development or the bundled app folder."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundled_path(*parts: str) -> Path:
    """Resolve a path stored beside the executable in a portable build."""
    return application_root().joinpath(*parts)
