"""Tests that generated initiatives use UNIQUE policyDefinitionReferenceIds.

Azure rejects a policy set definition whose ``policyDefinitionReferenceId``
values are not unique. Before the fix every reference reused the bare external
control id, so a control mapped to several policies (or several controls) all
collided on the same reference id and ``az policy set-definition create`` failed.
"""

import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.models import ControlMapping, PolicyGenerationRequest
from app.services.policy_service import PolicyGenerationService, _sanitize_ref_id

G1 = "11111111-1111-1111-1111-111111111111"
G2 = "22222222-2222-2222-2222-222222222222"
G3 = "33333333-3333-3333-3333-333333333333"
G4 = "44444444-4444-4444-4444-444444444444"


def _mapping(control_id, policy_ids, confidence=0.9):
    return ControlMapping(
        external_control_id=control_id,
        external_control_name=f"Control {control_id}",
        mcsb_control_id="IM-1",
        mcsb_control_name="Protect identities",
        mcsb_domain="Identity",
        confidence_score=confidence,
        reasoning="Relevant control",
        azure_policy_ids=policy_ids,
        mapping_type="exact",
    )


def _generate(mappings):
    return PolicyGenerationService().generate_initiative(
        PolicyGenerationRequest(
            framework_name="Test",
            framework_version="1.0",
            mappings=mappings,
            min_confidence_threshold=0.6,
            include_all_policies=False,
        )
    )


def _ref_ids(resp):
    return [d.policy_definition_reference_id for d in resp.initiative.properties.policy_definitions]


def test_single_control_multiple_policies_get_unique_ref_ids():
    resp = _generate([_mapping("AC-1", [G1, G2, G3])])
    ref_ids = _ref_ids(resp)
    assert len(ref_ids) == 3
    assert len(set(ref_ids)) == 3, f"reference ids must be unique, got {ref_ids}"
    assert ref_ids[0] == "AC-1"  # first keeps the readable base id


def test_multiple_controls_unique_ref_ids():
    resp = _generate([_mapping("AC-1", [G1, G2]), _mapping("SC-1", [G3, G4])])
    ref_ids = _ref_ids(resp)
    assert len(ref_ids) == 4
    assert len(set(ref_ids)) == 4


def test_duplicate_policy_guid_across_controls_deduped():
    # G1 shared by both controls -> included once (dedup by policy id).
    resp = _generate([_mapping("AC-1", [G1, G2]), _mapping("SC-1", [G1, G3])])
    defs = resp.initiative.properties.policy_definitions
    guids = [d.policy_definition_id.rsplit("/", 1)[-1] for d in defs]
    assert guids.count(G1) == 1
    assert len(set(_ref_ids(resp))) == len(_ref_ids(resp))


def test_ref_ids_valid_after_sanitizing_control_id():
    resp = _generate([_mapping("A.C 1/2", [G1, G2])])
    ref_ids = _ref_ids(resp)
    assert all(all(ch.isalnum() or ch in "._-" for ch in r) for r in ref_ids)
    assert len(set(ref_ids)) == len(ref_ids)


def test_sanitize_ref_id():
    assert _sanitize_ref_id("AC-1") == "AC-1"
    assert _sanitize_ref_id("A.C 1/2") == "A.C_1_2"
    assert _sanitize_ref_id("   ") == "control"
    assert _sanitize_ref_id("") == "control"
