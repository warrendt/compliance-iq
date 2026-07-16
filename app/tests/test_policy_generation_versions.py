"""Regression tests for automatic Version History entries from policy generation."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
import os

import pytest
from starlette.requests import Request

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

import app.api.routes.policy as policy
from app.auth.azure_ad_auth import User
from app.models import ControlMapping, PolicyGenerationRequest
from app.models.sovereignty import SovereigntyMapping


def _request() -> Request:
    return Request({"type": "http", "headers": []})


def _mapping(with_sovereignty: bool = False) -> ControlMapping:
    return ControlMapping(
        external_control_id="CTRL-1",
        external_control_name="Example control",
        mcsb_control_id="IM-1",
        mcsb_control_name="Protect identities",
        mcsb_domain="Identity",
        confidence_score=0.9,
        reasoning="Relevant control",
        azure_policy_ids=["policy-id"],
        mapping_type="exact",
        sovereignty=(
            SovereigntyMapping(
                sovereignty_level="L2",
                sovereignty_objectives=["SO-3"],
                slz_policy_names=["cmk-storage-account"],
            )
            if with_sovereignty
            else None
        ),
    )


def _user() -> User:
    return User(oid="user-1", email="user@example.com", name="User")


@pytest.mark.asyncio
async def test_mcsb_generation_creates_version_with_all_downloadable_files(monkeypatch):
    response = SimpleNamespace(
        included_policies=1,
        excluded_policies=0,
        initiative=SimpleNamespace(to_azure_json=lambda: {"properties": {}}),
        model_dump=lambda: {"total_controls": 1},
    )
    service = SimpleNamespace(
        generate_initiative=lambda request: response,
        export_as_bicep=lambda initiative, name: "resource initiative 'Microsoft.Authorization/policySetDefinitions@2023-04-01' = {}",
        generate_deployment_script=lambda initiative, name, enforce_mode: {
            "powershell": "New-AzPolicySetDefinition",
            "cli": "az policy set-definition create",
        },
        generate_security_standard=lambda initiative, name: {
            "standard_name": "00000000-0000-0000-0000-000000000000",
            "arm_template": "{}",
            "powershell": "Invoke-AzRestMethod",
        },
    )
    create_version = AsyncMock(
        return_value={"id": "version-1", "version_number": 1, "semantic_version": "1.0.0"}
    )

    monkeypatch.setattr(policy, "get_policy_service", lambda: service)
    monkeypatch.setattr(policy.version_service, "create_version", create_version)
    monkeypatch.setattr(policy, "_persist_artifact", AsyncMock(return_value="artifact-1"))

    result = await policy.generate_policy_initiative(
        PolicyGenerationRequest(framework_name="Example Framework", mappings=[_mapping()]),
        _request(),
        _user(),
    )

    assert result["version_id"] == "version-1"
    assert result["version_number"] == 1
    assert result["semantic_version"] == "1.0.0"
    create_version.assert_awaited_once()
    kwargs = create_version.await_args.kwargs
    assert kwargs["user_id"] == "user@example.com"
    assert kwargs["metadata"]["source"] == "mcsb_initiative"
    assert {file["name"] for file in kwargs["artifact_payload"]["files"]} == {
        "Example_Framework_initiative.json",
        "Example_Framework_initiative.bicep",
        "Deploy-Example_FrameworkInitiative.ps1",
        "deploy-Example_Framework-initiative.sh",
        "Example_Framework_mappings.json",
        "Example_Framework_defender_standard.json",
        "Deploy-Example_FrameworkDefenderStandard.ps1",
    }


@pytest.mark.asyncio
async def test_slz_generation_creates_version_with_every_archetype_file(monkeypatch):
    generated_archetypes = {
        "archetype_artifacts": {
            "sovereign_root": {
                "initiative_json": {"properties": {}},
                "bicep_template": "targetScope = 'managementGroup'",
                "deployment_scripts": {
                    "cli": "az deployment mg create",
                    "powershell": "New-AzManagementGroupDeployment",
                },
            }
        }
    }
    service = SimpleNamespace(
        generate_slz_initiatives=lambda mappings, framework_name, allowed_locations: generated_archetypes
    )
    create_version = AsyncMock(
        return_value={"id": "version-2", "version_number": 2, "semantic_version": "1.0.0"}
    )

    monkeypatch.setattr(policy, "get_policy_service", lambda: service)
    monkeypatch.setattr(policy.version_service, "create_version", create_version)
    monkeypatch.setattr(policy, "_persist_artifact", AsyncMock(return_value="artifact-2"))

    result = await policy.generate_slz_initiatives(
        policy.SLZGenerationRequest(
            framework_name="Example Framework",
            mappings=[_mapping(with_sovereignty=True)],
            allowed_locations=["southafricanorth"],
        ),
        _request(),
        _user(),
    )

    assert result["version_id"] == "version-2"
    assert result["version_number"] == 2
    assert result["semantic_version"] == "1.0.0"
    create_version.assert_awaited_once()
    kwargs = create_version.await_args.kwargs
    assert kwargs["user_id"] == "user@example.com"
    assert kwargs["metadata"]["source"] == "slz_initiative"
    assert {file["name"] for file in kwargs["artifact_payload"]["files"]} == {
        "slz_sovereign_root_initiative.json",
        "slz_sovereign_root_initiative.bicep",
        "deploy_slz_sovereign_root.sh",
        "Deploy-slz_sovereign_root.ps1",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint_name", "expected_key"),
    [
        ("generate_policy_json", "body"),
        ("generate_policy_bicep", "body"),
        ("generate_deployment_scripts", "version_number"),
    ],
)
async def test_legacy_policy_exports_use_versioned_generation(
    monkeypatch, endpoint_name, expected_key
):
    versioned_result = {
        "initiative_id": "example-framework-compliance",
        "initiative_json": {"properties": {}},
        "bicep_template": "resource initiative 'Microsoft.Authorization/policySetDefinitions@2023-04-01' = {}",
        "powershell_script": "New-AzPolicySetDefinition",
        "cli_script": "az policy set-definition create",
        "version_id": "version-3",
        "version_number": 3,
    }
    generated = AsyncMock(return_value=versioned_result)
    monkeypatch.setattr(policy, "generate_policy_initiative", generated)

    endpoint = getattr(policy, endpoint_name)
    response = await endpoint(
        PolicyGenerationRequest(framework_name="Example Framework", mappings=[_mapping()]),
        _request(),
        _user(),
    )

    generated.assert_awaited_once()
    if expected_key == "body":
        assert response.body
    else:
        assert response[expected_key] == 3
