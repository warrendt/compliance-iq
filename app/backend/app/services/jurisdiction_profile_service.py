"""Country-aware Azure region recommendations for sovereignty exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


_AZURE_REGIONS_SOURCE = "https://learn.microsoft.com/en-us/azure/reliability/regions-list"


@dataclass(frozen=True)
class JurisdictionProfile:
    """A source-backed country profile that still requires operator confirmation."""

    identifier: str
    display_name: str
    aliases: Tuple[str, ...]
    suggested_locations: Tuple[str, ...]
    restricted_locations: Tuple[str, ...] = ()

    def to_recommendation(self, detected_jurisdiction: str) -> Dict[str, Any]:
        return {
            "status": "known",
            "profile_id": self.identifier,
            "display_name": self.display_name,
            "detected_jurisdiction": detected_jurisdiction,
            "suggested_locations": list(self.suggested_locations),
            "restricted_locations": list(self.restricted_locations),
            "source": _AZURE_REGIONS_SOURCE,
            "requires_confirmation": True,
        }


_PROFILES = (
    JurisdictionProfile("AE", "United Arab Emirates", ("uae", "united arab emirates"), ("uaenorth",), ("uaecentral",)),
    JurisdictionProfile("QA", "Qatar", ("qatar",), ("qatarcentral",)),
    JurisdictionProfile("IL", "Israel", ("israel",), ("israelcentral",)),
    JurisdictionProfile("GB", "United Kingdom", ("united kingdom", "uk", "great britain", "britain"), ("uksouth", "ukwest")),
    JurisdictionProfile("FR", "France", ("france",), ("francecentral",), ("francesouth",)),
    JurisdictionProfile("DE", "Germany", ("germany", "deutschland"), ("germanywestcentral",), ("germanynorth",)),
    JurisdictionProfile("IT", "Italy", ("italy", "italia"), ("italynorth",)),
    JurisdictionProfile("NO", "Norway", ("norway", "norge"), ("norwayeast",), ("norwaywest",)),
    JurisdictionProfile("PL", "Poland", ("poland", "polska"), ("polandcentral",)),
    JurisdictionProfile("ES", "Spain", ("spain", "espana", "españa"), ("spaincentral",)),
    JurisdictionProfile("SE", "Sweden", ("sweden", "sverige"), ("swedencentral",), ("swedensouth",)),
    JurisdictionProfile("ZA", "South Africa", ("south africa",), ("southafricanorth",), ("southafricawest",)),
    JurisdictionProfile("NL", "Netherlands", ("netherlands", "holland"), ("westeurope",)),
    JurisdictionProfile("IE", "Ireland", ("ireland",), ("northeurope",)),
)


class JurisdictionProfileService:
    """Resolve a scanned jurisdiction to a source-backed regional suggestion."""

    def recommend(self, country_or_region: str) -> Dict[str, Any]:
        normalized = (country_or_region or "").casefold().strip()
        for profile in _PROFILES:
            if any(alias in normalized for alias in profile.aliases):
                return profile.to_recommendation(country_or_region)
        return {
            "status": "unknown",
            "profile_id": None,
            "display_name": None,
            "detected_jurisdiction": country_or_region,
            "suggested_locations": [],
            "restricted_locations": [],
            "source": None,
            "requires_confirmation": True,
            "guidance": (
                "No source-backed Azure region profile is available for this jurisdiction. "
                "Select the permitted locations and record the residency rationale."
            ),
        }


_service = JurisdictionProfileService()


def get_jurisdiction_profile_service() -> JurisdictionProfileService:
    """Return the stateless jurisdiction-profile service."""

    return _service
