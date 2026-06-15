from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QueryInput:
    raw_input: str
    query_type: str
    source_hint: str = "umin_ctr"


@dataclass(frozen=True)
class LiteratureInput:
    literature_file: str
    registry_id: str
    registry_type: str
    status: str
    raw_line: str
    source_hint: str = ""
    message: str = ""


@dataclass(frozen=True)
class SearchMatch:
    source: str
    match_rank: int
    match_key: str
    title: str
    detail_url: str
    raw_summary: dict[str, str] = field(default_factory=dict)
    matched_by: str = ""


@dataclass
class StudyRecord:
    source: str
    record_id: str
    detail_url: str
    fetched_at: str
    meta: OrderedDict[str, Any]
    sections: OrderedDict[str, OrderedDict[str, Any]]
    raw_html_optional: str | None = None
    raw_data_optional: dict[str, Any] | None = None
    raw_text_optional: str | None = None
    fetch_status: str = "fetched"
    fetch_note: str = ""
    match: SearchMatch | None = None


NormalizedRow = OrderedDict[str, str]


@dataclass
class ExportResult:
    run_id: str
    output_dir: Path
    files: dict[str, Path]
    manifest_path: Path
    match_count: int
    failure_count: int
    status: str = ""


@dataclass
class BatchResult:
    output_root: Path
    index_path: Path
    results: list[ExportResult]
    total_count: int
    saved_count: int
    pending_count: int
    failure_count: int
