from __future__ import annotations

from pathlib import Path

from ..types import NormalizedRow, StudyRecord
from .base import Exporter


class MarkdownExporter(Exporter):
    name = "md"

    def export(
        self,
        *,
        output_dir: Path,
        rows: list[NormalizedRow],
        records: list[StudyRecord],
        run_id: str,
    ) -> Path:
        path = output_dir / f"{run_id}.md"
        with path.open("w", encoding="utf-8") as handle:
            handle.write(f"# Trial Registry Results: {run_id}\n\n")
            for index, row in enumerate(rows, start=1):
                title = row.get("scientific_title") or row.get("title_brief") or f"Record {index}"
                handle.write(f"## {index}. {title}\n\n")
                for key, value in row.items():
                    handle.write(f"- `{key}`: {value}\n")
                handle.write("\n")
        return path
