from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from .types import QueryInput


RECEIPT_RE = re.compile(r"^R\d{9}$", re.IGNORECASE)
UMIN_ID_RE = re.compile(r"^UMIN\d{9}$", re.IGNORECASE)
NCT_ID_RE = re.compile(r"^NCT\d+$", re.IGNORECASE)
ISRCTN_ID_RE = re.compile(r"^ISRCTN\d{5,10}$", re.IGNORECASE)
CHICTR_ID_RE = re.compile(r"^ChiCTR(?:-[A-Z]{2,5}-\d{5,12}|\d{6,12})$", re.IGNORECASE)
CHINA_DRUG_TRIAL_ID_RE = re.compile(r"^CTR\d{8}$", re.IGNORECASE)
ACTRN_ID_RE = re.compile(r"^(?:ACTRN|ANZCTR-?)\d{10,20}$", re.IGNORECASE)
EUDRACT_ID_RE = re.compile(r"^(?:EUCTR|EudraCT)?\s*\d{4}-\d{6}-\d{2}$", re.IGNORECASE)
CTIS_ID_RE = re.compile(r"^\d{4}-\d{6}-\d{2}-\d{2}$", re.IGNORECASE)


def resolve_query(raw_input: str, source_hint: str = "umin_ctr") -> QueryInput:
    value = raw_input.strip()
    if not value:
        raise ValueError("Input query cannot be empty.")

    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        if "isrctn.com" in host:
            return QueryInput(value, "detail_url", "isrctn")
        if "chictr.org.cn" in host:
            return QueryInput(value, "detail_url" if "showproj" in path else "search_url", "chictr")
        if "chinadrugtrials.org.cn" in host:
            return QueryInput(value, "detail_url" if "searchlistdetail" in path else "search_url", "china_drug_trials")
        if "anzctr.org.au" in host:
            return QueryInput(value, "detail_url" if "trialreview" in path else "search_url", "anzctr")
        if "clinicaltrialsregister.eu" in host:
            return QueryInput(value, "detail_url" if "/trial/" in path else "search_url", "euctr")
        if "euclinicaltrials.eu" in host:
            return QueryInput(value, "search_url", "ctis")
        if query.get("recptno"):
            return QueryInput(value, "detail_url", source_hint)
        return QueryInput(value, "url", source_hint)

    if RECEIPT_RE.fullmatch(value):
        return QueryInput(value.upper(), "receipt_number", source_hint)

    if UMIN_ID_RE.fullmatch(value):
        return QueryInput(value.upper(), "umin_id", "umin_ctr")

    if NCT_ID_RE.fullmatch(value):
        return QueryInput(value.upper(), "nct_id", "clinicaltrials_gov")

    if ISRCTN_ID_RE.fullmatch(value):
        return QueryInput(value.upper(), "isrctn_id", "isrctn")

    if CHICTR_ID_RE.fullmatch(value):
        return QueryInput(value.upper(), "chictr_id", "chictr")

    if CHINA_DRUG_TRIAL_ID_RE.fullmatch(value):
        return QueryInput(value.upper(), "china_drug_trial_id", "china_drug_trials")

    if ACTRN_ID_RE.fullmatch(value):
        normalized = re.sub(r"^ANZCTR-?", "ACTRN", value, flags=re.IGNORECASE).upper()
        return QueryInput(normalized, "actrn_id", "anzctr")

    if EUDRACT_ID_RE.fullmatch(value):
        return QueryInput(normalize_eudract_id(value), "eudract_id", "euctr")

    if CTIS_ID_RE.fullmatch(value):
        return QueryInput(value.upper(), "ctis_id", "ctis")

    # 当前版本暂不启用关键词搜索，保留接口用于后续扩展。
    # Keyword search is reserved for a later version and intentionally disabled in v1.
    return QueryInput(value, "keyword_search_not_enabled", source_hint)


def normalize_eudract_id(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^(?:EUCTR|EudraCT)\s*", "", value, flags=re.IGNORECASE)
    return value.upper()
