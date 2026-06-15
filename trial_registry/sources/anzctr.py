from __future__ import annotations

import re
from urllib.parse import parse_qs, quote, urljoin, urlparse

from bs4 import BeautifulSoup

from ..http import fetch_html
from ..text import normalize_text
from ..types import QueryInput, SearchMatch
from .link_based import LinkBasedRegistrySource, live_search_enabled


class AnzctrSource(LinkBasedRegistrySource):
    name = "anzctr"
    registry_label = "ANZCTR"
    protocol_filename = "ANZCTR_protocol.json"
    protocol_file_key = "anzctr_protocol"
    id_query_types = {"actrn_id"}
    link_only_note = "search_required"

    def search(self, query: QueryInput) -> list[SearchMatch]:
        if query.query_type in self.id_query_types:
            urls = self.urls_for_id(query.raw_input)
            if live_search_enabled():
                try:
                    html = fetch_html(urls["search"])
                    matches = parse_anzctr_search_results(html, query=query, source=self)
                    if matches:
                        return matches
                except Exception:
                    return [self.unresolved_match(query, urls=urls, fetch_status="search_required")]
            return [self.unresolved_match(query, urls=urls, fetch_status="search_required")]
        return super().search(query)

    def urls_for_id(self, registry_id: str) -> dict[str, str]:
        encoded = quote(registry_id)
        return {"search": f"https://www.anzctr.org.au/TrialSearch.aspx#&&searchTxt={encoded}"}

    def extract_id_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        detail_id = parse_qs(parsed.query).get("id", [""])[0].strip()
        if detail_id:
            return f"ANZCTR-detail-{detail_id}"
        match = re.search(r"((?:ACTRN|ANZCTR-?)\d{10,20})", url, flags=re.IGNORECASE)
        return re.sub(r"^ANZCTR-?", "ACTRN", match.group(1), flags=re.IGNORECASE).upper() if match else ""

    def can_fetch_detail_url(self, url: str) -> bool:
        lowered = url.lower()
        return "anzctr.org.au" in lowered and "trialreview.aspx" in lowered


def parse_anzctr_search_results(
    html: str,
    *,
    query: QueryInput,
    source: AnzctrSource,
) -> list[SearchMatch]:
    soup = BeautifulSoup(html, "lxml")
    registry_id = query.raw_input.upper()
    matches: list[SearchMatch] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "trialreview.aspx" not in href.lower():
            continue
        container = link.find_parent("tr") or link.find_parent(["li", "div"]) or link
        text = normalize_text(container.get_text("\n", strip=False))
        if registry_id not in text.upper() and registry_id not in href.upper():
            continue
        detail_url = urljoin("https://www.anzctr.org.au/", href)
        matches.append(
            source.detail_match_from_url(
                query=query,
                detail_url=detail_url,
                match_key=registry_id,
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
