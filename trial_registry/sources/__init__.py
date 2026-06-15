from __future__ import annotations

from .anzctr import AnzctrSource
from .base import RegistrySource
from .chictr import ChictrSource
from .china_drug_trials import ChinaDrugTrialsSource
from .clinicaltrials_gov import ClinicalTrialsGovSource
from .ctis import CtisSource
from .euctr import EuCtrSource
from .isrctn import IsrctnSource
from .umin_ctr import UminCtrSource


SOURCE_REGISTRY: dict[str, type[RegistrySource]] = {
    AnzctrSource.name: AnzctrSource,
    ChictrSource.name: ChictrSource,
    ChinaDrugTrialsSource.name: ChinaDrugTrialsSource,
    ClinicalTrialsGovSource.name: ClinicalTrialsGovSource,
    CtisSource.name: CtisSource,
    EuCtrSource.name: EuCtrSource,
    IsrctnSource.name: IsrctnSource,
    UminCtrSource.name: UminCtrSource,
}


def get_source(name: str) -> RegistrySource:
    try:
        source_class = SOURCE_REGISTRY[name]
    except KeyError as exc:
        choices = ", ".join(sorted(SOURCE_REGISTRY))
        raise ValueError(f"Unknown source {name!r}. Available sources: {choices}") from exc
    return source_class()
