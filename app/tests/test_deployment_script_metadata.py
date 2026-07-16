"""Regression tests for generated PowerShell deployment scripts.

Az.Resources 10.x's Autorest-based ``New-AzPolicySetDefinition`` declares
``-Metadata <String>`` and rejects a raw hashtable with::

    Unrecognized metadata format - value: [System.Collections.Hashtable], type: [string]

The generator previously emitted ``-Metadata @{category="..."}`` (a hashtable),
so every generated deploy script failed at runtime. These tests assert the
PowerShell now passes metadata as a JSON string (built via
``ConvertTo-Json -Compress``) for both the MCSB/generic and the SLZ management
group generators.
"""

from types import SimpleNamespace

from app.services.policy_service import PolicyGenerationService


def _make_initiative():
    return SimpleNamespace(
        to_azure_json=lambda: {"properties": {"policyDefinitions": []}},
        properties=SimpleNamespace(
            display_name="UAE National Cloud Security Policy Compliance Initiative",
            description="AI-generated policy initiative",
            metadata=SimpleNamespace(category="Regulatory Compliance"),
        ),
    )


def test_mcsb_powershell_passes_metadata_as_json_string():
    ps = PolicyGenerationService().generate_deployment_script(
        initiative=_make_initiative(),
        initiative_name="uae-national-cloud-security-policy",
    )["powershell"]

    # Metadata must be a JSON string, not a raw hashtable.
    assert "-Metadata @{" not in ps
    assert "ConvertTo-Json -Compress" in ps
    assert "-Metadata $metadata" in ps
    # The category value is still carried through into the hashtable literal
    # that gets converted to JSON.
    assert 'category="Regulatory Compliance"' in ps


def test_slz_powershell_passes_metadata_as_json_string():
    scripts = PolicyGenerationService()._generate_slz_deployment_scripts(
        initiative_name="slz-sovereign-root",
        display_name="SLZ Sovereign Root",
        description="Sovereign landing zone initiative",
        archetype_name="Confidential Corp",
        initiative_json={"properties": {"policyDefinitions": []}},
    )
    ps = scripts["powershell"]

    assert "-Metadata @{" not in ps
    assert "ConvertTo-Json -Compress" in ps
    assert "-Metadata $metadata" in ps
