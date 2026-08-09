"""Small, reader-friendly stylesheet variants."""

from __future__ import annotations


def stylesheet(mode: str = "reader") -> str:
    """Return reflowable CSS that lets the reading system control typography."""
    base = """@charset \"utf-8\";
html { font-size: 100%; }
body { line-height: 1.5; margin: 5%; }
h1, h2, h3, h4 { line-height: 1.2; margin: 1.5em 0 0.6em; page-break-after: avoid; }
p { margin: 0 0 0.8em; orphans: 2; widows: 2; }
li { margin-bottom: 0.25em; }
img { display: block; height: auto; margin: 0 auto; max-width: 100%; }
figure { break-inside: avoid; margin: 1.2em auto; text-align: center; }
figcaption { font-size: 0.9em; font-style: italic; margin-top: 0.45em; }
table { border-collapse: collapse; margin: 1em auto; max-width: 100%; }
th, td { border: 1px solid #888; padding: 0.35em; vertical-align: top; }
"""
    if mode == "compact":
        return base.replace("margin: 5%;", "margin: 2%;").replace(
            "line-height: 1.5", "line-height: 1.35"
        )
    return base
