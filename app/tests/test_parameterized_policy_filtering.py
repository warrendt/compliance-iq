"""Tests that built-in policies with a required (no-default) parameter are
stripped at generation time, so the emitted custom initiative deploys cleanly.

Regression for the observed deploy where parameterized built-ins (e.g. Backup
policies needing a vault name/region) leaked into the custom initiative and
Azure rejected the set definition with ``MissingPolicyParameter``. The generator
cannot invent resource-specific values, so it excludes such built-ins and
reports the count honestly via ``excluded_parameterized_policies``.
"""

import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.models import ControlMapping, PolicyGenerationRequest
from app.services.policy_service import PolicyGenerationService
from app.services.policy_catalog_service import get_policy_catalog_service

# Real built-ins in the catalog snapshot that have a required (no-default)
# parameter (verified empirically to fail set-definition create without a value).
PARAMETERIZED_GUID = "f32ca068-2ada-4705-b5b5-84ce89422846"  # Backup: vaultName/vaultLocation
PARAMETERIZED_GUID_2 = "ac34a73f-9fa5-4067-9247-a3ecae514468"  # Compute: sourceRegion/targetRegion
# A valid, includable, non-parameterized built-in (kept).
VALID_GUID = "18adea5e-f416-4d0f-8aa8-d24321e3e274"  # SQL, all params defaulted


def _mapping(control_id: str, policy_ids: list[str]) -> ControlMapping:
    return ControlMapping(
        external_control_id=control_id,
        external_control_name=f"Control {control_id}",
        confidence_score=0.9,
        reasoning="Relevant control",
        azure_policy_ids=policy_ids,
        mapping_type="exact",
    )


# ── catalog classification ───────────────────────────────────────────────────

def test_catalog_flags_known_parameterized_guid():
    catalog = get_policy_catalog_service()
    assert catalog.requires_parameters(PARAMETERIZED_GUID) is True
    assert catalog.requires_parameters(PARAMETERIZED_GUID_2) is True


def test_catalog_does_not_flag_non_parameterized_or_unknown_guid():
    catalog = get_policy_catalog_service()
    assert catalog.requires_parameters(VALID_GUID) is False
    assert catalog.requires_parameters("not-a-real-guid") is False


def test_catalog_search_still_returns_parameterized_builtins():
    # Unlike System Policy, parameterized built-ins remain in retrieval so
    # mapping coverage is preserved — they are only stripped at generation.
    catalog = get_policy_catalog_service()
    entry = catalog.get(PARAMETERIZED_GUID)
    assert entry is not None
    assert entry.get("requires_parameters") is True


# ── generation stripping ─────────────────────────────────────────────────────

def test_generation_strips_parameterized_builtin():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="UAE National Cloud Security Policy",
        mappings=[
            _mapping("2.3.2.1", [VALID_GUID]),
            _mapping("2.7.1.3", [PARAMETERIZED_GUID]),
        ],
    )

    response = service.generate_initiative(request)

    emitted = [
        pd.policy_definition_id
        for pd in response.initiative.properties.policy_definitions
    ]
    assert f"/providers/Microsoft.Authorization/policyDefinitions/{VALID_GUID}" in emitted
    assert all(PARAMETERIZED_GUID not in pid for pid in emitted)
    assert response.included_policies == 1
    assert response.excluded_parameterized_policies == 1
    assert any("parameterized" in w.lower() for w in response.warnings)


def test_generation_deduplicates_parameterized_across_controls():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="Framework",
        mappings=[
            _mapping("CTRL-1", [PARAMETERIZED_GUID]),
            _mapping("CTRL-2", [PARAMETERIZED_GUID]),
        ],
    )

    response = service.generate_initiative(request)

    assert response.included_policies == 0
    assert response.excluded_parameterized_policies == 1


def test_generation_keeps_valid_and_strips_both_special_categories():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="Framework",
        mappings=[
            _mapping("CTRL-1", [VALID_GUID]),
            _mapping("CTRL-2", [PARAMETERIZED_GUID, PARAMETERIZED_GUID_2]),
        ],
    )

    response = service.generate_initiative(request)

    assert response.included_policies == 1
    assert response.excluded_parameterized_policies == 2


# ── opt-in include with operator-supplied values ─────────────────────────────

def test_generation_surfaces_parameter_requirements():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="Framework",
        mappings=[_mapping("CTRL-1", [PARAMETERIZED_GUID])],
    )

    response = service.generate_initiative(request)

    assert response.excluded_parameterized_policies == 1
    assert len(response.parameterized_requirements) == 1
    req = response.parameterized_requirements[0]
    assert req.policy_id == PARAMETERIZED_GUID
    assert req.control_ids == ["CTRL-1"]
    # Backup policy needs a vault name + location, both no-default.
    assert set(req.parameters) == {"vaultName", "vaultLocation"}
    assert req.parameters["vaultName"].type == "String"


def test_generation_includes_parameterized_when_values_supplied():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="Framework",
        mappings=[_mapping("CTRL-1", [PARAMETERIZED_GUID])],
        policy_parameter_values={
            PARAMETERIZED_GUID: {
                "vaultName": "rsv-prod",
                "vaultLocation": "southafricanorth",
            }
        },
    )

    response = service.generate_initiative(request)

    assert response.included_policies == 1
    assert response.excluded_parameterized_policies == 0
    assert response.parameterized_requirements == []
    ref = response.initiative.properties.policy_definitions[0]
    assert PARAMETERIZED_GUID in ref.policy_definition_id
    # Literal values baked into the reference so the set definition is complete.
    assert ref.parameters == {
        "vaultName": {"value": "rsv-prod"},
        "vaultLocation": {"value": "southafricanorth"},
    }
    # And it survives to Azure JSON.
    azure = response.initiative.to_azure_json()
    emitted = azure["properties"]["policyDefinitions"][0]["parameters"]
    assert emitted["vaultName"] == {"value": "rsv-prod"}


def test_generation_excludes_when_values_partially_supplied():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="Framework",
        mappings=[_mapping("CTRL-1", [PARAMETERIZED_GUID])],
        policy_parameter_values={
            # vaultLocation left blank → not fully satisfied → still excluded.
            PARAMETERIZED_GUID: {"vaultName": "rsv-prod", "vaultLocation": "  "}
        },
    )

    response = service.generate_initiative(request)

    assert response.included_policies == 0
    assert response.excluded_parameterized_policies == 1
    assert len(response.parameterized_requirements) == 1
