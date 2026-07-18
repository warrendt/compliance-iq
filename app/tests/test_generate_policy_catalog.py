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
    }


def test_build_catalog_header():
    cat = gen.build_catalog(
        [{"name": "g1", "display_name": "Policy one"}], source="test"
    )
    assert cat["count"] == 1
    assert cat["source"] == "test"
    assert cat["definitions"][0]["name"] == "g1"
    assert "generated_at" in cat and "api_version" in cat
