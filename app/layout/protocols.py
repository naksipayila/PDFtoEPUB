"""Extension point for future AI-enhanced layout analyzers."""

from __future__ import annotations

from typing import Protocol

from app.core.config import ConversionOptions
from app.core.models import ConversionReport, ParsedPage, SemanticDocument


class LayoutAnalyzer(Protocol):
    def analyze(
        self,
        pages: list[ParsedPage],
        options: ConversionOptions,
        report: ConversionReport,
    ) -> SemanticDocument:
        """Convert raw source pages to a semantic document."""
