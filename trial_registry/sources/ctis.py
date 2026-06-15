from __future__ import annotations

import json
import re
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ..http import fetch_html, post_json
from ..text import normalize_text
from ..types import LiteratureInput, NormalizedRow, QueryInput, SearchMatch, StudyRecord
from .link_based import LinkBasedRegistrySource, live_search_enabled
from .protocol import build_source_protocol, write_raw_evidence_files


CTIS_SEARCH_API_URL = "https://euclinicaltrials.eu/ctis-public-api/search"
CTIS_RECORD_URL = "https://euclinicaltrials.eu/ctis-public/view/{ct_number}?lang=en"
CTIS_STATUS_LABELS = {
    1: "Draft",
    2: "Authorised",
    3: "Rejected",
    4: "Withdrawn",
    5: "Submitted",
    6: "Not authorised",
    7: "Restarted",
    8: "Suspended",
    9: "Ended",
    10: "Temporarily halted",
    11: "Transitioned",
}


class CtisSource(LinkBasedRegistrySource):
    name = "ctis"
    registry_label = "Clinical Trials Information System"
    protocol_filename = "CTIS_protocol.json"
    protocol_file_key = "ctis_protocol"
    id_query_types = {"ctis_id"}
    link_only_note = "search_required"

    def search(self, query: QueryInput) -> list[SearchMatch]:
        if query.query_type in self.id_query_types or query.query_type in self.search_url_query_types:
            registry_id = self.extract_id_from_url(query.raw_input) or query.raw_input.upper()
            urls = self.urls_for_id(registry_id) if registry_id else {"search": query.raw_input}
            if live_search_enabled():
                try:
                    api_response = fetch_ctis_search_response(registry_id)
                    matches = parse_ctis_search_response(
                        api_response,
                        query=query,
                        source=self,
                        registry_id=registry_id,
                    )
                    if matches:
                        return matches
                    pagination = api_response.get("pagination") if isinstance(api_response, dict) else {}
                    total_records = str(pagination.get("totalRecords", "")) if isinstance(pagination, dict) else ""
                    return [
                        self.unresolved_match(
                            query,
                            urls=urls,
                            fetch_status="not_found",
                            fetch_note=f"ctis_api_no_exact_match totalRecords={total_records}".strip(),
                        )
                    ]
                except Exception:
                    try:
                        html = fetch_html(urls["search"])
                        if ctis_page_has_trial_content(html, registry_id):
                            return [
                                self.detail_match_from_url(
                                    query=query,
                                    detail_url=urls["search"],
                                    match_key=registry_id,
                                    raw_summary={"search": urls["search"]},
                                )
                            ]
                    except Exception:
                        pass
                    return [self.unresolved_match(query, urls=urls, fetch_status="search_required")]
            return [self.unresolved_match(query, urls=urls, fetch_status="search_required")]
        return super().search(query)

    def fetch_detail(self, match: SearchMatch) -> StudyRecord:
        if match.raw_summary.get("fetch_mode") == "ctis_api":
            raw = json.loads(match.raw_summary["api_response_json"])
            item = json.loads(match.raw_summary["ctis_search_result_json"])
            return record_from_ctis_search_result(
                item,
                raw_response=raw,
                detail_url=match.detail_url,
                match=match,
            )
        return super().fetch_detail(match)

    def normalize(
        self,
        record: StudyRecord,
        *,
        run_id: str,
        query: QueryInput,
        match_count: int,
    ) -> NormalizedRow:
        row = super().normalize(record, run_id=run_id, query=query, match_count=match_count)
        raw = record.raw_data_optional or {}
        item = raw.get("search_result") if isinstance(raw.get("search_result"), dict) else {}
        row["ct_number"] = str(item.get("ctNumber") or record.record_id)
        row["ct_status"] = ctis_status_label(item.get("ctStatus"))
        row["ct_title"] = str(item.get("ctTitle") or "")
        row["short_title"] = str(item.get("shortTitle") or "")
        row["conditions"] = str(item.get("conditions") or "")
        row["sponsor"] = str(item.get("sponsor") or "")
        row["trial_phase"] = str(item.get("trialPhase") or "")
        row["trial_countries"] = json.dumps(item.get("trialCountries") or [], ensure_ascii=False)
        row["results_first_received"] = str(item.get("resultsFirstReceived") or "")
        row["last_updated"] = str(item.get("lastUpdated") or "")
        return row

    def record_from_html(self, match: SearchMatch, html: str) -> StudyRecord:
        if not ctis_page_has_trial_content(html, match.match_key):
            unresolved = self.record_from_link(
                self.unresolved_match(
                    QueryInput(match.match_key, "ctis_id", self.name),
                    urls={"search": match.detail_url},
                    fetch_status="search_required",
                    fetch_note="ctis_frontend_shell_or_no_visible_trial_content",
                )
            )
            unresolved.raw_html_optional = html
            unresolved.raw_text_optional = normalize_text(html)
            return unresolved
        return super().record_from_html(match, html)

    def urls_for_id(self, registry_id: str) -> dict[str, str]:
        encoded = quote(registry_id)
        return {
            "search": f"https://euclinicaltrials.eu/search-for-clinical-trials/?lang=en&EUCT={encoded}",
            "view_candidate": CTIS_RECORD_URL.format(ct_number=encoded),
            "api_search": CTIS_SEARCH_API_URL,
        }

    def extract_id_from_url(self, url: str) -> str:
        match = re.search(r"(\d{4}-\d{6}-\d{2}-\d{2})", url)
        return match.group(1).upper() if match else ""

    def can_fetch_detail_url(self, url: str) -> bool:
        return False

    def write_sidecar_files(
        self,
        record: StudyRecord,
        *,
        output_dir: Path,
        literature: LiteratureInput | None = None,
    ) -> dict[str, Path]:
        protocol_path = output_dir / self.protocol_filename
        raw_payload = record.raw_data_optional or {}
        raw_files = write_raw_evidence_files(
            record,
            output_dir=output_dir,
            basename=self.raw_file_basename(),
            json_payload=raw_payload,
        )
        protocol = build_ctis_protocol(
            record,
            source_file=literature.literature_file if literature else "",
            raw_evidence_files=raw_files,
        )
        with protocol_path.open("w", encoding="utf-8") as handle:
            json.dump(protocol, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        files = {self.protocol_file_key: protocol_path}
        if "raw_json" in raw_files:
            files["ctis_raw"] = raw_files["raw_json"]
        if "raw_html" in raw_files:
            files["ctis_raw_html"] = raw_files["raw_html"]
        if "raw_text" in raw_files:
            files["ctis_raw_text"] = raw_files["raw_text"]
        return files


def fetch_ctis_search_response(registry_id: str) -> dict[str, Any]:
    payload = {
        "pagination": {"page": 1, "size": 20},
        "sort": {"property": "ctNumber", "direction": "ASC"},
        "searchCriteria": {"number": registry_id},
    }
    headers = {
        "Origin": "https://euclinicaltrials.eu",
        "Referer": CTIS_RECORD_URL.format(ct_number=quote(registry_id)),
    }
    response = post_json(CTIS_SEARCH_API_URL, payload, headers=headers)
    if not isinstance(response, dict):
        raise ValueError("CTIS search API did not return a JSON object.")
    return response


def parse_ctis_search_response(
    raw: dict[str, Any],
    *,
    query: QueryInput,
    source: CtisSource,
    registry_id: str | None = None,
) -> list[SearchMatch]:
    registry_id = (registry_id or query.raw_input).upper()
    data = raw.get("data")
    if not isinstance(data, list):
        return []
    exact_items = [item for item in data if isinstance(item, dict) and str(item.get("ctNumber", "")).upper() == registry_id]
    if len(exact_items) != 1:
        return []
    item = exact_items[0]
    detail_url = CTIS_RECORD_URL.format(ct_number=quote(registry_id))
    raw_summary = {
        "registration_number": registry_id,
        "registry": source.registry_label,
        "fetch_mode": "ctis_api",
        "fetch_status": "fetched",
        "fetch_note": "",
        "search": source.urls_for_id(registry_id)["search"],
        "detail": detail_url,
        "api_search": CTIS_SEARCH_API_URL,
        "api_response_json": json.dumps(raw, ensure_ascii=False),
        "ctis_search_result_json": json.dumps(item, ensure_ascii=False),
    }
    return [
        SearchMatch(
            source=source.name,
            match_rank=1,
            match_key=registry_id,
            title=str(item.get("ctTitle") or ""),
            detail_url=detail_url,
            raw_summary=raw_summary,
            matched_by=query.query_type,
        )
    ]


def record_from_ctis_search_result(
    item: dict[str, Any],
    *,
    raw_response: dict[str, Any],
    detail_url: str,
    match: SearchMatch | None = None,
) -> StudyRecord:
    ct_number = str(item.get("ctNumber") or (match.match_key if match else ""))
    meta: OrderedDict[str, Any] = OrderedDict(
        [
            ("Registration number", ct_number),
            ("Registry", "Clinical Trials Information System"),
            ("Title", item.get("ctTitle") or ""),
            ("Detail URL", detail_url),
            ("Search URL", CtisSource().urls_for_id(ct_number)["search"] if ct_number else ""),
            ("Fetch status", "fetched"),
            ("Fetch note", ""),
        ]
    )
    sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict(
        [
            (
                "search_result_summary",
                OrderedDict(
                    [
                        ("ctNumber", item.get("ctNumber")),
                        ("ctStatus", ctis_status_label(item.get("ctStatus"))),
                        ("ctStatusCode", item.get("ctStatus")),
                        ("ctTitle", item.get("ctTitle")),
                        ("shortTitle", item.get("shortTitle")),
                        ("conditions", item.get("conditions")),
                        ("trialCountries", item.get("trialCountries")),
                        ("decisionDateOverall", item.get("decisionDateOverall")),
                        ("decisionDate", item.get("decisionDate")),
                        ("lastUpdated", item.get("lastUpdated")),
                    ]
                ),
            ),
            (
                "sponsor_and_design",
                OrderedDict(
                    [
                        ("sponsor", item.get("sponsor")),
                        ("sponsorType", item.get("sponsorType")),
                        ("trialPhase", item.get("trialPhase")),
                        ("product", item.get("product")),
                        ("ageRangeSecondary", item.get("ageRangeSecondary")),
                        ("ageGroup", item.get("ageGroup")),
                        ("gender", item.get("gender")),
                        ("trialRegion", item.get("trialRegion")),
                        ("totalNumberEnrolled", item.get("totalNumberEnrolled")),
                    ]
                ),
            ),
            (
                "conditions_and_therapeutic_areas",
                OrderedDict(
                    [
                        ("conditions", item.get("conditions")),
                        ("therapeuticAreas", item.get("therapeuticAreas")),
                    ]
                ),
            ),
            (
                "outcomes_and_results",
                OrderedDict(
                    [
                        ("primaryEndPoint", item.get("primaryEndPoint")),
                        ("endPoint", item.get("endPoint")),
                        ("resultsFirstReceived", item.get("resultsFirstReceived")),
                        ("lastPublicationUpdate", item.get("lastPublicationUpdate")),
                    ]
                ),
            ),
        ]
    )
    raw = {
        "api_url": CTIS_SEARCH_API_URL,
        "api_payload": {
            "pagination": {"page": 1, "size": 20},
            "sort": {"property": "ctNumber", "direction": "ASC"},
            "searchCriteria": {"number": ct_number},
        },
        "search_result": item,
        "api_response": raw_response,
    }
    return StudyRecord(
        source=CtisSource.name,
        record_id=ct_number,
        detail_url=detail_url,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        meta=meta,
        sections=sections,
        raw_data_optional=raw,
        fetch_status="fetched",
        match=match,
    )


def build_ctis_protocol(
    record: StudyRecord,
    *,
    source_file: str = "",
    raw_evidence_files: dict[str, Path] | None = None,
) -> OrderedDict[str, Any]:
    raw = record.raw_data_optional or {}
    item = raw.get("search_result") if isinstance(raw.get("search_result"), dict) else {}
    protocol_sections = OrderedDict(
        (name, fields)
        for name, fields in record.sections.items()
        if name != "outcomes_and_results"
    )
    results_sections = OrderedDict()
    if "outcomes_and_results" in record.sections:
        results_sections["outcomes_and_results"] = record.sections["outcomes_and_results"]
    return build_source_protocol(
        record,
        source_registry="Clinical Trials Information System",
        source_file=source_file,
        protocol_sections=protocol_sections,
        results_sections=results_sections,
        source_specific=OrderedDict(
            [
                ("api_url", raw.get("api_url", CTIS_SEARCH_API_URL)),
                ("api_payload", raw.get("api_payload", {})),
                ("search_result", item),
                ("pagination", raw.get("api_response", {}).get("pagination", {})),
            ]
        ),
        raw_evidence_files=raw_evidence_files,
        extra={
            "search_url": record.meta.get("Search URL", ""),
            "title": item.get("ctTitle", ""),
            "ct_status": ctis_status_label(item.get("ctStatus")),
            "meta": record.meta,
        },
    )


def ctis_status_label(value: Any) -> str:
    try:
        return CTIS_STATUS_LABELS.get(int(value), str(value) if value is not None else "")
    except (TypeError, ValueError):
        return str(value) if value is not None else ""


def ctis_page_has_trial_content(html: str, registry_id: str) -> bool:
    text = normalize_text(html)
    lowered = text.lower()
    if registry_id not in text:
        return False
    evidence_terms = [
        "trial title",
        "sponsor",
        "medical condition",
        "therapeutic area",
        "trial status",
    ]
    return any(term in lowered for term in evidence_terms)
