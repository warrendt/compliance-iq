"""Tests for Regulatory-Compliance style grouping of generated initiatives.

Built-in Azure regulatory-compliance initiatives group their policy references
under ``policyDefinitionGroups`` (one group per source control) and tag each
reference with ``groupNames``. These tests assert the exporter now emits that
structure so the generated initiative renders grouped like the built-ins.
"""

import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.models import ControlMapping, PolicyGenerationRequest
from app.services.policy_service import PolicyGenerationService

import pytest


@pytest.fixture(autouse=True)
def _accept_all_guids(monkeypatch):
    """Grouping is orthogonal to built-in existence; stub the catalog so every
    well-formed placeholder GUID is treated as a real, includable built-in."""

    class _AllCatalog:
        available = True

        def exists(self, name):
            return True

        def is_non_includable(self, name):
            return False

        def requires_parameters(self, name):
            return False

        def get(self, name):
            return None

        def get_required_parameters(self, name):
            return {}

    monkeypatch.setattr(
        "app.services.policy_service.get_policy_catalog_service",
        lambda: _AllCatalog(),
    )


G1 = "11111111-1111-1111-1111-111111111111"
G2 = "22222222-2222-2222-2222-222222222222"
G3 = "33333333-3333-3333-3333-333333333333"


def _mapping(control_id, policy_ids, name=None):
    return ControlMapping(
        external_control_id=control_id,
        external_control_name=name or f"Control {control_id}",
        confidence_score=0.9,
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


def test_azure_json_emits_groups_and_group_names():
    resp = _generate([_mapping("AC-1", [G1, G2])])
    props = resp.initiative.to_azure_json()["properties"]

    assert "policyDefinitionGroups" in props
    groups = props["policyDefinitionGroups"]
    assert len(groups) == 1
    assert groups[0]["name"]  # sanitized group name present

    for defn in props["policyDefinitions"]:
        assert defn["groupNames"], "each policy reference must carry groupNames"


def test_shared_policy_accumulates_group_names_across_controls():
    # G1 is shared by both controls -> single reference, two group names.
    resp = _generate(
        [_mapping("AC-1", [G1, G2]), _mapping("SC-1", [G1, G3])]
    )
    props = resp.initiative.to_azure_json()["properties"]

    # Two distinct groups (one per control).
    assert len(props["policyDefinitionGroups"]) == 2

    shared = [
        d
        for d in props["policyDefinitions"]
        if d["policyDefinitionId"].rsplit("/", 1)[-1] == G1
    ]
    assert len(shared) == 1, "shared GUID must be deduped to a single reference"
    assert len(shared[0]["groupNames"]) == 2, "shared policy belongs to both groups"


def test_deploy_scripts_pass_group_definitions():
    resp = _generate([_mapping("AC-1", [G1, G2])])
    scripts = PolicyGenerationService().generate_deployment_script(
        resp.initiative, "test", enforce_mode=False
    )
    assert "-GroupDefinition" in scripts["powershell"]
    assert "--definition-groups" in scripts["cli"]
