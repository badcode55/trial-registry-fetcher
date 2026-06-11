from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

from .registry_ids import resolve_registry_id
from .types import LiteratureInput


class InputReader(ABC):
    @abstractmethod
    def read(self, path: Path) -> list[LiteratureInput]:
        raise NotImplementedError


class TxtLiteratureListReader(InputReader):
    def read(self, path: Path) -> list[LiteratureInput]:
        items: list[LiteratureInput] = []
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            items.append(parse_txt_line(line, raw_line))
        return items


class CSVInputReader(InputReader):
    """Reserved for future CSV inputs.

    当前版本暂未启用 CSV 输入，保留接口用于后续扩展。
    CSV input is reserved for a later version and intentionally disabled in v1.
    """

    def read(self, path: Path) -> list[LiteratureInput]:
        raise NotImplementedError("CSV input is reserved for a later version.")


class JSONInputReader(InputReader):
    """Reserved for future JSON inputs.

    当前版本暂未启用 JSON 输入，保留接口用于后续扩展。
    JSON input is reserved for a later version and intentionally disabled in v1.
    """

    def read(self, path: Path) -> list[LiteratureInput]:
        raise NotImplementedError("JSON input is reserved for a later version.")


def get_input_reader(input_format: str) -> InputReader:
    normalized = input_format.strip().lower()
    if normalized == "txt":
        return TxtLiteratureListReader()
    if normalized == "csv":
        return CSVInputReader()
    if normalized == "json":
        return JSONInputReader()
    raise ValueError("Unsupported input format. Available now: txt")


def parse_txt_line(line: str, raw_line: str) -> LiteratureInput:
    cleaned = re.sub(r"^\s*[-*]\s*", "", line).strip()
    if ":" not in cleaned:
        return LiteratureInput(
            literature_file="",
            registry_id="",
            registry_type="unknown",
            status="invalid_input",
            raw_line=raw_line,
            message="Expected '<literature file>: <registry id or not found>'.",
        )

    literature_file, registry_id = cleaned.split(":", 1)
    literature_file = literature_file.strip()
    registry_id = registry_id.strip()
    if not literature_file:
        return LiteratureInput(
            literature_file="",
            registry_id=registry_id,
            registry_type="unknown",
            status="invalid_input",
            raw_line=raw_line,
            message="Missing literature file name.",
        )

    return resolve_registry_id(literature_file, registry_id, raw_line)
