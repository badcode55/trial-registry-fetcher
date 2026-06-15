from __future__ import annotations

import json
import re
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..http import fetch_json
from ..text import stringify
from ..types import LiteratureInput, NormalizedRow, QueryInput, SearchMatch, StudyRecord
from .base import RegistrySource
from .protocol import build_source_protocol, write_raw_evidence_files


RECORD_URL = "https://clinicaltrials.gov/study/{nct_id}"
API_URL = "https://clinicaltrials.gov/api/v2/studies/{nct_id}"
NCT_ID_RE = re.compile(r"^NCT\d+$", re.IGNORECASE)


class ClinicalTrialsGovSource(RegistrySource):
    name = "clinicaltrials_gov"

    def search(self, query: QueryInput) -> list[SearchMatch]:
        if query.query_type != "nct_id" or not NCT_ID_RE.fullmatch(query.raw_input):
            raise ValueError("ClinicalTrials.gov source expects an NCT ID.")

        nct_id = query.raw_input.upper()
        return [
            SearchMatch(
                source=self.name,
                match_rank=1,
                match_key=nct_id,
                title="",
                detail_url=RECORD_URL.format(nct_id=nct_id),
                matched_by="nct_id",
            )
        ]

    def fetch_detail(self, match: SearchMatch) -> StudyRecord:
        raw = fetch_json(API_URL.format(nct_id=match.match_key))
        return parse_nct_record(raw, detail_url=match.detail_url, match=match)

    def normalize(
        self,
        record: StudyRecord,
        *,
        run_id: str,
        query: QueryInput,
        match_count: int,
    ) -> NormalizedRow:
        protocol = build_nct_protocol(record)
        row: NormalizedRow = OrderedDict()
        row["run_id"] = run_id
        row["source"] = record.source
        row["query_value"] = query.raw_input
        row["query_type"] = query.query_type
        row["match_rank"] = str(record.match.match_rank if record.match else "")
        row["match_count"] = str(match_count)
        row["matched_by"] = record.match.matched_by if record.match else query.query_type
        row["detail_url"] = record.detail_url
        row["nct_id"] = protocol["identification"]["nct_id"] or record.record_id
        row["brief_title"] = protocol["identification"]["brief_title"]
        row["official_title"] = protocol["identification"]["official_title"]
        row["organization"] = protocol["identification"]["organization"]
        row["lead_sponsor"] = protocol["identification"]["lead_sponsor"]
        row["overall_status"] = protocol["status"]["overall_status"]
        row["start_date"] = protocol["status"]["start_date"]
        row["primary_completion_date"] = protocol["status"]["primary_completion_date"]
        row["completion_date"] = protocol["status"]["completion_date"]
        row["first_submit_date"] = protocol["status"]["first_submit_date"]
        row["first_post_date"] = protocol["status"]["first_post_date"]
        row["last_update_submit_date"] = protocol["status"]["last_update_submit_date"]
        row["last_update_post_date"] = protocol["status"]["last_update_post_date"]
        row["study_type"] = protocol["design"]["study_type"]
        row["phases"] = json_cell(protocol["design"]["phases"])
        row["allocation"] = protocol["design"]["allocation"]
        row["intervention_model"] = protocol["design"]["intervention_model"]
        row["primary_purpose"] = protocol["design"]["primary_purpose"]
        row["masking"] = protocol["design"]["masking"]
        row["who_masked"] = json_cell(protocol["design"]["who_masked"])
        row["enrollment"] = json_cell(protocol["design"]["enrollment"])
        row["conditions"] = json_cell(protocol["conditions"])
        row["brief_summary"] = protocol["brief_summary"]
        row["detailed_description"] = protocol["detailed_description"]
        row["arms"] = json_cell(protocol["arms"])
        row["interventions"] = json_cell(protocol["interventions"])
        row["primary_outcomes"] = json_cell(protocol["outcomes"]["primary"])
        row["secondary_outcomes"] = json_cell(protocol["outcomes"]["secondary"])
        row["other_outcomes"] = json_cell(protocol["outcomes"]["other"])
        row["eligibility_criteria"] = protocol["eligibility"]["criteria"]
        row["sex"] = protocol["eligibility"]["sex"]
        row["minimum_age"] = protocol["eligibility"]["minimum_age"]
        row["maximum_age"] = protocol["eligibility"]["maximum_age"]
        row["healthy_volunteers"] = stringify(protocol["eligibility"]["healthy_volunteers"])
        row["oversight"] = json_cell(protocol["oversight"])
        row["contacts_locations"] = json_cell(protocol["contacts_locations"])
        return row

    def write_sidecar_files(
        self,
        record: StudyRecord,
        *,
        output_dir: Path,
        literature: LiteratureInput | None = None,
    ) -> dict[str, Path]:
        protocol_path = output_dir / "NCT_protocol.json"
        raw = record.raw_data_optional or {}
        raw_files = write_raw_evidence_files(record, output_dir=output_dir, basename="NCT", json_payload=raw)
        protocol = build_nct_protocol(
            record,
            source_file=literature.literature_file if literature else "",
            raw_evidence_files=raw_files,
        )
        write_json(protocol_path, protocol)
        files = {"nct_protocol": protocol_path}
        if "raw_json" in raw_files:
            files["nct_raw"] = raw_files["raw_json"]
        return files


def parse_nct_record(
    raw: dict[str, Any],
    *,
    detail_url: str,
    match: SearchMatch | None = None,
) -> StudyRecord:
    protocol_section = raw.get("protocolSection")
    if not isinstance(protocol_section, dict):
        raise ValueError("ClinicalTrials.gov response does not contain protocolSection.")

    identification = protocol_section.get("identificationModule", {})
    nct_id = identification.get("nctId") or (match.match_key if match else "")
    if not nct_id:
        raise ValueError("ClinicalTrials.gov response does not contain an NCT ID.")

    meta: OrderedDict[str, Any] = OrderedDict(
        [
            ("NCT ID", nct_id),
            ("Brief title", identification.get("briefTitle")),
            ("Official title", identification.get("officialTitle")),
            ("Has results", raw.get("hasResults")),
        ]
    )
    sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    for key, value in protocol_section.items():
        sections[key] = OrderedDict(value) if isinstance(value, dict) else OrderedDict([("value", value)])

    return StudyRecord(
        source=ClinicalTrialsGovSource.name,
        record_id=nct_id,
        detail_url=detail_url,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        meta=meta,
        sections=sections,
        raw_data_optional=raw,
        fetch_status="fetched",
        match=match,
    )


def build_nct_protocol(
    record: StudyRecord,
    *,
    source_file: str = "",
    raw_evidence_files: dict[str, Path] | None = None,
) -> dict[str, Any]:
    raw = record.raw_data_optional or {}
    ps = raw.get("protocolSection", {})
    results_section = raw.get("resultsSection") or {}
    idm = ps.get("identificationModule", {})
    status = ps.get("statusModule", {})
    design = ps.get("designModule", {})
    arms = ps.get("armsInterventionsModule", {})
    outcomes = ps.get("outcomesModule", {})
    eligibility = ps.get("eligibilityModule", {})
    description = ps.get("descriptionModule", {})
    sponsor = ps.get("sponsorCollaboratorsModule", {})
    oversight = ps.get("oversightModule", {})
    contacts = ps.get("contactsLocationsModule", {})
    design_info = design.get("designInfo", {}) or {}
    masking_info = design_info.get("maskingInfo", {}) or {}

    compatibility_blocks = {
        "identification": {
            "nct_id": idm.get("nctId"),
            "brief_title": idm.get("briefTitle"),
            "official_title": idm.get("officialTitle"),
            "organization": idm.get("organization", {}).get("fullName"),
            "lead_sponsor": sponsor.get("leadSponsor", {}).get("name"),
        },
        "status": {
            "overall_status": status.get("overallStatus"),
            "start_date": status.get("startDateStruct", {}).get("date"),
            "primary_completion_date": status.get("primaryCompletionDateStruct", {}).get("date"),
            "completion_date": status.get("completionDateStruct", {}).get("date"),
            "first_submit_date": status.get("studyFirstSubmitDate"),
            "first_post_date": status.get("studyFirstPostDateStruct", {}).get("date"),
            "last_update_submit_date": status.get("lastUpdateSubmitDate"),
            "last_update_post_date": status.get("lastUpdatePostDateStruct", {}).get("date"),
        },
        "design": {
            "study_type": design.get("studyType"),
            "phases": design.get("phases"),
            "allocation": design_info.get("allocation"),
            "intervention_model": design_info.get("interventionModel"),
            "primary_purpose": design_info.get("primaryPurpose"),
            "masking": masking_info.get("masking"),
            "who_masked": masking_info.get("whoMasked"),
            "enrollment": design.get("enrollmentInfo"),
        },
        "conditions": ps.get("conditionsModule", {}).get("conditions", []),
        "brief_summary": description.get("briefSummary"),
        "detailed_description": description.get("detailedDescription"),
        "arms": arms.get("armGroups", []),
        "interventions": arms.get("interventions", []),
        "outcomes": {
            "primary": outcomes.get("primaryOutcomes", []),
            "secondary": outcomes.get("secondaryOutcomes", []),
            "other": outcomes.get("otherOutcomes", []),
        },
        "eligibility": {
            "criteria": eligibility.get("eligibilityCriteria"),
            "sex": eligibility.get("sex"),
            "minimum_age": eligibility.get("minimumAge"),
            "maximum_age": eligibility.get("maximumAge"),
            "healthy_volunteers": eligibility.get("healthyVolunteers"),
        },
        "oversight": {
            "has_dmc": oversight.get("oversightHasDmc"),
            "fda_regulated_drug": oversight.get("isFdaRegulatedDrug"),
            "fda_regulated_device": oversight.get("isFdaRegulatedDevice"),
        },
        "contacts_locations": contacts,
    }
    source_protocol = build_source_protocol(
        record,
        source_registry="ClinicalTrials.gov",
        source_file=source_file,
        protocol_sections=ps,
        results_sections=results_section,
        source_specific={
            "has_results": raw.get("hasResults"),
            "derivedSection": raw.get("derivedSection", {}),
            "documentSection": raw.get("documentSection", {}),
        },
        raw_evidence_files=raw_evidence_files,
        extra=compatibility_blocks,
    )
    return dict(source_protocol)


def json_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
