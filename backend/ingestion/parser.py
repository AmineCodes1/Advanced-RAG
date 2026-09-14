from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docling.document_converter import DocumentConverter


@dataclass(frozen=True)
class ParsedPage:
    text: str
    page: int | None = None
    section: str | None = None


class PdfParser:
    """Convert PDFs to structured markdown using Docling."""

    def __init__(self, converter: DocumentConverter | None = None) -> None:
        self.converter = converter or DocumentConverter()

    def parse(self, filepath: str | Path) -> list[ParsedPage]:
        path = Path(filepath)
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a PDF file, received: {path.name}")
        if not path.is_file():
            raise FileNotFoundError(path)

        conversion = self.converter.convert(str(path))
        document = conversion.document
        markdown = document.export_to_markdown().strip()
        if not markdown:
            return []

        # Docling's exported markdown preserves tables and headings. Page-level
        # objects differ between Docling releases, so retain a document-level
        # record when a stable page export is unavailable.
        return [ParsedPage(text=markdown, page=None)]


def parse_pdf(filepath: str | Path) -> list[ParsedPage]:
    return PdfParser().parse(filepath)
