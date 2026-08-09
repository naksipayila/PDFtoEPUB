"""Conservative text repair for common PDF extraction artifacts."""

from __future__ import annotations

import re
import unicodedata

_LIGATURES = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"})
_CONTROL_CHARS = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]")
_WHITESPACE = re.compile(r"[\t\r\n\u00a0\u2007\u202f ]+")


def normalize_text(value: str) -> str:
    """Normalize whitespace and compatibility ligatures without rewriting punctuation."""
    normalized = unicodedata.normalize("NFC", value).translate(_LIGATURES)
    normalized = normalized.replace("\u00ad", "")
    normalized = _CONTROL_CHARS.sub("", normalized)
    return _WHITESPACE.sub(" ", normalized).strip()


def join_line_text(previous: str, current: str) -> str:
    """Join visual lines while repairing only clear discretionary hyphenation."""
    current = current.strip()
    if previous.endswith("-") and current[:1].islower() and len(previous) > 2:
        return previous[:-1] + current
    return f"{previous.rstrip()} {current}".strip()
