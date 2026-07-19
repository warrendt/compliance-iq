"""Tests that generated deployment scripts assign initiatives with a managed
identity + location and that the Azure CLI script reproduces the full deploy
chain (set-definition -> audit assignment -> Defender standard).

Regression for the observed deploy failure where an initiative containing
DeployIfNotExists / Modify policies (e.g. the UAE National Cloud Security
Policy) could not be assigned: Azure requires ``-IdentityType SystemAssigned
-Location`` on the assignment even under ``DoNotEnforce``. The CLI script also
previously created only the set-definition (no assignment, no Defender
standard) and passed metadata as ``category="Regulatory Compliance"`` — a
"key=value" shorthand that breaks on the space in the value.
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


def _scripts(location="southafricanorth"):
    return PolicyGenerationService().generate_deployment_script(
        initiative=_make_initiative(),
        initiative_name="uae-national-cloud-security-policy",
        location=location,
    )


# ── PowerShell assignment identity ───────────────────────────────────────────

def test_powershell_assignment_has_system_identity_and_location():
    ps = _scripts()["powershell"]
    assert "-IdentityType SystemAssigned" in ps
    assert "-Location $Location" in ps


def test_powershell_location_param_defaults_to_generator_location():
    ps = _scripts(location="southafricanorth")["powershell"]
    assert '[string]$Location = "southafricanorth"' in ps


# ── Azure CLI full deploy chain ──────────────────────────────────────────────

def test_cli_metadata_is_json_not_key_value_shorthand():
    # "key=value" shorthand breaks on the space in "Regulatory Compliance".
    cli = _scripts()["cli"]
    assert '--metadata category=' not in cli
    assert '--metadata \'{"category":"Regulatory Compliance"}\'' in cli


def test_cli_creates_audit_assignment_with_identity():
    cli = _scripts()["cli"]
    assert "az policy assignment create" in cli
    assert "--enforcement-mode DoNotEnforce" in cli
    assert "--mi-system-assigned" in cli
    assert '--location "$LOCATION"' in cli


def test_cli_registers_defender_security_standard():
    cli = _scripts()["cli"]
    assert "Microsoft.Security/securityStandards" in cli
    assert "api-version=2024-08-01" in cli
    assert "az rest --method put" in cli
    # assessments must be present ([] accepted; null returns HTTP 400)
    assert '"assessments": []' in cli
    assert '"policySetDefinitionId"' in cli


def test_cli_location_defaults_to_generator_location():
    cli = _scripts(location="southafricanorth")["cli"]
    assert 'LOCATION="${LOCATION:-southafricanorth}"' in cli
