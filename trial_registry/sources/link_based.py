from __future__ import annotations

import json
import os
import re
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from ..http import fetch_html
from ..text import normalize_text
from ..types import LiteratureInput, NormalizedRow, QueryInput, SearchMatch, StudyRecord
from .base import RegistrySource
from .protocol import (
    build_source_protocol,
    split_protocol_and_results_sections,
    write_raw_evidence_files,
)


class LinkBasedRegistrySource(RegistrySource):
    registry_label: str
    protocol_filename: str
    protocol_file_key: str
    id_query_types: set[str] = set()
    detail_query_types: set[str] = {"detail_url"}
    search_url_query_types: set[str] = {"search_url"}
    link_only_note = "link_only_in_v1"

    def search(self, query: QueryInput) -> list[SearchMatch]:
        if query.query_type in self.id_query_types:
            return [self.match_from_id(query)]
        if query.query_type in self.detail_query_types:
            return [self.match_from_detail_url(query)]
        if query.query_type in self.search_url_query_types:
            return [self.match_from_search_url(query)]
        if query.query_type == "keyword_search_not_enabled":
            raise ValueError("Keyword search is not enabled in this ID-only version.")
        raise ValueError(f"{self.registry_label} does not support query type {query.query_type!r}.")

    def fetch_detail(self, match: SearchMatch) -> StudyRecord:
        if match.raw_summary.get("fetch_mode") == "html":
            html = self.fetch_html_for_match(match)
            return self.record_from_html(match, html)
        return self.record_from_link(match)

    def fetch_html_for_match(self, match: SearchMatch) -> str:
        return fetch_html(match.detail_url)

    def normalize(
        self,
        record: StudyRecord,
        *,
        run_id: str,
        query: QueryInput,
        match_count: int,
    ) -> NormalizedRow:
        protocol = build_generic_protocol(record)
        match = record.match
        row: NormalizedRow = OrderedDict()
        row["run_id"] = run_id
        row["source"] = record.source
        row["source_registry"] = self.registry_label
        row["query_value"] = query.raw_input
        row["query_type"] = query.query_type
        row["match_rank"] = str(match.match_rank if match else "")
        row["match_count"] = str(match_count)
        row["matched_by"] = match.matched_by if match else query.query_type
        row["detail_url"] = record.detail_url
        row["search_url"] = stringify_meta(record, "Search URL")
        row["registration_number"] = protocol["registration_number"]
        row["fetch_status"] = protocol["fetch_status"]
        row["fetch_note"] = protocol["fetch_note"]
        row["title"] = stringify_meta(record, "Title") or protocol["title"]
        row["page_text_preview"] = protocol["page_text_preview"]
        return row

    def write_sidecar_files(
        self,
        record: StudyRecord,
        *,
        output_dir: Path,
        literature: LiteratureInput | None = None,
    ) -> dict[str, Path]:
        protocol_path = output_dir / self.protocol_filename
        raw_files = write_raw_evidence_files(record, output_dir=output_dir, basename=self.raw_file_basename())
        protocol = build_generic_protocol(
            record,
            source_file=literature.literature_file if literature else "",
            raw_evidence_files=raw_files,
        )
        with protocol_path.open("w", encoding="utf-8") as handle:
            json.dump(protocol, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        files = {self.protocol_file_key: protocol_path}
        if "raw_html" in raw_files:
            files[f"{self.name}_raw_html"] = raw_files["raw_html"]
        if "raw_text" in raw_files:
            files[f"{self.name}_raw_text"] = raw_files["raw_text"]
        return files

    def match_from_id(self, query: QueryInput) -> SearchMatch:
        urls = self.urls_for_id(query.raw_input)
        detail_url = urls.get("detail") or urls.get("record") or urls.get("search") or ""
        fetch_mode = "html" if urls.get("detail") and self.can_fetch_detail_url(detail_url) else "link_only"
        fetch_note = "" if fetch_mode == "html" else self.link_only_note
        return SearchMatch(
            source=self.name,
            match_rank=1,
            match_key=query.raw_input,
            title="",
            detail_url=detail_url,
            raw_summary={
                "registration_number": query.raw_input,
                "registry": self.registry_label,
                "fetch_mode": fetch_mode,
                "fetch_status": "fetched" if fetch_mode == "html" else fetch_note,
                "fetch_note": fetch_note,
                **urls,
            },
            matched_by=query.query_type,
        )

    def match_from_detail_url(self, query: QueryInput) -> SearchMatch:
        record_id = self.extract_id_from_url(query.raw_input) or query.raw_input
        fetch_mode = "html" if self.can_fetch_detail_url(query.raw_input) else "link_only"
        fetch_note = "" if fetch_mode == "html" else self.link_only_note
        return SearchMatch(
            source=self.name,
            match_rank=1,
            match_key=record_id,
            title="",
            detail_url=query.raw_input,
            raw_summary={
                "registration_number": record_id,
                "registry": self.registry_label,
                "fetch_mode": fetch_mode,
                "fetch_status": "fetched" if fetch_mode == "html" else fetch_note,
                "fetch_note": fetch_note,
            },
            matched_by=query.query_type,
        )

    def match_from_search_url(self, query: QueryInput) -> SearchMatch:
        return SearchMatch(
            source=self.name,
            match_rank=1,
            match_key=query.raw_input,
            title="",
            detail_url=query.raw_input,
            raw_summary={
                "registration_number": query.raw_input,
                "registry": self.registry_label,
                "fetch_mode": "link_only",
                "fetch_status": "search_required",
                "fetch_note": "search_required",
                "search": query.raw_input,
            },
            matched_by=query.query_type,
        )

    def record_from_link(self, match: SearchMatch) -> StudyRecord:
        registration_number = match.raw_summary.get("registration_number") or match.match_key
        fetch_status = match.raw_summary.get("fetch_status") or "link_only"
        fetch_note = match.raw_summary.get("fetch_note") or self.link_only_note
        meta = OrderedDict(
            [
                ("Registration number", registration_number),
                ("Registry", self.registry_label),
                ("Detail URL", match.detail_url),
                ("Search URL", match.raw_summary.get("search", "")),
                ("Fetch status", fetch_status),
                ("Fetch note", fetch_note),
            ]
        )
        return StudyRecord(
            source=self.name,
            record_id=registration_number,
            detail_url=match.detail_url,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            meta=meta,
            sections=OrderedDict(),
            raw_data_optional=dict(match.raw_summary),
            fetch_status=fetch_status,
            fetch_note=fetch_note,
            match=match,
        )

    def record_from_html(self, match: SearchMatch, html: str) -> StudyRecord:
        text = html_to_text(html)
        title = html_title(html)
        registration_number = match.raw_summary.get("registration_number") or match.match_key
        sections = extract_structured_sections(html)
        meta = OrderedDict(
            [
                ("Registration number", registration_number),
                ("Registry", self.registry_label),
                ("Title", title),
                ("Detail URL", match.detail_url),
                ("Search URL", match.raw_summary.get("search", "")),
                ("Fetch status", "fetched"),
                ("Fetch note", ""),
            ]
        )
        if "page" not in sections:
            sections["page"] = OrderedDict([("title", title), ("text", text)])
        return StudyRecord(
            source=self.name,
            record_id=registration_number,
            detail_url=match.detail_url,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            meta=meta,
            sections=sections,
            raw_html_optional=html,
            raw_text_optional=text,
            raw_data_optional=dict(match.raw_summary),
            fetch_status="fetched",
            match=match,
        )

    def urls_for_id(self, registry_id: str) -> dict[str, str]:
        raise NotImplementedError

    def extract_id_from_url(self, url: str) -> str:
        return ""

    def can_fetch_detail_url(self, url: str) -> bool:
        return False

    def raw_file_basename(self) -> str:
        return self.protocol_filename.removesuffix("_protocol.json").removesuffix(".json")

    def unresolved_match(
        self,
        query: QueryInput,
        *,
        urls: dict[str, str] | None = None,
        fetch_status: str | None = None,
        fetch_note: str | None = None,
    ) -> SearchMatch:
        urls = urls or self.urls_for_id(query.raw_input)
        status = fetch_status or self.link_only_note
        note = fetch_note or status
        detail_url = urls.get("detail") or urls.get("record") or urls.get("search") or ""
        return SearchMatch(
            source=self.name,
            match_rank=1,
            match_key=query.raw_input,
            title="",
            detail_url=detail_url,
            raw_summary={
                "registration_number": query.raw_input,
                "registry": self.registry_label,
                "fetch_mode": "link_only",
                "fetch_status": status,
                "fetch_note": note,
                **urls,
            },
            matched_by=query.query_type,
        )

    def detail_match_from_url(
        self,
        *,
        query: QueryInput,
        detail_url: str,
        match_key: str | None = None,
        title: str = "",
        raw_summary: dict[str, str] | None = None,
        match_rank: int = 1,
    ) -> SearchMatch:
        summary = {
            "registration_number": match_key or query.raw_input,
            "registry": self.registry_label,
            "fetch_mode": "html",
            "fetch_status": "fetched",
            "fetch_note": "",
        }
        if raw_summary:
            summary.update(raw_summary)
        return SearchMatch(
            source=self.name,
            match_rank=match_rank,
            match_key=match_key or query.raw_input,
            title=title,
            detail_url=detail_url,
            raw_summary=summary,
            matched_by=query.query_type,
        )


def build_generic_protocol(
    record: StudyRecord,
    *,
    source_file: str = "",
    raw_evidence_files: dict[str, Path] | None = None,
) -> dict[str, Any]:
    fetch_status = stringify_meta(record, "Fetch status") or "unknown"
    page_text = ""
    page_section = record.sections.get("page")
    if page_section:
        page_text = str(page_section.get("text") or "")
    protocol_sections, results_sections = split_protocol_and_results_sections(record.sections)
    protocol = build_source_protocol(
        record,
        source_registry=stringify_meta(record, "Registry") or record.source,
        source_file=source_file,
        protocol_sections=protocol_sections,
        results_sections=results_sections,
        source_specific=OrderedDict(
            [
                ("meta", record.meta),
                ("urls", record.raw_data_optional or {}),
            ]
        ),
        raw_evidence_files=raw_evidence_files,
        extra={
            "search_url": stringify_meta(record, "Search URL"),
            "urls": record.raw_data_optional or {},
            "title": stringify_meta(record, "Title"),
            "meta": record.meta,
            "sections": record.sections,
            "page_text_preview": page_text[:2500],
        },
    )
    protocol["fetch_status"] = fetch_status
    protocol["fetch_note"] = stringify_meta(record, "Fetch note")
    return dict(protocol)


def live_search_enabled() -> bool:
    value = os.environ.get("TRIAL_REGISTRY_DISABLE_LIVE_SEARCH", "").strip().lower()
    return value not in {"1", "true", "yes", "on"}


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return normalize_text(soup.get_text("\n", strip=False))


def html_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return normalize_text(soup.title.string)
    heading = soup.find(["h1", "h2"])
    return normalize_text(heading.get_text(" ", strip=False)) if heading else ""


def extract_structured_sections(html: str) -> OrderedDict[str, OrderedDict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    table_sections = extract_table_sections(soup)
    for key, value in table_sections.items():
        sections[key] = value

    heading_sections = extract_heading_sections(soup)
    for key, value in heading_sections.items():
        if key not in sections:
            sections[key] = value

    text = normalize_text(soup.get_text("\n", strip=False))
    title = html_title(html)
    sections["page"] = OrderedDict([("title", title), ("text", text)])
    return sections


def extract_table_sections(soup: BeautifulSoup) -> OrderedDict[str, OrderedDict[str, Any]]:
    sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    for table_index, table in enumerate(soup.find_all("table"), start=1):
        fields: OrderedDict[str, Any] = OrderedDict()
        for row in table.find_all("tr"):
            cells = [
                normalize_text(cell.get_text(" ", strip=False))
                for cell in row.find_all(["th", "td"], recursive=False)
            ]
            cells = [cell for cell in cells if cell]
            if len(cells) == 2:
                fields[cells[0]] = cells[1]
            elif len(cells) > 2:
                fields[f"row_{len(fields) + 1}"] = cells
        if fields:
            caption = table.find("caption")
            if caption:
                section_name = normalize_text(caption.get_text(" ", strip=False))
            else:
                section_name = nearest_heading_text(table) or f"table_{table_index}"
            sections[section_name] = fields
    return sections


def extract_heading_sections(soup: BeautifulSoup) -> OrderedDict[str, OrderedDict[str, Any]]:
    sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    headings = soup.find_all(["h1", "h2", "h3"])
    for heading in headings:
        section_name = normalize_text(heading.get_text(" ", strip=False))
        if not section_name:
            continue
        pieces: list[str] = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) in {"h1", "h2", "h3"}:
                break
            if hasattr(sibling, "get_text"):
                text = normalize_text(sibling.get_text("\n", strip=False))
            else:
                text = normalize_text(str(sibling))
            if text:
                pieces.append(text)
        if pieces:
            sections[section_name] = OrderedDict([("text", "\n".join(pieces))])
    return sections


def nearest_heading_text(tag) -> str:
    for previous in tag.find_all_previous(["h1", "h2", "h3"], limit=1):
        text = normalize_text(previous.get_text(" ", strip=False))
        if text:
            return text
    return ""


def stringify_meta(record: StudyRecord, key: str) -> str:
    value = record.meta.get(key)
    if value is None:
        return ""
    return str(value)


def extract_first(pattern: str, value: str) -> str:
    match = re.search(pattern, value, flags=re.IGNORECASE)
    return match.group(1) if match else ""
