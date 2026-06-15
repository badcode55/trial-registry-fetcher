from __future__ import annotations

import json
import re
from urllib.parse import quote, urlencode, urljoin

from bs4 import BeautifulSoup

from ..browser_fetch import chrome_cdp_enabled, fetch_html_with_chrome_cdp
from ..http import fetch_html
from ..text import normalize_text
from ..types import QueryInput, SearchMatch, StudyRecord
from .link_based import LinkBasedRegistrySource, live_search_enabled


class ChinaDrugTrialsSource(LinkBasedRegistrySource):
    name = "china_drug_trials"
    registry_label = "China Drug Trials"
    protocol_filename = "ChinaDrugTrials_protocol.json"
    protocol_file_key = "china_drug_trials_protocol"
    id_query_types = {"china_drug_trial_id"}
    link_only_note = "blocked_by_site"

    def search(self, query: QueryInput) -> list[SearchMatch]:
        if query.query_type in self.id_query_types:
            urls = self.urls_for_id(query.raw_input)
            if live_search_enabled():
                try:
                    html = self.fetch_http_html(urls["search"])
                    matches = parse_china_drug_trials_search_results(html, query=query, source=self)
                    if matches:
                        return matches
                    browser_matches = self.search_with_browser_if_enabled(query, urls)
                    if browser_matches:
                        return browser_matches
                    if is_china_drug_trials_blocked_page(html):
                        return [
                            self.unresolved_match(
                                query,
                                urls=urls,
                                fetch_status="blocked_by_site",
                                fetch_note="cde_waf_javascript_challenge",
                            )
                        ]
                    return [
                        self.unresolved_match(
                            query,
                            urls=urls,
                            fetch_status="search_required",
                            fetch_note="cde_http_search_no_exact_detail_match",
                        )
                    ]
                except Exception:
                    browser_matches = self.search_with_browser_if_enabled(query, urls)
                    if browser_matches:
                        return browser_matches
                    return [self.unresolved_match(query, urls=urls, fetch_status="blocked_by_site")]
            return [self.unresolved_match(query, urls=urls, fetch_status="blocked_by_site")]
        return super().search(query)

    def search_with_browser_if_enabled(self, query: QueryInput, urls: dict[str, str]) -> list[SearchMatch]:
        if not chrome_cdp_enabled():
            return []
        try:
            html = self.fetch_browser_html(urls["search"])
        except Exception:
            return [
                self.unresolved_match(
                    query,
                    urls=urls,
                    fetch_status="blocked_by_site",
                    fetch_note="cde_chrome_cdp_search_failed",
                )
            ]
        matches = parse_china_drug_trials_search_results(html, query=query, source=self)
        if matches:
            return [as_browser_fetch_match(match) for match in matches]
        if is_china_drug_trials_blocked_page(html):
            return [
                self.unresolved_match(
                    query,
                    urls=urls,
                    fetch_status="blocked_by_site",
                    fetch_note="cde_chrome_cdp_still_blocked",
                )
            ]
        return [
            self.unresolved_match(
                query,
                urls=urls,
                fetch_status="search_required",
                fetch_note="cde_browser_search_no_exact_detail_match",
            )
        ]

    def fetch_detail(self, match: SearchMatch) -> StudyRecord:
        fetch_mode = match.raw_summary.get("fetch_mode")
        if fetch_mode in {"html", "cde_chrome_cdp_html"} and match.raw_summary.get("fetch_status") == "fetched":
            html = self.fetch_html_for_match(match)
            return self.record_from_html(match, html)
        return self.record_from_link(match)

    def fetch_html_for_match(self, match: SearchMatch) -> str:
        if match.raw_summary.get("fetch_mode") == "cde_chrome_cdp_html":
            return self.fetch_browser_html(match.detail_url)
        try:
            html = self.fetch_http_html(match.detail_url)
        except Exception:
            if chrome_cdp_enabled():
                return self.fetch_browser_html(match.detail_url)
            raise
        if is_china_drug_trials_blocked_page(html) and chrome_cdp_enabled():
            return self.fetch_browser_html(match.detail_url)
        return html

    def fetch_http_html(self, url: str) -> str:
        return fetch_html(url)

    def fetch_browser_html(self, url: str) -> str:
        return fetch_html_with_chrome_cdp(url)

    def urls_for_id(self, registry_id: str) -> dict[str, str]:
        encoded = quote(registry_id)
        return {
            "search": f"https://www.chinadrugtrials.org.cn/clinicaltrials.searchlist.dhtml?keywords={encoded}",
            "detail_candidate": "https://www.chinadrugtrials.org.cn/clinicaltrials.searchlistdetail.dhtml",
        }

    def extract_id_from_url(self, url: str) -> str:
        match = re.search(r"(CTR\d{8})", url, flags=re.IGNORECASE)
        return match.group(1).upper() if match else ""

    def can_fetch_detail_url(self, url: str) -> bool:
        return "chinadrugtrials.org.cn" in url.lower() and "searchlistdetail" in url.lower()

    def record_from_html(self, match: SearchMatch, html: str) -> StudyRecord:
        registry_id = (match.raw_summary.get("registration_number") or match.match_key).upper()
        if is_china_drug_trials_blocked_page(html):
            unresolved = self.record_from_link(
                self.unresolved_match(
                    QueryInput(registry_id, "china_drug_trial_id", self.name),
                    urls={"detail": match.detail_url},
                    fetch_status="blocked_by_site",
                    fetch_note="cde_waf_javascript_challenge",
                )
            )
            unresolved.raw_html_optional = html
            unresolved.raw_text_optional = normalize_text(html)
            return unresolved
        if not is_china_drug_trials_detail_page(html, registry_id):
            unresolved = self.record_from_link(
                self.unresolved_match(
                    QueryInput(registry_id, "china_drug_trial_id", self.name),
                    urls={"detail": match.detail_url},
                    fetch_status="parse_failed",
                    fetch_note="cde_detail_page_missing_expected_fields",
                )
            )
            unresolved.raw_html_optional = html
            unresolved.raw_text_optional = normalize_text(html)
            return unresolved
        return super().record_from_html(match, html)


def parse_china_drug_trials_search_results(
    html: str,
    *,
    query: QueryInput,
    source: ChinaDrugTrialsSource,
) -> list[SearchMatch]:
    soup = BeautifulSoup(html, "lxml")
    registry_id = query.raw_input.upper()
    matches: list[SearchMatch] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "searchlistdetail" not in href.lower():
            continue
        container = link.find_parent("tr") or link.find_parent(["li", "div"]) or link
        text = normalize_text(container.get_text("\n", strip=False))
        if registry_id not in text.upper() and registry_id not in href.upper():
            continue
        detail_url = urljoin("https://www.chinadrugtrials.org.cn/", href)
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

    for match in parse_china_drug_trials_form_detail_matches(soup, query=query, source=source):
        matches.append(match)

    return dedupe_matches(matches)


def parse_china_drug_trials_form_detail_matches(
    soup: BeautifulSoup,
    *,
    query: QueryInput,
    source: ChinaDrugTrialsSource,
) -> list[SearchMatch]:
    registry_id = query.raw_input.upper()
    detail_base_url = "https://www.chinadrugtrials.org.cn/clinicaltrials.searchlistdetail.dhtml"
    matches: list[SearchMatch] = []

    for link in soup.find_all("a", onclick=True, id=True):
        onclick = str(link.get("onclick") or "")
        if "getDetail" not in onclick:
            continue
        container = link.find_parent("tr") or link.find_parent(["li", "div"]) or link
        text = normalize_text(container.get_text("\n", strip=False))
        if registry_id not in text.upper():
            continue
        detail_id = str(link.get("id") or "").strip()
        ckm_index = str(link.get("name") or "").strip()
        if not detail_id:
            continue
        form_payload = {
            "id": detail_id,
            "ckm_index": ckm_index,
            "keywords": registry_id,
            "currentpage": "1",
        }
        detail_url = f"{detail_base_url}?{urlencode(form_payload)}"
        matches.append(
            SearchMatch(
                source=source.name,
                match_rank=len(matches) + 1,
                match_key=registry_id,
                title=normalize_text(link.get_text(" ", strip=False)),
                detail_url=detail_url,
                raw_summary={
                    "registration_number": registry_id,
                    "registry": source.registry_label,
                    "fetch_mode": "cde_detail_form_post_required",
                    "fetch_status": "search_required",
                    "fetch_note": "cde_detail_requires_browser_validated_form_post",
                    "search": source.urls_for_id(registry_id)["search"],
                    "detail": detail_url,
                    "detail_form_payload_json": json.dumps(form_payload, ensure_ascii=False),
                    "search_result_text": text,
                },
                matched_by=query.query_type,
            )
        )

    return matches


def is_china_drug_trials_blocked_page(html: str) -> bool:
    lowered = html.lower()
    return (
        "fssbbil1ugzbn7n80" in lowered
        or "4qbvtadbnlvic" in lowered
        or "content=\"lm&lt;" in lowered
        or "javascript challenge" in lowered
    )


def is_china_drug_trials_detail_page(html: str, registry_id: str) -> bool:
    text = normalize_text(html)
    if registry_id.upper() not in text.upper():
        return False
    required_terms = ["基本信息", "登记号", "试验状态"]
    return any(term in text for term in required_terms)


def dedupe_matches(matches: list[SearchMatch]) -> list[SearchMatch]:
    seen: set[str] = set()
    deduped: list[SearchMatch] = []
    for match in matches:
        if match.detail_url in seen:
            continue
        seen.add(match.detail_url)
        deduped.append(match)
    return deduped


def as_browser_fetch_match(match: SearchMatch) -> SearchMatch:
    raw_summary = dict(match.raw_summary)
    raw_summary.update(
        {
            "fetch_mode": "cde_chrome_cdp_html",
            "fetch_status": "fetched",
            "fetch_note": "",
            "browser_fetch": "chrome_cdp",
        }
    )
    return SearchMatch(
        source=match.source,
        match_rank=match.match_rank,
        match_key=match.match_key,
        title=match.title,
        detail_url=match.detail_url,
        raw_summary=raw_summary,
        matched_by=match.matched_by,
    )
