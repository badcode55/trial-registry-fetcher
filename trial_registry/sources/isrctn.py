from __future__ import annotations

import re

from .link_based import LinkBasedRegistrySource


class IsrctnSource(LinkBasedRegistrySource):
    name = "isrctn"
    registry_label = "ISRCTN"
    protocol_filename = "ISRCTN_protocol.json"
    protocol_file_key = "isrctn_protocol"
    id_query_types = {"isrctn_id"}

    def urls_for_id(self, registry_id: str) -> dict[str, str]:
        return {"detail": f"https://www.isrctn.com/{registry_id.upper()}"}

    def extract_id_from_url(self, url: str) -> str:
        match = re.search(r"/(ISRCTN\d{5,10})(?:[/?#]|$)", url, flags=re.IGNORECASE)
        return match.group(1).upper() if match else ""

    def can_fetch_detail_url(self, url: str) -> bool:
        return "isrctn.com" in url.lower()
