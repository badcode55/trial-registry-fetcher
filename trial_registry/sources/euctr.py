from __future__ import annotations

import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from ..http import fetch_html
from ..text import normalize_text
from ..types import QueryInput, SearchMatch
from .link_based import LinkBasedRegistrySource, live_search_enabled


class EuCtrSource(LinkBasedRegistrySource):
    name = "euctr"
    registry_label = "EU Clinical Trials Register"
    protocol_filename = "EUCTR_protocol.json"
    protocol_file_key = "euctr_protocol"
    id_query_types = {"eudract_id"}
    link_only_note = "search_required"

    def search(self, query: QueryInput) -> list[SearchMatch]:
        if query.query_type in self.id_query_types:
            urls = self.urls_for_id(query.raw_input)
            if live_search_enabled():
                try:
                    html = fetch_html(urls["search"])
                    matches = parse_euctr_search_results(html, query=query, source=self)
                    if matches:
                        return matches
                except Exception:
                    return [self.unresolved_match(query, urls=urls, fetch_status="search_required")]
            return [self.unresolved_match(query, urls=urls, fetch_status="search_required")]
        return super().search(query)

    def urls_for_id(self, registry_id: str) -> dict[str, str]:
        eudract_id = normalize_eudract_id(registry_id)
        encoded = quote(eudract_id)
        return {
            "search": f"https://www.clinicaltrialsregister.eu/ctr-search/search?query={encoded}",
            "results": f"https://www.clinicaltrialsregister.eu/ctr-search/trial/{eudract_id}/results",
        }

    def extract_id_from_url(self, url: str) -> str:
        match = re.search(r"(\d{4}-\d{6}-\d{2})", url)
        return match.group(1).upper() if match else ""

    def can_fetch_detail_url(self, url: str) -> bool:
        return "clinicaltrialsregister.eu" in url.lower() and "/ctr-search/trial/" in url.lower()


def normalize_eudract_id(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^(?:EUCTR|EudraCT)\s*", "", value, flags=re.IGNORECASE)
    return value.upper()


def parse_euctr_search_results(
    html: str,
    *,
    query: QueryInput,
    source: EuCtrSource,
) -> list[SearchMatch]:
    soup = BeautifulSoup(html, "lxml")
    eudract_id = normalize_eudract_id(query.raw_input)
    matches: list[SearchMatch] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/ctr-search/trial/" not in href.lower():
            continue
        if eudract_id not in href.upper():
            continue
        detail_url = urljoin("https://www.clinicaltrialsregister.eu/", href)
        container = link.find_parent("tr") or link.find_parent(["li", "div"]) or link
        text = normalize_text(container.get_text("\n", strip=False))
        matches.append(
            source.detail_match_from_url(
                query=query,
                detail_url=detail_url,
                match_key=eudract_id,
                title=normalize_text(link.get_text(" ", strip=False)),
                raw_summary={"search_result_text": text},
                match_rank=len(matches) + 1,
            )
        )

    return dedupe_matches(matches)


def dedupe_matches(matches: list[SearchMatch]) -> list[SearchMatch]:
    seen: set[str] = set()
    deduped: list[SearchMatch] = []
    for match in matches:
        if match.detail_url in seen:
            continue
        seen.add(match.detail_url)
        deduped.append(match)
    return deduped
