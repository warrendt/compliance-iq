"""Unit tests for the offline policy-catalog generator's pure logic."""

import importlib.util
import os
from pathlib import Path

_GEN = Path(__file__).resolve().parents[2] / "scripts" / "generate_policy_catalog.py"
_spec = importlib.util.spec_from_file_location("generate_policy_catalog", _GEN)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def test_normalize_drops_deprecated_by_display_name():
    out = gen.normalize(
        [
            {"name": "g1", "display_name": "[Deprecated]: Old policy"},
            {"name": "g2", "display_name": "Active policy"},
        ]
    )
    assert [d["name"] for d in out] == ["g2"]


def test_normalize_drops_deprecated_by_version():
    out = gen.normalize(
        [
            {"name": "g1", "display_name": "Some policy", "version": "1.0.0-deprecated"},
            {"name": "g2", "display_name": "Kept policy", "version": "2.0.0"},
        ]
    )
    assert [d["name"] for d in out] == ["g2"]


def test_normalize_dedupes_by_name_and_sorts():
    out = gen.normalize(
        [
            {"name": "b", "display_name": "B"},
            {"name": "a", "display_name": "A"},
            {"name": "a", "display_name": "A duplicate"},
        ]
    )
    assert [d["name"] for d in out] == ["a", "b"]  # deduped + sorted


def test_normalize_requires_name_and_display():
    out = gen.normalize(
        [
            {"name": "", "display_name": "no name"},
            {"name": "g1", "display_name": ""},
            {"name": "g2", "display_name": "ok"},
        ]
    )
    assert [d["name"] for d in out] == ["g2"]


def test_normalize_projects_lean_schema_with_defaults():
    out = gen.normalize([{"name": "g1", "displayName": "Camel case display"}])
    assert out[0] == {
        "name": "g1",
        "display_name": "Camel case display",
        "description": "",
        "category": "Uncategorized",
        "mode": "All",
        "effect": "",
        "requires_parameters": False,
        "required_parameters": {},
    }


def test_extract_effect_literal():
    out = gen.normalize(
        [
            {
                "name": "g1",
                "display_name": "Denies something",
                "policyRule": {"if": {}, "then": {"effect": "Deny"}},
            }
        ]
    )
    assert out[0]["effect"] == "Deny"


def test_extract_effect_resolves_parameter_reference_default():
    out = gen.normalize(
        [
            {
                "name": "g1",
                "display_name": "Audits by default",
                "parameters": {
                    "effect": {
                        "type": "String",
                        "defaultValue": "AuditIfNotExists",
                        "allowedValues": ["AuditIfNotExists", "Disabled"],
                    }
                },
                "policyRule": {"if": {}, "then": {"effect": "[parameters('effect')]"}},
            }
        ]
    )
    assert out[0]["effect"] == "AuditIfNotExists"


def test_extract_effect_manual_placeholder():
    out = gen.normalize(
        [
            {
                "name": "g1",
                "display_name": "Manual attestation control",
                "policyRule": {"if": {}, "then": {"effect": "Manual"}},
            }
        ]
    )
    assert out[0]["effect"] == "Manual"


def test_extract_effect_empty_when_parameterized_without_default():
    out = gen.normalize(
        [
            {
                "name": "g1",
                "display_name": "No resolvable default",
                "parameters": {"effect": {"type": "String"}},
                "policyRule": {"if": {}, "then": {"effect": "[parameters('effect')]"}},
            }
        ]
    )
    assert out[0]["effect"] == ""


def test_extract_effect_empty_when_no_policy_rule():
    out = gen.normalize([{"name": "g1", "display_name": "Ruleless"}])
    assert out[0]["effect"] == ""


def test_build_catalog_header():
    cat = gen.build_catalog(
        [{"name": "g1", "display_name": "Policy one"}], source="test"
    )
    assert cat["count"] == 1
    assert cat["source"] == "test"
    assert cat["definitions"][0]["name"] == "g1"
    assert "generated_at" in cat and "api_version" in cat


def test_requires_parameters_true_when_param_lacks_default():
    out = gen.normalize(
        [
            {
                "name": "g1",
                "display_name": "Needs a vault name",
                "parameters": {
                    "vaultName": {"type": "String"},
                    "effect": {"type": "String", "defaultValue": "AuditIfNotExists"},
                },
            }
        ]
    )
    assert out[0]["requires_parameters"] is True


def test_requires_parameters_false_when_all_params_have_defaults():
    out = gen.normalize(
        [
            {
                "name": "g1",
                "display_name": "All defaulted",
                "parameters": {
                    "effect": {"type": "String", "defaultValue": "Audit"},
                },
            }
        ]
    )
    assert out[0]["requires_parameters"] is False


def test_requires_parameters_false_when_no_parameters():
    out = gen.normalize([{"name": "g1", "display_name": "Parameterless"}])
    assert out[0]["requires_parameters"] is False


def test_required_parameters_schema_captured_for_no_default_params():
    out = gen.normalize(
        [
            {
                "name": "g1",
                "display_name": "Needs a vault name",
                "parameters": {
                    "vaultName": {
                        "type": "String",
                        "metadata": {"description": "Recovery Services vault name"},
                    },
                    "vaultLocation": {
                        "type": "String",
                        "allowedValues": ["southafricanorth", "westeurope"],
                    },
                    "effect": {"type": "String", "defaultValue": "AuditIfNotExists"},
                },
            }
        ]
    )
    req = out[0]["required_parameters"]
    # Only the no-default params are captured; 'effect' (defaulted) is omitted.
    assert set(req) == {"vaultName", "vaultLocation"}
    assert req["vaultName"]["type"] == "String"
    assert req["vaultName"]["description"] == "Recovery Services vault name"
    assert req["vaultLocation"]["allowed_values"] == ["southafricanorth", "westeurope"]


def test_raw_arm_shape_is_read_the_same_as_the_az_projected_shape():
    """The two --source paths once produced different corpora, silently.

    `az policy definition list` flattens metadata and filters built-ins
    server-side; a raw ARM dump does neither. Before _field(), a --raw
    regeneration emitted every definition with category "Uncategorized",
    disabling category boosting with no error and no failing test. This pins
    both shapes to the same output.
    """
    az_shape = {
        "name": "g1",
        "display_name": "Storage accounts should restrict network access",
        "description": "Network access should be restricted.",
        "category": "Storage",
        "policy_type": "BuiltIn",
    }
    raw_shape = {
        "name": "g1",
        "properties": {
            "displayName": "Storage accounts should restrict network access",
            "description": "Network access should be restricted.",
            "policyType": "BuiltIn",
            "metadata": {"category": "Storage"},
        },
    }
    az_out = gen.normalize([az_shape])
    raw_out = gen.normalize([raw_shape])
    assert len(az_out) == 1 and len(raw_out) == 1
    for key in ("name", "display_name", "category"):
        assert az_out[0][key] == raw_out[0][key], key


def test_normalize_drops_non_builtin_definitions():
    """The az path filters these server-side; the raw path must filter them here."""
    out = gen.normalize(
        [
            {"name": "b", "display_name": "Built-in one", "policy_type": "BuiltIn"},
            {"name": "c", "display_name": "Custom one", "policy_type": "Custom"},
            {
                "name": "s",
                "properties": {
                    "displayName": "Static one",
                    "policyType": "Static",
                },
            },
        ]
    )
    assert [d["name"] for d in out] == ["b"]


def test_missing_category_falls_back_rather_than_raising():
    out = gen.normalize([{"name": "g1", "display_name": "No category policy"}])
    assert len(out) == 1
    assert out[0]["category"]


def test_allowed_effects_captured_from_parameter_allowed_values():
    """A policy defaulting to Audit but permitting Deny can be escalated.

    Recording only the resolved default understates what the definition can do.
    """
    out = gen.normalize(
        [
            {
                "name": "g1",
                "display_name": "Parameterised policy",
                "policy_type": "BuiltIn",
                "parameters": {
                    "effect": {
                        "type": "String",
                        "allowedValues": ["Audit", "Deny", "Disabled"],
                        "defaultValue": "Audit",
                    }
                },
                "policy_rule": {"then": {"effect": "[parameters('effect')]"}},
            }
        ]
    )
    assert out[0]["effect"] == "Audit"
    assert out[0]["allowed_effects"] == ["Audit", "Deny", "Disabled"]


def test_allowed_effects_absent_for_hardcoded_effects():
    out = gen.normalize(
        [
            {
                "name": "g1",
                "display_name": "Fixed policy",
                "policy_type": "BuiltIn",
                "policy_rule": {"then": {"effect": "Deny"}},
            }
        ]
    )
    assert out[0]["effect"] == "Deny"
    assert not out[0].get("allowed_effects")


def test_empty_output_is_not_silently_accepted_from_a_shape_mismatch():
    """The regression that motivated _unwrap: every record dropped, exit 0.

    A REST-shaped dump must yield definitions, not an empty catalog.
    """
    rest_dump = [
        {
            "id": "/providers/Microsoft.Authorization/policyDefinitions/g1",
            "name": "g1",
            "properties": {
                "displayName": "A real policy",
                "policyType": "BuiltIn",
                "metadata": {"category": "Storage", "version": "1.0.0"},
                "policyRule": {"then": {"effect": "Deny"}},
            },
        }
    ]
    out = gen.normalize(rest_dump)
    assert len(out) == 1
    assert out[0]["name"] == "g1"
    assert out[0]["category"] == "Storage"
    assert out[0]["effect"] == "Deny"


def test_unwrap_does_not_let_properties_shadow_the_guid():
    """ARM keeps `name` outside `properties`; a stray inner name must not win."""
    out = gen.normalize(
        [
            {
                "name": "outer-guid",
                "properties": {
                    "name": "inner-wrong",
                    "displayName": "P",
                    "policyType": "BuiltIn",
                },
            }
        ]
    )
    assert out[0]["name"] == "outer-guid"


def test_nested_non_builtin_definitions_are_dropped():
    out = gen.normalize(
        [
            {"name": "c", "properties": {"displayName": "Custom", "policyType": "Custom"}},
            {"name": "b", "properties": {"displayName": "Built", "policyType": "BuiltIn"}},
        ]
    )
    assert [d["name"] for d in out] == ["b"]
