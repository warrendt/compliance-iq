"""Tests for the Defender for Cloud custom compliance standard generator.

A plain policy set definition shows in Defender for Cloud as *Custom (legacy)*.
To surface as a first-class Compliance standard it must be wrapped in a
``Microsoft.Security/securityStandards`` resource whose ``policySetDefinitionId``
links the initiative. These tests assert the generated artifacts have that shape.
"""

import json
import os
import uuid

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.models import ControlMapping, PolicyGenerationRequest
from app.services.policy_service import PolicyGenerationService

G1 = "11111111-1111-1111-1111-111111111111"


def _initiative():
    svc = PolicyGenerationService()
    resp = svc.generate_initiative(
        PolicyGenerationRequest(
            framework_name="Test Framework",
            framework_version="1.0",
            mappings=[
                ControlMapping(
                    external_control_id="AC-1",
                    external_control_name="Access control",
                    confidence_score=0.9,
                    reasoning="Relevant",
                    azure_policy_ids=[G1],
                    mapping_type="exact",
                )
            ],
            min_confidence_threshold=0.6,
            include_all_policies=False,
        )
    )
    return svc, resp.initiative


def test_arm_template_shape():
    svc, initiative = _initiative()
    standard = svc.generate_security_standard(initiative, "test_framework")

    template = json.loads(standard["arm_template"])
    res = template["resources"][0]
    assert res["type"] == "Microsoft.Security/securityStandards"
    assert res["apiVersion"] == "2024-08-01"
    assert res["properties"]["cloudProviders"] == ["Azure"]
    assert "policySetDefinitionId" in res["properties"]
    # standard name must be a valid GUID
    uuid.UUID(standard["standard_name"])


def test_powershell_links_initiative():
    svc, initiative = _initiative()
    standard = svc.generate_security_standard(initiative, "test_framework")

    ps = standard["powershell"]
    assert "Invoke-AzRestMethod" in ps
    assert "Microsoft.Security/securityStandards" in ps
    assert "2024-08-01" in ps
    assert "policySetDefinitionId" in ps
    assert "Defender CSPM" in ps  # documents the prerequisite


def test_standard_name_can_be_supplied():
    svc, initiative = _initiative()
    fixed = str(uuid.uuid4())
    standard = svc.generate_security_standard(
        initiative, "test_framework", standard_name=fixed
    )
    assert standard["standard_name"] == fixed
    assert fixed in standard["powershell"]


def test_initiative_json_carries_asc_onboarding_flag():
    """The initiative metadata must carry ``"ASC":"true"`` so Defender for Cloud
    onboards it to Regulatory compliance (controls surface 24-48h later)."""
    _svc, initiative = _initiative()
    azure_json = initiative.to_azure_json()
    assert azure_json["properties"]["metadata"]["ASC"] == "true"


def test_export_paths_carry_asc_flag():
    """bicep, CLI (bash) and PowerShell deploy scripts must all set ASC=true on
    the initiative metadata — otherwise the initiative shows as *Custom (legacy)*
    and never surfaces under Regulatory compliance."""
    svc, initiative = _initiative()

    bicep = svc.export_as_bicep(initiative, "test_framework")
    assert "ASC: 'true'" in bicep

    scripts = svc.generate_deployment_script(initiative, "test_framework")
    assert '"ASC":"true"' in scripts["cli"]
    assert 'ASC="true"' in scripts["powershell"]
