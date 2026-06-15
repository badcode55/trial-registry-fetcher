from __future__ import annotations

import re
from urllib.parse import urlparse

from .types import LiteratureInput


UMIN_ID_RE = re.compile(r"^UMIN\d{9}$", re.IGNORECASE)
NCT_ID_RE = re.compile(r"^NCT\d+$", re.IGNORECASE)
ISRCTN_ID_RE = re.compile(r"^ISRCTN\d{5,10}$", re.IGNORECASE)
CHICTR_ID_RE = re.compile(
    r"^ChiCTR(?:-[A-Z]{2,5}-\d{5,12}|\d{6,12})$",
    re.IGNORECASE,
)
CHINA_DRUG_TRIAL_ID_RE = re.compile(r"^CTR\d{8}$", re.IGNORECASE)
ACTRN_ID_RE = re.compile(r"^(?:ACTRN|ANZCTR-?)\d{10,20}$", re.IGNORECASE)
EUDRACT_ID_RE = re.compile(r"^(?:EUCTR|EudraCT)?\s*\d{4}-\d{6}-\d{2}$", re.IGNORECASE)
CTIS_ID_RE = re.compile(r"^\d{4}-\d{6}-\d{2}-\d{2}$", re.IGNORECASE)


def resolve_registry_id(literature_file: str, registry_id: str, raw_line: str) -> LiteratureInput:
    value = registry_id.strip()
    lowered = value.lower()

    if not value:
        return LiteratureInput(
            literature_file=literature_file,
            registry_id=value,
            registry_type="unknown",
            status="invalid_input",
            raw_line=raw_line,
            message="Missing registry ID.",
        )

    if lowered == "not found":
        return LiteratureInput(
            literature_file=literature_file,
            registry_id=value,
            registry_type="not_found",
            status="not_found",
            raw_line=raw_line,
            message="No registry ID was found for this literature item.",
        )

    if value.startswith(("http://", "https://")):
        routed = resolve_registry_url(literature_file, value, raw_line)
        if routed is not None:
            return routed

    if UMIN_ID_RE.fullmatch(value):
        return LiteratureInput(
            literature_file=literature_file,
            registry_id=value.upper(),
            registry_type="umin",
            status="ready",
            raw_line=raw_line,
            source_hint="umin_ctr",
        )

    if NCT_ID_RE.fullmatch(value):
        return LiteratureInput(
            literature_file=literature_file,
            registry_id=value.upper(),
            registry_type="nct",
            status="ready",
            raw_line=raw_line,
            source_hint="clinicaltrials_gov",
        )

    if ISRCTN_ID_RE.fullmatch(value):
        normalized = value.upper()
        return LiteratureInput(
            literature_file=literature_file,
            registry_id=normalized,
            registry_type="isrctn",
            status="ready",
            raw_line=raw_line,
            source_hint="isrctn",
        )

    if CHICTR_ID_RE.fullmatch(value):
        normalized = value.upper()
        return LiteratureInput(
            literature_file=literature_file,
            registry_id=normalized,
            registry_type="chictr",
            status="ready",
            raw_line=raw_line,
            source_hint="chictr",
        )

    if CHINA_DRUG_TRIAL_ID_RE.fullmatch(value):
        normalized = value.upper()
        return LiteratureInput(
            literature_file=literature_file,
            registry_id=normalized,
            registry_type="china_drug_trials",
            status="ready",
            raw_line=raw_line,
            source_hint="china_drug_trials",
        )

    if ACTRN_ID_RE.fullmatch(value):
        normalized = re.sub(r"^ANZCTR-?", "ACTRN", value, flags=re.IGNORECASE).upper()
        return LiteratureInput(
            literature_file=literature_file,
            registry_id=normalized,
            registry_type="anzctr",
            status="ready",
            raw_line=raw_line,
            source_hint="anzctr",
        )

    if EUDRACT_ID_RE.fullmatch(value):
        normalized = normalize_eudract_id(value)
        return LiteratureInput(
            literature_file=literature_file,
            registry_id=normalized,
            registry_type="euctr",
            status="ready",
            raw_line=raw_line,
            source_hint="euctr",
        )

    if CTIS_ID_RE.fullmatch(value):
        return LiteratureInput(
            literature_file=literature_file,
            registry_id=value.upper(),
            registry_type="ctis",
            status="ready",
            raw_line=raw_line,
            source_hint="ctis",
        )

    if looks_like_keyword(value):
        return LiteratureInput(
            literature_file=literature_file,
            registry_id=value,
            registry_type="keyword",
            status="keyword_search_not_enabled",
            raw_line=raw_line,
            message=(
                "Keyword search is reserved for a later version and intentionally disabled in v1."
            ),
        )

    # 新增注册库时只需扩展 ID 识别规则和 RegistrySource。
    # New registries should be added through ID resolver rules and RegistrySource adapters.
    return LiteratureInput(
        literature_file=literature_file,
        registry_id=value,
        registry_type="unknown",
        status="pending_source_integration",
        raw_line=raw_line,
        message="Registry source is not integrated yet.",
    )


def looks_like_keyword(value: str) -> bool:
    return bool(re.search(r"\s", value)) and not re.fullmatch(r"[A-Za-z0-9_-]+", value)


def normalize_eudract_id(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^(?:EUCTR|EudraCT)\s*", "", value, flags=re.IGNORECASE)
    return value.upper()


def resolve_registry_url(literature_file: str, value: str, raw_line: str) -> LiteratureInput | None:
    host = urlparse(value).netloc.lower()
    routes = [
        ("isrctn.com", "isrctn", "isrctn"),
        ("chictr.org.cn", "chictr", "chictr"),
        ("chinadrugtrials.org.cn", "china_drug_trials", "china_drug_trials"),
        ("anzctr.org.au", "anzctr", "anzctr"),
        ("clinicaltrialsregister.eu", "euctr", "euctr"),
        ("euclinicaltrials.eu", "ctis", "ctis"),
    ]
    for domain, registry_type, source_hint in routes:
        if domain in host:
            return LiteratureInput(
                literature_file=literature_file,
                registry_id=value,
                registry_type=registry_type,
                status="ready",
                raw_line=raw_line,
                source_hint=source_hint,
            )
    return None
