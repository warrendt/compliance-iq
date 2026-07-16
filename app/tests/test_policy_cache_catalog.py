"""Tests for catalog-first policy detail resolution.

The policy detail lookup must resolve built-in policy GUIDs to readable
display names + descriptions from the local catalog snapshot, without
depending on Cosmos DB or a Microsoft Learn search.
"""
import json
from pathlib import Path

import pytest

from app.services.policy_cache_service import (
    PolicyCacheService,
    _portal_definition_url,
    _is_stub_description,
)
from app.services.policy_catalog_service import get_policy_catalog_service

CATALOG_PATH = (
    Path(__file__).resolve().parent.parent
    / "backend/app/data/policy_catalog/azure_policy_catalog.json"
)


def _first_catalog_definition() -> dict:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return data["definitions"][0]


def test_portal_definition_url_encodes_definition_id():
    guid = "afd5d60a-48d2-8073-1ec2-6687e22f2ddd"
    url = _portal_definition_url(guid)
    assert url.startswith(
        "https://portal.azure.com/#view/Microsoft_Azure_Policy/PolicyDetailBlade/definitionId/"
    )
    # The definition resource id must be percent-encoded (slashes escaped).
    assert "%2Fproviders%2FMicrosoft.Authorization%2FpolicyDefinitions%2F" in url
    assert url.endswith(guid)


@pytest.mark.asyncio
async def test_get_policy_details_resolves_from_catalog():
    """A real built-in GUID resolves to its catalog name/description."""
    definition = _first_catalog_definition()
    guid = definition["name"]

    service = PolicyCacheService()
    results = await service.get_policy_details([guid])

    assert guid in results
    detail = results[guid]
    assert detail["display_name"] == definition["display_name"]
    assert detail["display_name"]  # non-empty, human-readable
    assert not detail["display_name"].startswith("Policy ")  # not the stub
    assert detail["description"] == definition["description"]
    assert detail["learn_url"].endswith(guid)
    assert detail["category"] == definition.get("category", "")


@pytest.mark.asyncio
async def test_get_policy_details_skips_invalid_guids():
    service = PolicyCacheService()
    results = await service.get_policy_details(["not-a-guid", ""])
    assert results == {}


@pytest.mark.asyncio
async def test_get_policy_details_deduplicates_and_batches():
    definition = _first_catalog_definition()
    guid = definition["name"]

    service = PolicyCacheService()
    results = await service.get_policy_details([guid, guid, guid])

    assert list(results.keys()) == [guid]


@pytest.mark.parametrize(
    "display_name,description,expected",
    [
        # Empty description is a stub.
        ("Establish a secure software development program", "", True),
        # CMA_ prefix that just repeats the display name is a stub.
        (
            "Establish a secure software development program",
            "CMA_0259 - Establish a secure software development program",
            True,
        ),
        # Exact repeat of the name (no CMA prefix) is a stub.
        ("Review development process, standards and tools",
         "Review development process, standards and tools", True),
        # A genuine, informative description is NOT a stub.
        (
            "Audit virtual machines without disaster recovery configured",
            "Audit virtual machines which do not have disaster recovery configured.",
            False,
        ),
    ],
)
def test_is_stub_description(display_name, description, expected):
    assert _is_stub_description(display_name, description) is expected


@pytest.mark.asyncio
async def test_get_policy_details_flags_stub_descriptions():
    """CMA_ Regulatory Compliance policies are flagged as description stubs."""
    guid = "e750ca06-1824-464a-2cf3-d0fa754d1cb4"  # CMA_0259, real built-in

    service = PolicyCacheService()
    results = await service.get_policy_details([guid])

    assert guid in results
    detail = results[guid]
    assert detail["display_name"] == "Establish a secure software development program"
    # The Azure description just repeats the name -> flagged so the UI can hide it.
    assert detail["description_is_stub"] is True
    assert detail["category"] == "Regulatory Compliance"


@pytest.mark.asyncio
async def test_get_policy_details_rich_description_not_flagged():
    """A real Audit/Deny policy keeps its informative description (not a stub)."""
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    rich = next(
        d for d in data["definitions"]
        if not _is_stub_description(d.get("display_name", ""), d.get("description", ""))
    )
    guid = rich["name"]

    service = PolicyCacheService()
    results = await service.get_policy_details([guid])

    assert results[guid]["description_is_stub"] is False
    assert results[guid]["description"] == rich["description"]


@pytest.mark.asyncio
async def test_non_catalog_guid_falls_through(monkeypatch):
    """A GUID absent from the catalog is not resolved by the catalog pass."""
    catalog = get_policy_catalog_service()
    monkeypatch.setattr(catalog, "get", lambda name: None)

    # Force the Cosmos + Learn passes to be no-ops so we isolate the fallthrough.
    from app.services import policy_cache_service as mod

    monkeypatch.setattr(mod.cosmos_client, "database", None)

    service = PolicyCacheService()

    async def _no_learn(_pid):
        return None

    monkeypatch.setattr(service, "_fetch_from_learn", _no_learn)

    guid = "00000000-0000-0000-0000-000000000000"
    results = await service.get_policy_details([guid])
    assert results == {}
