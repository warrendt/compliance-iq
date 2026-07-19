"""Tests for the policy-assignment request body builder.

An assignment of any initiative that contains ``DeployIfNotExists``/``Modify``
policies is rejected by ARM (HTTP 400) unless it carries a managed identity and
a ``location`` — even under ``DoNotEnforce``. ``_build_assignment_body`` always
attaches a system-assigned identity + location so those initiatives assign
cleanly, and drives audit-only vs enforced via ``enforcementMode``.
"""

from app.services.policy_deploy_service import _build_assignment_body

_DEF_ID = (
    "/subscriptions/0000/providers/Microsoft.Authorization"
    "/policySetDefinitions/my-initiative"
)


def test_audit_only_body_is_donotenforce_with_identity():
    body = _build_assignment_body(
        policy_set_definition_id=_DEF_ID,
        display_name="My Initiative",
        description="desc",
        enforce_mode=False,
        location="southafricanorth",
    )
    assert body["identity"] == {"type": "SystemAssigned"}
    assert body["location"] == "southafricanorth"
    props = body["properties"]
    assert props["policyDefinitionId"] == _DEF_ID
    assert props["displayName"] == "My Initiative"
    assert props["description"] == "desc"
    # Audit-only: effects are never applied, compliance is still assessed.
    assert props["enforcementMode"] == "DoNotEnforce"


def test_enforce_mode_body_is_default():
    body = _build_assignment_body(
        policy_set_definition_id=_DEF_ID,
        display_name="My Initiative",
        enforce_mode=True,
    )
    assert body["properties"]["enforcementMode"] == "Default"
    # Identity is attached regardless of enforcement mode (DINE/Modify support).
    assert body["identity"] == {"type": "SystemAssigned"}


def test_defaults_are_audit_only():
    body = _build_assignment_body(
        policy_set_definition_id=_DEF_ID,
        display_name="X",
    )
    assert body["properties"]["enforcementMode"] == "DoNotEnforce"
    assert body["location"] == "eastus"
    assert body["properties"]["description"] == ""
