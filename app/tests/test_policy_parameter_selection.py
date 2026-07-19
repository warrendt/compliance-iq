"""Unit tests for the opt-in parameterized built-in inclusion helper.

Exercises ``satisfied_parameter_values`` — the pure logic that decides which
excluded parameterized built-ins get re-included when the operator supplies
values on the Export/Deploy page. Inclusion is all-or-nothing per built-in so
the emitted initiative stays deployable (ARM rejects a set definition with a
required parameter left unsatisfied).

Run with: PYTHONPATH=app/backend:app/frontend
"""

from utils.policy_parameters import satisfied_parameter_values


_REQUIREMENTS = [
    {
        "policy_id": "vault-builtin",
        "display_name": "Configure backup on VMs",
        "control_ids": ["A.1"],
        "parameters": {
            "vaultName": {"type": "String", "description": "RSV name"},
            "vaultLocation": {"type": "String", "description": "RSV region"},
        },
    },
    {
        "policy_id": "geo-builtin",
        "display_name": "Geo-redundant replication",
        "control_ids": ["A.2"],
        "parameters": {
            "sourceRegion": {"type": "String"},
            "targetRegion": {"type": "String"},
        },
    },
]


def test_all_values_supplied_includes_builtin():
    raw = {
        "vault-builtin": {"vaultName": "rsv-prod", "vaultLocation": "eastus"},
        "geo-builtin": {"sourceRegion": "eastus", "targetRegion": "westus"},
    }
    result = satisfied_parameter_values(_REQUIREMENTS, raw)
    assert result == {
        "vault-builtin": {"vaultName": "rsv-prod", "vaultLocation": "eastus"},
        "geo-builtin": {"sourceRegion": "eastus", "targetRegion": "westus"},
    }


def test_partial_values_excludes_that_builtin():
    raw = {
        "vault-builtin": {"vaultName": "rsv-prod", "vaultLocation": ""},
        "geo-builtin": {"sourceRegion": "eastus", "targetRegion": "westus"},
    }
    result = satisfied_parameter_values(_REQUIREMENTS, raw)
    # vault-builtin dropped (blank location); geo-builtin kept.
    assert "vault-builtin" not in result
    assert result == {"geo-builtin": {"sourceRegion": "eastus", "targetRegion": "westus"}}


def test_whitespace_only_value_is_treated_as_blank():
    raw = {
        "vault-builtin": {"vaultName": "   ", "vaultLocation": "eastus"},
    }
    result = satisfied_parameter_values(_REQUIREMENTS, raw)
    assert result == {}


def test_missing_policy_id_entry_is_excluded():
    # No raw values at all for either built-in.
    result = satisfied_parameter_values(_REQUIREMENTS, {})
    assert result == {}


def test_empty_requirements_returns_empty():
    assert satisfied_parameter_values([], {"x": {"y": "z"}}) == {}


def test_requirement_without_parameters_is_skipped():
    reqs = [{"policy_id": "no-params", "parameters": {}}]
    assert satisfied_parameter_values(reqs, {"no-params": {}}) == {}


def test_requirement_without_policy_id_is_skipped():
    reqs = [{"parameters": {"vaultName": {"type": "String"}}}]
    assert satisfied_parameter_values(reqs, {"": {"vaultName": "x"}}) == {}


def test_non_string_values_are_accepted_when_truthy():
    reqs = [{"policy_id": "num", "parameters": {"count": {"type": "Integer"}}}]
    raw = {"num": {"count": 3}}
    assert satisfied_parameter_values(reqs, raw) == {"num": {"count": 3}}


def test_zero_string_value_is_kept_as_non_blank():
    # "0" is a legitimate supplied value; only blank/whitespace should exclude.
    reqs = [{"policy_id": "num", "parameters": {"count": {"type": "String"}}}]
    raw = {"num": {"count": "0"}}
    assert satisfied_parameter_values(reqs, raw) == {"num": {"count": "0"}}
