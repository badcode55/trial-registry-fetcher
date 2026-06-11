from __future__ import annotations

from pathlib import Path

from ..types import NormalizedRow, StudyRecord
from .base import Exporter


class TextExporter(Exporter):
    name = "txt"

    def export(
        self,
        *,
        output_dir: Path,
        rows: list[NormalizedRow],
        records: list[StudyRecord],
        run_id: str,
    ) -> Path:
        path = output_dir / f"{run_id}.txt"
        with path.open("w", encoding="utf-8") as handle:
            for index, row in enumerate(rows, start=1):
                handle.write(f"Record {index}\n")
                handle.write("=" * 8 + "\n")
                for key, value in row.items():
                    handle.write(f"{key}: {value}\n")
                handle.write("\n")
        return path
