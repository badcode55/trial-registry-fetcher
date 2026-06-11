from __future__ import annotations

from .base import Exporter
from .csv_exporter import CSVExporter
from .json_exporter import JSONExporter
from .markdown_exporter import MarkdownExporter
from .text_exporter import TextExporter


EXPORTER_REGISTRY: dict[str, type[Exporter]] = {
    CSVExporter.name: CSVExporter,
    JSONExporter.name: JSONExporter,
    MarkdownExporter.name: MarkdownExporter,
    TextExporter.name: TextExporter,
}


def get_exporter(name: str) -> Exporter:
    normalized = name.strip().lower()
    try:
        exporter_class = EXPORTER_REGISTRY[normalized]
    except KeyError as exc:
        choices = ", ".join(sorted(EXPORTER_REGISTRY))
        raise ValueError(f"Unknown format {name!r}. Available formats: {choices}") from exc
    return exporter_class()
