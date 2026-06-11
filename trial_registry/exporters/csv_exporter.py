from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path

from ..types import NormalizedRow, StudyRecord
from .base import Exporter


class CSVExporter(Exporter):
    name = "csv"

    def export(
        self,
        *,
        output_dir: Path,
        rows: list[NormalizedRow],
        records: list[StudyRecord],
        run_id: str,
    ) -> Path:
        path = output_dir / f"{run_id}.csv"
        fieldnames = collect_fieldnames(rows)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return path


def collect_fieldnames(rows: list[NormalizedRow]) -> list[str]:
    fieldnames: OrderedDict[str, None] = OrderedDict()
    for row in rows:
        for key in row.keys():
            fieldnames.setdefault(key, None)
    return list(fieldnames.keys())
