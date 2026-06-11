from __future__ import annotations

from .base import RegistrySource
from .umin_ctr import UminCtrSource


SOURCE_REGISTRY: dict[str, type[RegistrySource]] = {
    UminCtrSource.name: UminCtrSource,
}


def get_source(name: str) -> RegistrySource:
    try:
        source_class = SOURCE_REGISTRY[name]
    except KeyError as exc:
        choices = ", ".join(sorted(SOURCE_REGISTRY))
        raise ValueError(f"Unknown source {name!r}. Available sources: {choices}") from exc
    return source_class()
