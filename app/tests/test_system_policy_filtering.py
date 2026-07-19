"""Tests that built-in policies which cannot be part of a custom policy set
(e.g. Azure "System Policy" built-ins) are never recommended by the retrieval
catalog and are stripped at generation time, so the emitted initiative deploys
cleanly.

Regression for the observed deploy where "System Policy" built-ins leaked into
the custom initiative and Azure rejected them with "can not be part of a custom
policy set", breaking the generated deployment scripts.
"""

import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.models import ControlMapping, PolicyGenerationRequest
from app.services.policy_service import PolicyGenerationService
from app.services.policy_catalog_service import (
    get_policy_catalog_service,
    _is_non_includable_category,
)

# Real "System Policy" built-ins present in the catalog snapshot.
SYSTEM_POLICY_GUID = "f69cd8b8-9a6e-46b4-be84-244e8b127944"  # MFA Enforcement - Delete
SYSTEM_POLICY_GUID_2 = "54f51f64-eaa5-44cf-8674-830bcfd14d21"  # MFA Enforcement - Write
# A valid, includable built-in GUID (unknown to the catalog snapshot -> kept).
VALID_GUID = "18adea5e-f416-4d0f-8aa8-d24321e3e274"


def _mapping(control_id: str, policy_ids: list[str]) -> ControlMapping:
    return ControlMapping(
        external_control_id=control_id,
        external_control_name=f"Control {control_id}",
        mcsb_control_id="IM-1",
        mcsb_control_name="Protect identities",
        mcsb_domain="Identity",
        confidence_score=0.9,
        reasoning="Relevant control",
        azure_policy_ids=policy_ids,
        mapping_type="exact",
    )


# ── catalog classification ───────────────────────────────────────────────────

def test_is_non_includable_category_matches_system_policy_casefold():
    assert _is_non_includable_category("System Policy") is True
    assert _is_non_includable_category("SYSTEM POLICY") is True
    assert _is_non_includable_category("Regulatory Compliance") is False


def test_catalog_flags_known_system_policy_guid():
    catalog = get_policy_catalog_service()
    assert catalog.is_non_includable(SYSTEM_POLICY_GUID) is True


def test_catalog_does_not_flag_unknown_guid():
    # Never strip a policy the catalog cannot positively classify.
    catalog = get_policy_catalog_service()
    assert catalog.is_non_includable(VALID_GUID) is False
    assert catalog.is_non_includable("not-a-real-guid") is False


def test_catalog_search_excludes_system_policy():
    catalog = get_policy_catalog_service()
    results = catalog.search("multi factor authentication enforcement", top_n=50)
    names = {c.name for c in results}
    assert SYSTEM_POLICY_GUID not in names
    assert SYSTEM_POLICY_GUID_2 not in names
    assert all(c.category.strip().casefold() != "system policy" for c in results)


# ── generation stripping ─────────────────────────────────────────────────────

def test_generation_strips_system_policy_builtin():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="UAE National Cloud Security Policy",
        mappings=[
            _mapping("2.3.2.1", [VALID_GUID]),
            _mapping("2.7.1.3", [SYSTEM_POLICY_GUID]),
        ],
    )

    response = service.generate_initiative(request)

    emitted = [
        pd.policy_definition_id
        for pd in response.initiative.properties.policy_definitions
    ]
    assert f"/providers/Microsoft.Authorization/policyDefinitions/{VALID_GUID}" in emitted
    assert all(SYSTEM_POLICY_GUID not in pid for pid in emitted)
    assert response.included_policies == 1
    assert response.excluded_builtin_policies == 1
    assert any("non-includable" in w.lower() for w in response.warnings)


def test_generation_deduplicates_system_policy_across_controls():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="Framework",
        mappings=[
            _mapping("CTRL-1", [SYSTEM_POLICY_GUID]),
            _mapping("CTRL-2", [SYSTEM_POLICY_GUID]),
        ],
    )

    response = service.generate_initiative(request)

    assert response.included_policies == 0
    assert response.excluded_builtin_policies == 1
