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
