from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from .types import QueryInput


RECEIPT_RE = re.compile(r"^R\d{9}$", re.IGNORECASE)
UMIN_ID_RE = re.compile(r"^UMIN\d{9}$", re.IGNORECASE)


def resolve_query(raw_input: str, source_hint: str = "umin_ctr") -> QueryInput:
    value = raw_input.strip()
    if not value:
        raise ValueError("Input query cannot be empty.")

    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
        if query.get("recptno"):
            return QueryInput(value, "detail_url", source_hint)
        return QueryInput(value, "url", source_hint)

    if RECEIPT_RE.fullmatch(value):
        return QueryInput(value.upper(), "receipt_number", source_hint)

    if UMIN_ID_RE.fullmatch(value):
        return QueryInput(value.upper(), "umin_id", source_hint)

    # 当前版本暂不启用关键词搜索，保留接口用于后续扩展。
    # Keyword search is reserved for a later version and intentionally disabled in v1.
    return QueryInput(value, "keyword_search_not_enabled", source_hint)
