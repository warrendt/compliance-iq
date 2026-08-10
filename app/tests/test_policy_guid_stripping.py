"""Tests that invalid (non-GUID) Azure Policy definition IDs are stripped at
generation time so the emitted initiative is deployable by ARM.

Regression for the observed ARM 400 ``PolicyDefinitionNotFound`` where an
LLM-hallucinated document title (e.g. "Regulatory Compliance in initiative
definitions - Azure Policy") leaked into ``policyDefinitions``.
"""

import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.models import ControlMapping, PolicyGenerationRequest
from app.services.policy_service import (
    PolicyGenerationService,
    _is_valid_policy_guid,
)

VALID_GUID_1 = "18adea5e-f416-4d0f-8aa8-d24321e3e274"
VALID_GUID_2 = "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b"
INVALID_TITLE_1 = "Regulatory Compliance in initiative definitions - Azure Policy"
INVALID_TITLE_2 = "Get policy compliance data - Azure Policy"


def _mapping(control_id: str, policy_ids: list[str], confidence: float = 0.9) -> ControlMapping:
    return ControlMapping(
        external_control_id=control_id,
        external_control_name=f"Control {control_id}",
        confidence_score=confidence,
        reasoning="Relevant control",
        azure_policy_ids=policy_ids,
        mapping_type="exact",
    )


# ── _is_valid_policy_guid ─────────────────────────────────────────────────────

def test_is_valid_policy_guid_accepts_bare_guid():
    assert _is_valid_policy_guid(VALID_GUID_1) is True


def test_is_valid_policy_guid_accepts_full_resource_id():
    full = f"/providers/Microsoft.Authorization/policyDefinitions/{VALID_GUID_2}"
    assert _is_valid_policy_guid(full) is True


def test_is_valid_policy_guid_rejects_document_title():
    assert _is_valid_policy_guid(INVALID_TITLE_1) is False


def test_is_valid_policy_guid_rejects_empty():
    assert _is_valid_policy_guid("") is False
    assert _is_valid_policy_guid("   ") is False


def test_is_valid_policy_guid_rejects_truncated_guid():
    assert _is_valid_policy_guid("18adea5e-f416-4d0f-8aa8") is False


# ── generate_initiative ───────────────────────────────────────────────────────

def test_generation_strips_invalid_and_keeps_valid():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="UAE National Cloud Security Policy",
        mappings=[
            _mapping("2.3.2.1", [VALID_GUID_1]),
            _mapping("2.7.1.3", [VALID_GUID_2]),
            _mapping("CTRL-007", [INVALID_TITLE_1, INVALID_TITLE_2]),
        ],
    )

    response = service.generate_initiative(request)

    emitted = [
        pd.policy_definition_id
        for pd in response.initiative.properties.policy_definitions
    ]
    assert f"/providers/Microsoft.Authorization/policyDefinitions/{VALID_GUID_1}" in emitted
    assert f"/providers/Microsoft.Authorization/policyDefinitions/{VALID_GUID_2}" in emitted
    # Neither hallucinated title should survive
    assert all("Azure Policy" not in pid for pid in emitted)
    assert response.included_policies == 2
    assert response.invalid_policies == 2


def test_generation_reports_invalid_ids_in_warnings():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="Framework",
        mappings=[_mapping("CTRL-007", [INVALID_TITLE_1])],
    )

    response = service.generate_initiative(request)

    assert response.invalid_policies == 1
    assert response.included_policies == 0
    assert any(
        "policy definition id(s) dropped" in w.lower() for w in response.warnings
    )
    assert any(INVALID_TITLE_1 in w for w in response.warnings)


def test_generation_all_valid_reports_zero_invalid():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="Framework",
        mappings=[_mapping("2.3.2.1", [VALID_GUID_1])],
    )

    response = service.generate_initiative(request)

    assert response.invalid_policies == 0
    assert response.included_policies == 1
    assert not any("invalid policy definition" in w.lower() for w in response.warnings)


def test_generation_deduplicates_invalid_across_controls():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="Framework",
        mappings=[
            _mapping("CTRL-007", [INVALID_TITLE_1]),
            _mapping("CTRL-008", [INVALID_TITLE_1]),
        ],
    )

    response = service.generate_initiative(request)

    # Same invalid id seen twice must be counted once
    assert response.invalid_policies == 1
    assert response.included_policies == 0


# ── pipeline initiative_builder._build_policies ───────────────────────────────

def test_pipeline_build_policies_strips_invalid_guids():
    from app.pipeline.initiative_builder import _build_policies
    from app.pipeline.models import AzurePolicyMapping, ControlPolicyMapping

    def _pipeline_mapping(control_id: str, policy_ids: list[str]) -> ControlPolicyMapping:
        return ControlPolicyMapping(
            control_id=control_id,
            control_title=f"Control {control_id}",
            domain="Identity",
            confidence_score=0.9,
            mapping_rationale="Relevant",
            azure_policies=[
                AzurePolicyMapping(
                    policy_definition_id=pid,
                    policy_name="p",
                    policy_description="d",
                    relevance="high",
                )
                for pid in policy_ids
            ],
            is_automatable=True,
        )

    policy_refs = _build_policies([
        _pipeline_mapping("2.3.2.1", [VALID_GUID_1]),
        _pipeline_mapping("CTRL-007", [INVALID_TITLE_1]),
    ])

    ids = [p["PolicyDefinitionId"] for p in policy_refs]
    assert f"/providers/Microsoft.Authorization/policyDefinitions/{VALID_GUID_1}" in ids
    assert all("Azure Policy" not in pid for pid in ids)
    assert len(policy_refs) == 1

