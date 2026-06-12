from __future__ import annotations

import re

from .types import LiteratureInput


UMIN_ID_RE = re.compile(r"^UMIN\d{9}$", re.IGNORECASE)
NCT_ID_RE = re.compile(r"^NCT\d+$", re.IGNORECASE)


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
