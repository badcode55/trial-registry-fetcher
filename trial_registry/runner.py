from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .exporters import get_exporter
from .input_readers import get_input_reader
from .query import resolve_query
from .sources import get_source
from .types import BatchResult, ExportResult, LiteratureInput, NormalizedRow, StudyRecord


INDEX_FIELDNAMES = [
    "run_id",
    "created_at_utc",
    "literature_file",
    "registry_id",
    "registry_type",
    "status",
    "source",
    "query_value",
    "query_type",
    "match_count",
    "saved_count",
    "failure_count",
    "result_csv",
    "manifest_path",
    "formats",
    "message",
]


def run_query(
    query: str,
    source: str = "umin_ctr",
    formats: list[str] | None = None,
    output_root: str = "output",
    run_id: str | None = None,
    literature: LiteratureInput | None = None,
) -> ExportResult:
    formats = formats or ["csv"]
    run_id = run_id or make_run_id()
    query_input = resolve_query(query, source_hint=source)
    if query_input.query_type == "keyword_search_not_enabled":
        raise ValueError("Keyword search is not enabled in this ID-only version.")
    registry_source = get_source(source)
    output_root_path = Path(output_root).expanduser().resolve()
    output_dir = output_root_path / run_id
    output_dir.mkdir(parents=True, exist_ok=False)

    matches = registry_source.search(query_input)
    records: list[StudyRecord] = []
    rows: list[NormalizedRow] = []
    failures: list[dict[str, str]] = []

    for match in matches:
        try:
            record = registry_source.fetch_detail(match)
            records.append(record)
            rows.append(
                registry_source.normalize(
                    record,
                    run_id=run_id,
                    query=query_input,
                    match_count=len(matches),
                )
            )
        except Exception as exc:  # pragma: no cover - captured in manifest for batch runs
            failures.append(
                {
                    "match_key": match.match_key,
                    "detail_url": match.detail_url,
                    "error": str(exc),
                }
            )

    files: dict[str, Path] = {}
    for output_format in formats:
        exporter = get_exporter(output_format)
        files[exporter.name] = exporter.export(
            output_dir=output_dir,
            rows=rows,
            records=records,
            run_id=run_id,
        )

    created_at_utc = datetime.now(timezone.utc).isoformat()
    manifest_path = output_dir / "manifest.json"
    index_path = output_root_path / "index.csv"
    result_csv = files.get("csv")
    manifest = {
        "run_id": run_id,
        "query": asdict(query_input),
        "source": source,
        "formats": formats,
        "match_count": len(matches),
        "saved_count": len(records),
        "failure_count": len(failures),
        "failures": failures,
        "files": {key: str(path) for key, path in files.items()},
        "index_path": str(index_path),
        "created_at_utc": created_at_utc,
    }
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    append_index_row(
        index_path=index_path,
        row={
            "run_id": run_id,
            "created_at_utc": created_at_utc,
            "literature_file": literature.literature_file if literature else "",
            "registry_id": literature.registry_id if literature else query_input.raw_input,
            "registry_type": literature.registry_type if literature else infer_registry_type(query_input.raw_input),
            "status": "saved" if records and not failures else ("failed" if failures else "no_match"),
            "source": source,
            "query_value": query_input.raw_input,
            "query_type": query_input.query_type,
            "match_count": str(len(matches)),
            "saved_count": str(len(records)),
            "failure_count": str(len(failures)),
            "result_csv": str(result_csv) if result_csv else "",
            "manifest_path": str(manifest_path),
            "formats": ",".join(formats),
            "message": literature.message if literature else "",
        },
    )

    return ExportResult(
        run_id=run_id,
        output_dir=output_dir,
        files=files,
        manifest_path=manifest_path,
        match_count=len(matches),
        failure_count=len(failures),
    )


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_batch(
    input_path: str,
    input_format: str = "txt",
    formats: list[str] | None = None,
    output_root: str = "output",
) -> BatchResult:
    formats = formats or ["csv"]
    output_root_path = Path(output_root).expanduser().resolve()
    output_root_path.mkdir(parents=True, exist_ok=True)
    reader = get_input_reader(input_format)
    items = reader.read(Path(input_path).expanduser())

    results: list[ExportResult] = []
    pending_count = 0
    failure_count = 0
    saved_count = 0
    index_path = output_root_path / "index.csv"

    for item in items:
        if item.status == "ready" and item.source_hint == "umin_ctr":
            run_id = make_literature_run_id(item)
            try:
                result = run_query(
                    item.registry_id,
                    source=item.source_hint,
                    formats=formats,
                    output_root=str(output_root_path),
                    run_id=run_id,
                    literature=item,
                )
                results.append(result)
                saved_count += 1 if result.failure_count == 0 else 0
                failure_count += result.failure_count
            except Exception as exc:
                failure_count += 1
                append_pending_index_row(
                    index_path=index_path,
                    item=item,
                    output_root=output_root_path,
                    formats=formats,
                    status="failed",
                    message=str(exc),
                )
            continue

        pending_count += 1
        append_pending_index_row(
            index_path=index_path,
            item=item,
            output_root=output_root_path,
            formats=formats,
            status=item.status,
            message=item.message,
        )

    return BatchResult(
        output_root=output_root_path,
        index_path=index_path,
        results=results,
        total_count=len(items),
        saved_count=saved_count,
        pending_count=pending_count,
        failure_count=failure_count,
    )


def append_index_row(*, index_path: Path, row: dict[str, str]) -> None:
    index_exists = index_path.exists()
    with index_path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_FIELDNAMES)
        if not index_exists:
            writer.writeheader()
        writer.writerow(row)


def append_pending_index_row(
    *,
    index_path: Path,
    item: LiteratureInput,
    output_root: Path,
    formats: list[str],
    status: str,
    message: str,
) -> None:
    created_at_utc = datetime.now(timezone.utc).isoformat()
    append_index_row(
        index_path=index_path,
        row={
            "run_id": "",
            "created_at_utc": created_at_utc,
            "literature_file": item.literature_file,
            "registry_id": item.registry_id,
            "registry_type": item.registry_type,
            "status": status,
            "source": item.source_hint,
            "query_value": item.registry_id,
            "query_type": "",
            "match_count": "0",
            "saved_count": "0",
            "failure_count": "0" if status not in {"failed", "invalid_input"} else "1",
            "result_csv": "",
            "manifest_path": "",
            "formats": ",".join(formats),
            "message": message,
        },
    )


def make_literature_run_id(item: LiteratureInput) -> str:
    stem = Path(item.literature_file).stem
    safe_stem = "".join(char if char.isalnum() else "_" for char in stem).strip("_").lower()
    safe_id = "".join(char if char.isalnum() else "_" for char in item.registry_id).strip("_").lower()
    return f"{safe_stem}_{safe_id}" or make_run_id()


def infer_registry_type(value: str) -> str:
    upper = value.upper()
    if upper.startswith("UMIN"):
        return "umin"
    if upper.startswith("NCT"):
        return "nct"
    return ""
