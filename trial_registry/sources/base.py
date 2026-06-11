from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import NormalizedRow, QueryInput, SearchMatch, StudyRecord


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
