from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..types import NormalizedRow, StudyRecord


class Exporter(ABC):
    name: str

    @abstractmethod
    def export(
        self,
        *,
        output_dir: Path,
        rows: list[NormalizedRow],
        records: list[StudyRecord],
        run_id: str,
    ) -> Path:
        raise NotImplementedError
