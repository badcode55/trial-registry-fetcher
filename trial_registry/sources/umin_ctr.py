from __future__ import annotations

import re
from collections import OrderedDict
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from ..http import fetch_html
from ..text import extract_fragment_text, insert_value, iter_flattened, normalize_text, slugify
from ..types import NormalizedRow, QueryInput, SearchMatch, StudyRecord
from .base import RegistrySource


DETAIL_BASE_URL = "https://center6.umin.ac.jp/cgi-open-bin/ctr_e/ctr_view.cgi?recptno={recptno}"
SEARCH_URL = "https://center6.umin.ac.jp/cgi-open-bin/ctr_e/index.cgi"

TEMPLATE_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("title_brief", "Basic information.Public title"),
    ("title_acronym", "Basic information.Acronym"),
    ("scientific_title", "Basic information.Scientific Title"),
    ("scientific_title_acronym", "Basic information.Scientific Title:Acronym"),
    ("region", "Basic information.Region"),
    ("condition", "Condition.Condition"),
    ("classification_by_specialty", "Condition.Classification by specialty"),
    ("classification_by_malignancy", "Condition.Classification by malignancy"),
    ("genomic_information", "Condition.Genomic information"),
    ("narrative_objectives", "Objectives.Narrative objectives1"),
    ("basic_objectives", "Objectives.Basic objectives2"),
    ("basic_objectives_other", "Objectives.Basic objectives -Others"),
    ("trial_characteristics_1", "Objectives.Trial characteristics_1"),
    ("trial_characteristics_2", "Objectives.Trial characteristics_2"),
    ("developmental_phase", "Objectives.Developmental phase"),
    ("primary_outcomes", "Assessment.Primary outcomes"),
    ("key_secondary_outcomes", "Assessment.Key secondary outcomes"),
    ("study_type", "Base.Study type"),
    ("basic_design", "Study design.Basic design"),
    ("randomization", "Study design.Randomization"),
    ("randomization_unit", "Study design.Randomization unit"),
    ("blinding", "Study design.Blinding"),
    ("control", "Study design.Control"),
    ("stratification", "Study design.Stratification"),
    ("dynamic_allocation", "Study design.Dynamic allocation"),
    ("institution_consideration", "Study design.Institution consideration"),
    ("blocking", "Study design.Blocking"),
    ("concealment", "Study design.Concealment"),
    ("number_of_arms", "Intervention.No. of arms"),
    ("purpose_of_intervention", "Intervention.Purpose of intervention"),
    ("type_of_intervention", "Intervention.Type of intervention"),
    ("interventions_control_1", "Intervention.Interventions/Control_1"),
    ("interventions_control_2", "Intervention.Interventions/Control_2"),
    ("interventions_control_3", "Intervention.Interventions/Control_3"),
    ("interventions_control_4", "Intervention.Interventions/Control_4"),
    ("interventions_control_5", "Intervention.Interventions/Control_5"),
    ("interventions_control_6", "Intervention.Interventions/Control_6"),
    ("interventions_control_7", "Intervention.Interventions/Control_7"),
    ("interventions_control_8", "Intervention.Interventions/Control_8"),
    ("interventions_control_9", "Intervention.Interventions/Control_9"),
    ("interventions_control_10", "Intervention.Interventions/Control_10"),
    ("age_lower_limit", "Eligibility.Age-lower limit"),
    ("age_upper_limit", "Eligibility.Age-upper limit"),
    ("gender", "Eligibility.Gender"),
    ("key_inclusion_criteria", "Eligibility.Key inclusion criteria"),
    ("key_exclusion_criteria", "Eligibility.Key exclusion criteria"),
    ("target_sample_size", "Eligibility.Target sample size"),
    ("lead_principal_investigator_name", "Research contact person.Name of lead principal investigator"),
    ("lead_principal_investigator_organization", "Research contact person.Organization"),
    ("lead_principal_investigator_division", "Research contact person.Division name"),
    ("lead_principal_investigator_zip_code", "Research contact person.Zip code"),
    ("lead_principal_investigator_address", "Research contact person.Address"),
    ("lead_principal_investigator_tel", "Research contact person.TEL"),
    ("lead_principal_investigator_email", "Research contact person.Email"),
    ("public_contact_name", "Public contact.Name of contact person"),
    ("public_contact_organization", "Public contact.Organization"),
    ("public_contact_division", "Public contact.Division name"),
    ("public_contact_zip_code", "Public contact.Zip code"),
    ("public_contact_address", "Public contact.Address"),
    ("public_contact_tel", "Public contact.TEL"),
    ("public_contact_homepage_url", "Public contact.Homepage URL"),
    ("public_contact_email", "Public contact.Email"),
    ("sponsor_institute", "Sponsor or person.Institute"),
    ("sponsor_department", "Sponsor or person.Department"),
    ("sponsor_personal_name", "Sponsor or person.Personal name"),
    ("funding_organization", "Funding Source.Organization"),
    ("funding_division", "Funding Source.Division"),
    ("funding_category", "Funding Source.Category of Funding Organization"),
    ("funding_nationality", "Funding Source.Nationality of Funding Organization"),
    ("co_sponsor", "Other related organizations.Co-sponsor"),
    ("secondary_funders", "Other related organizations.Name of secondary funder(s)"),
    ("secondary_ids", "Secondary IDs.Secondary IDs"),
    ("study_id_1", "Secondary IDs.Study ID_1"),
    ("study_id_2", "Secondary IDs.Study ID_2"),
    ("institutions", "Institutions.Institutions"),
    ("date_of_disclosure", "Other administrative information.Date of disclosure of the study information"),
    ("url_releasing_protocol", "Related information.URL releasing protocol"),
    ("publication_of_results", "Related information.Publication of results"),
    ("url_results_publications", "Result.URL related to results and publications"),
    ("enrolled_participants", "Result.Number of participants that the trial has enrolled"),
    ("results", "Result.Results"),
    ("recruitment_status", "Progress.Recruitment status"),
    ("date_of_protocol_fixation", "Progress.Date of protocol fixation"),
    ("date_of_irb", "Progress.Date of IRB"),
    ("anticipated_trial_start_date", "Progress.Anticipated trial start date"),
    ("last_follow_up_date", "Progress.Last follow-up date"),
    ("registered_date", "Management information.Registered date"),
    ("last_modified_on", "Management information.Last modified on"),
)


class UminCtrSource(RegistrySource):
    name = "umin_ctr"

    def search(self, query: QueryInput) -> list[SearchMatch]:
        if query.query_type in {"receipt_number", "detail_url"}:
            recptno = extract_recptno(query.raw_input)
            return [
                SearchMatch(
                    source=self.name,
                    match_rank=1,
                    match_key=recptno,
                    title="",
                    detail_url=DETAIL_BASE_URL.format(recptno=recptno),
                    raw_summary={},
                    matched_by=query.query_type,
                )
            ]

        if query.query_type == "umin_id":
            html = fetch_html(SEARCH_URL, data={"function": "04", "sort": "03", "ctrno": query.raw_input})
            return parse_search_results(html, matched_by=query.query_type)

        if query.query_type in {"title", "keyword_search_not_enabled"}:
            # 当前版本暂不启用关键词搜索，保留接口用于后续扩展。
            # Keyword search is reserved for a later version and intentionally disabled in v1.
            raise ValueError("Keyword search is not enabled in this ID-only version.")

        raise ValueError(f"UMIN-CTR does not support query type {query.query_type!r}.")

    def fetch_detail(self, match: SearchMatch) -> StudyRecord:
        html = fetch_html(match.detail_url)
        return parse_detail_page(html, detail_url=match.detail_url, match=match)

    def normalize(
        self,
        record: StudyRecord,
        *,
        run_id: str,
        query: QueryInput,
        match_count: int,
    ) -> NormalizedRow:
        row: NormalizedRow = OrderedDict()
        match = record.match
        row["run_id"] = run_id
        row["source"] = record.source
        row["query_value"] = query.raw_input
        row["query_type"] = query.query_type
        row["match_rank"] = str(match.match_rank if match else "")
        row["match_count"] = str(match_count)
        row["matched_by"] = match.matched_by if match else query.query_type
        row["detail_url"] = record.detail_url
        row["recptno"] = record.record_id
        row["umin_id"] = stringify_meta(record, "Unique ID issued by UMIN")

        used_keys = set()
        for column, path in TEMPLATE_FIELD_MAP:
            value = get_path_value(record, path)
            row[column] = value
            used_keys.add(path)

        for key, value in record.meta.items():
            flat_key = f"meta_{slugify(key)}"
            for output_key, output_value in iter_flattened(flat_key, value):
                if output_key not in row:
                    row[output_key] = output_value

        for section_name, fields in record.sections.items():
            for field_name, value in fields.items():
                path = f"{section_name}.{field_name}"
                if path in used_keys:
                    continue
                flat_key = f"extra_{slugify(section_name)}_{slugify(field_name)}"
                for output_key, output_value in iter_flattened(flat_key, value):
                    row[output_key] = output_value

        return row


def extract_recptno(target: str) -> str:
    if target.startswith(("http://", "https://")):
        parsed = urlparse(target)
        recptno = parse_qs(parsed.query).get("recptno", [""])[0].strip()
        if not recptno:
            raise ValueError("Could not find recptno in the provided URL.")
        return recptno.upper()

    recptno = target.strip().upper()
    if not re.fullmatch(r"R\d{9}", recptno):
        raise ValueError("Expected a receipt number like R000022360.")
    return recptno


def parse_detail_page(html: str, *, detail_url: str, match: SearchMatch | None = None) -> StudyRecord:
    soup = BeautifulSoup(html, "lxml")
    meta = parse_summary_table(soup)
    sections = parse_sections(html)
    recptno = stringify_meta_from_mapping(meta, "Receipt number") or extract_recptno(detail_url)
    return StudyRecord(
        source=UminCtrSource.name,
        record_id=recptno,
        detail_url=detail_url,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        meta=meta,
        sections=sections,
        raw_html_optional=html,
        match=match,
    )


def parse_summary_table(soup: BeautifulSoup) -> OrderedDict[str, object]:
    meta: OrderedDict[str, object] = OrderedDict()
    summary_table = soup.select_one("table.explain_table")
    if summary_table is None:
        return meta

    for row in summary_table.find_all("tr"):
        header = row.find("th")
        value = row.find("td")
        if header is None or value is None:
            continue
        insert_value(
            meta,
            normalize_text(header.get_text(" ", strip=False)),
            normalize_text(value.get_text("\n", strip=False)),
        )
    return meta


def parse_sections(html: str) -> OrderedDict[str, OrderedDict[str, object]]:
    match = re.search(r'<div class="wrap">(.*)</body>', html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Could not find the page wrapper.")

    wrap_html = match.group(1)
    sections: OrderedDict[str, OrderedDict[str, object]] = OrderedDict()
    section_pattern = re.compile(
        r"<h2>\s*(.*?)\s*</h2>(.*?)(?=<h2>|\Z)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    field_pattern = re.compile(
        r"<h3>\s*(.*?)\s*</h3>(.*?)(?=<div id=\"Input_vew|<h2>|\Z)",
        flags=re.IGNORECASE | re.DOTALL,
    )

    for section_match in section_pattern.finditer(wrap_html):
        section_name = normalize_text(
            BeautifulSoup(section_match.group(1), "lxml").get_text(" ", strip=False)
        )
        section_body = section_match.group(2)
        fields: OrderedDict[str, object] = OrderedDict()

        for field_match in field_pattern.finditer(section_body):
            label = normalize_text(
                BeautifulSoup(field_match.group(1), "lxml").get_text(" ", strip=False)
            )
            value = extract_fragment_text(field_match.group(2))
            insert_value(fields, label, value)

        sections[section_name] = fields

    return sections


def parse_search_results(html: str, *, matched_by: str) -> list[SearchMatch]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.index_vew_table")
    if table is None:
        return []

    matches: list[SearchMatch] = []
    rows = table.find_all("tr")
    for row in rows[1:]:
        cells = row.find_all("td", recursive=False)
        if len(cells) < 6:
            continue

        id_parts = split_cell(cells[1])
        title = normalize_text(cells[2].get_text("\n", strip=False))
        condition = normalize_text(cells[3].get_text("\n", strip=False))
        sponsor_status = split_cell(cells[4])
        detail_link = cells[5].find("a", string=lambda value: value and value.strip() == "Detail")
        if detail_link is None or not detail_link.get("href"):
            continue

        detail_url = urljoin(SEARCH_URL, detail_link["href"])
        recptno = extract_recptno(detail_url)
        raw_summary = {
            "unique_id": id_parts[0] if id_parts else "",
            "date_of_disclosure": id_parts[1] if len(id_parts) > 1 else "",
            "title": title,
            "condition": condition,
            "primary_person_or_sponsor": sponsor_status[0] if sponsor_status else "",
            "recruitment_status": sponsor_status[1] if len(sponsor_status) > 1 else "",
        }
        matches.append(
            SearchMatch(
                source=UminCtrSource.name,
                match_rank=len(matches) + 1,
                match_key=recptno,
                title=title,
                detail_url=detail_url,
                raw_summary=raw_summary,
                matched_by=matched_by,
            )
        )

    return matches


def split_cell(cell) -> list[str]:
    parts = [
        normalize_text(part)
        for part in cell.get_text("\n", strip=False).split("\n")
    ]
    return [part for part in parts if part]


def get_path_value(record: StudyRecord, path: str) -> str:
    section_name, field_name = path.split(".", 1)
    fields = record.sections.get(section_name)
    if fields is None:
        return ""
    value = fields.get(field_name, "")
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item is not None)
    return str(value) if value is not None else ""


def stringify_meta(record: StudyRecord, key: str) -> str:
    return stringify_meta_from_mapping(record.meta, key)


def stringify_meta_from_mapping(mapping: OrderedDict[str, object], key: str) -> str:
    value = mapping.get(key, "")
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item is not None)
    return str(value) if value is not None else ""
