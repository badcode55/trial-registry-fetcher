from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..types import LiteratureInput, NormalizedRow, QueryInput, SearchMatch, StudyRecord


class RegistrySource(ABC):
    name: str

    @abstractmethod
    def search(self, query: QueryInput) -> list[SearchMatch]:
        raise NotImplementedError

    @abstractmethod
    def fetch_detail(self, match: SearchMatch) -> StudyRecord:
        raise NotImplementedError

    @abstractmethod
    def normalize(
        self,
        record: StudyRecord,
        *,
        run_id: str,
        query: QueryInput,
        match_count: int,
    ) -> NormalizedRow:
        raise NotImplementedError

    def write_sidecar_files(
        self,
        record: StudyRecord,
        *,
        output_dir: Path,
        literature: LiteratureInput | None = None,
    ) -> dict[str, Path]:
        # 新增注册库时，可在适配器中实现来源专属 protocol JSON；runner 无需增加来源判断。
        # New registries can emit source-specific protocol JSON here without source checks in the runner.
        return {}
