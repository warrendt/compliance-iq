"""Regression coverage for jurisdiction-aware SLZ residency enforcement."""

import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.models import ControlMapping
from app.models.sovereignty import SovereigntyMapping
from app.services.jurisdiction_profile_service import get_jurisdiction_profile_service
from app.services.policy_service import PolicyGenerationService


_ALLOWED_LOCATIONS_ID = "e56962a6-4747-49cd-b67b-bf8b01975c4c"
_RESOURCE_GROUP_LOCATIONS_ID = "e765b5de-1225-4ba3-bd56-1ac6695af988"


def _residency_mapping() -> ControlMapping:
    return ControlMapping(
        external_control_id="RES-1",
        external_control_name="Restrict data residency",
        mcsb_control_id="NS-1",
        mcsb_control_name="Network segmentation",
        mcsb_domain="Network Security",
        confidence_score=0.95,
        reasoning="Require data residency enforcement.",
        azure_policy_ids=[],
        mapping_type="exact",
        sovereignty=SovereigntyMapping(
            sovereignty_level="L1",
            sovereignty_objectives=["SO-1"],
            slz_policy_names=["allowed-locations"],
        ),
    )


def test_jurisdiction_profiles_suggest_known_locations_without_fallback() -> None:
    service = get_jurisdiction_profile_service()

    uae = service.recommend("United Arab Emirates")
    assert uae["status"] == "known"
    assert uae["suggested_locations"] == ["uaenorth"]
    assert uae["restricted_locations"] == ["uaecentral"]
    assert uae["requires_confirmation"] is True

    france = service.recommend("France")
    assert france["status"] == "known"
    assert france["suggested_locations"] == ["francecentral"]

    unknown = service.recommend("Example EMEA Jurisdiction")
    assert unknown["status"] == "unknown"
    assert unknown["suggested_locations"] == []
    assert "Select the permitted locations" in unknown["guidance"]


def test_slz_export_binds_confirmed_locations_to_canonical_policy_references() -> None:
    result = PolicyGenerationService().generate_slz_initiatives(
        mappings=[_residency_mapping()],
        framework_name="UAE NCSP",
        allowed_locations=["uaenorth"],
        country_or_region="United Arab Emirates",
        jurisdiction_profile={"profile_id": "AE"},
        resolution_choices=[
            {
                "requirement": "key_custody",
                "path": "Not applicable to selected controls",
                "status": "complete",
            },
            {
                "requirement": "confidential_compute",
                "path": "Not applicable to selected controls",
                "status": "complete",
            },
        ],
    )

    artifact = result["archetype_artifacts"]["sovereign_root"]
    initiative = artifact["initiative_json"]["properties"]
    references = {
        item["policyDefinitionId"].rsplit("/", 1)[-1]: item
        for item in initiative["policyDefinitions"]
    }

    assert set((_ALLOWED_LOCATIONS_ID, _RESOURCE_GROUP_LOCATIONS_ID)) <= set(references)
    for policy_id in (_ALLOWED_LOCATIONS_ID, _RESOURCE_GROUP_LOCATIONS_ID):
        assert references[policy_id]["parameters"] == {
            "listOfAllowedLocations": {
                "value": "[parameters('listOfAllowedLocations')]",
            }
        }

    assert initiative["parameters"]["listOfAllowedLocations"]["defaultValue"] == ["uaenorth"]
    assert initiative["metadata"]["jurisdiction"] == "United Arab Emirates"
    assert initiative["metadata"]["resolvedSovereigntyPolicies"]["allowed-locations"] == _ALLOWED_LOCATIONS_ID
    assert "allowed-locations" not in {
        item["policyDefinitionId"] for item in initiative["policyDefinitions"]
    }
    assert result["summary"]["sovereignty_coverage_state"] == "partially_resolved"
    assert "listOfAllowedLocations" in artifact["bicep_template"]
