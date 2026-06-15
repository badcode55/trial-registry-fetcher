from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from ..types import StudyRecord


RESULT_KEYWORDS = (
    "result",
    "results",
    "outcome",
    "outcomes",
    "adverse",
    "publication",
    "publications",
    "participant flow",
    "baseline",
)


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_text(path: Path, payload: str) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        if payload and not payload.endswith("\n"):
            handle.write("\n")


def write_raw_evidence_files(
    record: StudyRecord,
    *,
    output_dir: Path,
    basename: str,
    json_payload: Any | None = None,
) -> dict[str, Path]:
    files: dict[str, Path] = {}

    if json_payload is not None:
        raw_json_path = output_dir / f"{basename}_raw.json"
        write_json(raw_json_path, json_payload)
        files["raw_json"] = raw_json_path

    if record.raw_html_optional:
        raw_html_path = output_dir / f"{basename}_raw.html"
        write_text(raw_html_path, record.raw_html_optional)
        files["raw_html"] = raw_html_path

    if record.raw_text_optional:
        raw_text_path = output_dir / f"{basename}_raw.txt"
        write_text(raw_text_path, record.raw_text_optional)
        files["raw_text"] = raw_text_path

    return files


def evidence_file_map(files: dict[str, Path]) -> OrderedDict[str, str]:
    return OrderedDict((key, str(path)) for key, path in sorted(files.items()))


def split_protocol_and_results_sections(
    sections: OrderedDict[str, OrderedDict[str, Any]],
) -> tuple[OrderedDict[str, OrderedDict[str, Any]], OrderedDict[str, OrderedDict[str, Any]]]:
    protocol_sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    results_sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()

    for section_name, fields in sections.items():
        target = results_sections if is_results_section(section_name) else protocol_sections
        target[section_name] = fields

    return protocol_sections, results_sections


def is_results_section(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in RESULT_KEYWORDS)


def build_source_protocol(
    record: StudyRecord,
    *,
    source_registry: str,
    source_file: str = "",
    protocol_sections: Any | None = None,
    results_sections: Any | None = None,
    source_specific: Any | None = None,
    raw_evidence_files: dict[str, Path] | None = None,
    extra: dict[str, Any] | None = None,
) -> OrderedDict[str, Any]:
    raw_evidence_files = raw_evidence_files or {}
    protocol = OrderedDict(
        [
            ("source_registry", source_registry),
            ("registration_number", record.record_id),
            ("source_file", source_file),
            ("detail_url", record.detail_url),
            ("fetched_at", record.fetched_at),
            ("fetch_status", record.fetch_status),
            ("fetch_note", record.fetch_note),
            ("protocol_sections", protocol_sections if protocol_sections is not None else record.sections),
            ("results_sections", results_sections if results_sections is not None else OrderedDict()),
            ("source_specific", source_specific if source_specific is not None else OrderedDict()),
            ("raw_evidence_files", evidence_file_map(raw_evidence_files)),
        ]
    )
    if extra:
        for key, value in extra.items():
            protocol[key] = value
    return protocol

