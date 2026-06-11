from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any, Iterable

from bs4 import BeautifulSoup
from bs4.element import Tag


def normalize_text(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\r", "\n")
    lines = []
    for raw_line in value.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def table_to_text(table: Tag) -> str:
    lines = []
    for row in table.find_all("tr", recursive=False):
        cells = [
            normalize_text(cell.get_text(" ", strip=False))
            for cell in row.find_all(["th", "td"], recursive=False)
        ]
        cells = [cell for cell in cells if cell]
        if not cells:
            continue
        if len(cells) == 2:
            lines.append(f"{cells[0]}: {cells[1]}")
        else:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_fragment_text(fragment: str) -> str:
    soup = BeautifulSoup(fragment, "html.parser")
    tables = soup.find_all("table")
    if tables:
        table_pieces = [table_to_text(table) for table in tables]
        table_pieces = [piece for piece in table_pieces if piece]
        if table_pieces:
            return "\n\n".join(table_pieces)

    return normalize_text(soup.get_text("\n", strip=False))


def insert_value(container: OrderedDict[str, Any], key: str, value: str) -> None:
    if key not in container:
        container[key] = value
        return

    existing = container[key]
    if isinstance(existing, list):
        existing.append(value)
    else:
        container[key] = [existing, value]


def slugify(text: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    return slug or "field"


def iter_flattened(prefix: str, value: Any) -> Iterable[tuple[str, str]]:
    if isinstance(value, list):
        for index, item in enumerate(value, start=1):
            suffix = "" if index == 1 else f"_{index}"
            yield f"{prefix}{suffix}", stringify(item)
        return

    yield prefix, stringify(value)


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)
