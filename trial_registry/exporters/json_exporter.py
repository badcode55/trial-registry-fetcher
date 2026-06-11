from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ..types import NormalizedRow, StudyRecord
from .base import Exporter


class JSONExporter(Exporter):
    name = "json"

    def export(
        self,
        *,
        output_dir: Path,
        rows: list[NormalizedRow],
        records: list[StudyRecord],
        run_id: str,
    ) -> Path:
        path = output_dir / f"{run_id}.json"
        payload = {
            "run_id": run_id,
            "rows": rows,
            "records": [record_to_dict(record) for record in records],
        }
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return path


def record_to_dict(record: StudyRecord) -> dict:
    data = asdict(record)
    data.pop("raw_html_optional", None)
    return data
