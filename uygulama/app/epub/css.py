"""Small, reader-friendly stylesheet variants."""

from __future__ import annotations


def stylesheet(mode: str = "reader") -> str:
    """Return reflowable CSS that lets the reading system control typography."""
    base = """@charset \"utf-8\";
html { font-size: 100%; }
body { line-height: 1.5; margin: 5%; }
h1, h2, h3, h4 { font-weight: 700; line-height: 1.2; margin: 1.5em 0 0.6em; page-break-after: avoid; }
p { margin: 0 0 0.8em; orphans: 2; widows: 2; }
li { margin-bottom: 0.25em; }
img { display: block; height: auto; margin: 0 auto; max-width: 100%; }
figure { break-inside: avoid; margin: 1.2em auto; text-align: center; }
figcaption { font-size: 0.9em; font-style: italic; margin-top: 0.45em; }
aside { font-size: 0.9em; margin: 0.7em 0; }
.footnote-label { font-weight: 700; }
table { border-collapse: collapse; margin: 1em auto; max-width: 100%; }
th, td { border: 1px solid #888; padding: 0.35em; vertical-align: top; }
.printed-toc { margin: 0.8em 0 1.2em; }
.printed-toc ol { list-style: none; margin: 0; padding: 0; }
.printed-toc-entry { align-items: baseline; break-inside: avoid; display: flex; gap: 0.35em; margin: 0 0 0.45em; page-break-inside: avoid; }
.printed-toc-title { min-width: 0; }
.printed-toc-leader { border-bottom: 1px dotted currentColor; flex: 1 1 1.5em; min-width: 1.5em; }
.printed-toc-page { flex: none; font-variant-numeric: tabular-nums; text-align: right; }
.printed-toc-level-1 { padding-left: 1em; padding-inline-start: 1em; }
.printed-toc-level-2 { padding-left: 2em; padding-inline-start: 2em; }
.printed-toc-level-3 { padding-left: 3em; padding-inline-start: 3em; }
"""
    if mode == "compact":
        return base.replace("margin: 5%;", "margin: 2%;").replace(
            "line-height: 1.5", "line-height: 1.35"
        )
    return base
