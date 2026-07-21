"""Unit tests for the ComplianceIQ skill client.

Run from the skill directory::

    cd .github/skills/complianceiq
    python -m pytest tests -q

Pure functions are tested directly; the HTTP/az layers are exercised with
monkeypatched stand-ins so no network or Azure login is required.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ciq  # noqa: E402
import ciq_core as core  # noqa: E402


# --------------------------------------------------------------------------- #
# api_url
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "base,path,expected",
    [
        ("https://f", "/health", "https://f/api/v1/health"),
        ("https://f/", "health", "https://f/api/v1/health"),
        ("https://f", "/api/v1/deploy/scopes", "https://f/api/v1/deploy/scopes"),
        ("https://f", "pipeline/status/abc", "https://f/api/v1/pipeline/status/abc"),
    ],
)
def test_api_url(base, path, expected):
    assert core.api_url(base, path) == expected


# --------------------------------------------------------------------------- #
# status helpers
# --------------------------------------------------------------------------- #

def test_terminal_and_success_status():
    assert core.is_terminal_status("completed")
    assert core.is_terminal_status("FAILED")
    assert core.is_terminal_status("cancelled")
    assert not core.is_terminal_status("mapping_policies")
    assert not core.is_terminal_status(None)
    assert core.is_success_status("completed")
    assert not core.is_success_status("failed")


def test_summarize_status_includes_error():
    s = {"status": "failed", "progress": 40, "stage": "map", "error": "boom"}
    out = core.summarize_status(s)
    assert "failed" in out and "40%" in out and "boom" in out


# --------------------------------------------------------------------------- #
# initiative helpers
# --------------------------------------------------------------------------- #

def test_default_initiative_name():
    assert core.default_initiative_name("SAMA Cyber Security") == "sama_cyber_security"
    assert core.default_initiative_name(None) == "compliance_framework"
    assert core.default_initiative_name("   ") == "compliance_framework"


def test_extract_initiative():
    payload = {"files": {"initiative": {"properties": {"displayName": "X"}}}}
    out = core.extract_initiative(payload)
    assert out["properties"]["displayName"] == "X"
    assert out["properties"]["policyType"] == "Custom"
    assert out["properties"]["metadata"]["ASC"] == "true"
    assert core.extract_initiative({"files": {}}) is None
    assert core.extract_initiative({}) is None


def test_normalize_initiative_pascalcase_to_camelcase():
    """The pipeline emits PascalCase policy defs; ARM needs camelCase."""
    pascal = {
        "properties": {
            "displayName": "Framework Controls",
            "description": "d",
            "metadata": {"frameworkName": "F"},
            "policyDefinitionGroups": [
                {"name": "G1", "displayName": "Group 1", "description": "gd"}
            ],
            "policyDefinitions": [
                {
                    "PolicyDefinitionReferenceId": "ref-1",
                    "PolicyDefinitionId": "/providers/Microsoft.Authorization/policyDefinitions/abc",
                    "Parameters": {},
                    "GroupNames": ["G1"],
                }
            ],
        }
    }
    out = core.normalize_initiative_for_deploy(pascal)
    props = out["properties"]
    assert props["policyType"] == "Custom"
    assert props["metadata"]["ASC"] == "true"
    assert props["metadata"]["category"] == "Regulatory Compliance"
    assert props["metadata"]["frameworkName"] == "F"  # preserved
    pd = props["policyDefinitions"][0]
    assert pd["policyDefinitionId"].endswith("/abc")
    assert pd["policyDefinitionReferenceId"] == "ref-1"
    assert pd["groupNames"] == ["G1"]
    assert pd["parameters"] == {}
    # No leftover PascalCase keys that ARM would ignore.
    assert not any(k[0].isupper() for k in pd)
    assert props["policyDefinitionGroups"][0]["name"] == "G1"


def test_normalize_initiative_is_idempotent_and_stamps_asc():
    camel = {
        "properties": {
            "displayName": "X",
            "policyDefinitions": [
                {
                    "policyDefinitionId": "/providers/Microsoft.Authorization/policyDefinitions/abc",
                    "policyDefinitionReferenceId": "r",
                    "parameters": {},
                    "groupNames": [],
                }
            ],
            "policyDefinitionGroups": [],
        }
    }
    once = core.normalize_initiative_for_deploy(camel)
    twice = core.normalize_initiative_for_deploy(once)
    assert once == twice
    assert once["properties"]["metadata"]["ASC"] == "true"
    assert once["properties"]["policyDefinitions"][0]["policyDefinitionReferenceId"] == "r"


def test_normalize_initiative_accepts_unwrapped_properties():
    """Some artifacts put the initiative body at the top level, not under
    ``properties``."""
    unwrapped = {
        "displayName": "Y",
        "policyDefinitions": [
            {"PolicyDefinitionId": "/x/abc", "PolicyDefinitionReferenceId": "r", "GroupNames": []}
        ],
        "policyDefinitionGroups": [],
    }
    out = core.normalize_initiative_for_deploy(unwrapped)
    assert out["properties"]["displayName"] == "Y"
    assert out["properties"]["policyDefinitions"][0]["policyDefinitionReferenceId"] == "r"


def test_normalize_clamps_description_and_groupnames_to_arm_limits():
    """A large report-grade initiative must be trimmed to ARM's hard limits
    (description <=512, <=16 groupNames per policy) or deploy 400s."""
    big = {
        "properties": {
            "displayName": "Big",
            "description": "x" * 900,
            "policyDefinitions": [
                {
                    "policyDefinitionId": "/x/abc",
                    "policyDefinitionReferenceId": "r1",
                    "groupNames": [f"g{i}" for i in range(19)],
                },
                {
                    "policyDefinitionId": "/x/def",
                    "policyDefinitionReferenceId": "r2",
                    "groupNames": ["g0", "g1"],
                },
            ],
            "policyDefinitionGroups": [],
        }
    }
    out = core.normalize_initiative_for_deploy(big)["properties"]
    assert len(out["description"]) == core.ARM_DESCRIPTION_MAX
    assert len(out["policyDefinitions"][0]["groupNames"]) == core.ARM_GROUPNAMES_MAX
    assert out["policyDefinitions"][0]["groupNames"] == [f"g{i}" for i in range(16)]
    # Under-limit policy is left untouched.
    assert out["policyDefinitions"][1]["groupNames"] == ["g0", "g1"]


def test_arm_safety_warnings_reports_clamps():
    big = {
        "properties": {
            "description": "x" * 900,
            "policyDefinitions": [
                {"policyDefinitionReferenceId": "r1", "groupNames": [f"g{i}" for i in range(19)]},
                {"policyDefinitionReferenceId": "r2", "groupNames": ["g0"]},
            ],
        }
    }
    warnings = core.arm_safety_warnings(big)
    assert any("description" in w for w in warnings)
    assert any("r1" in w and "3" in w for w in warnings)
    assert not any("r2" in w for w in warnings)


def test_arm_safety_warnings_empty_when_within_limits():
    ok = {
        "properties": {
            "description": "short",
            "policyDefinitions": [
                {"policyDefinitionReferenceId": "r1", "groupNames": ["g0", "g1"]},
            ],
        }
    }
    assert core.arm_safety_warnings(ok) == []


# --------------------------------------------------------------------------- #
# parameterized built-ins (required no-default params)
# --------------------------------------------------------------------------- #

def test_required_params_from_definition_ignores_defaulted():
    defn = {
        "parameters": {
            "effect": {"type": "String", "defaultValue": "Deny"},
            "listOfAllowedLocations": {
                "type": "Array",
                "metadata": {"description": "Allowed locations", "strongType": "location"},
            },
        }
    }
    required = core.required_params_from_definition(defn)
    assert list(required) == ["listOfAllowedLocations"]
    assert required["listOfAllowedLocations"]["type"] == "Array"
    assert required["listOfAllowedLocations"]["strongType"] == "location"


def _sample_initiative_with_param_builtin():
    return {
        "properties": {
            "policyDefinitions": [
                {"policyDefinitionId": "/providers/.../policyDefinitions/aaa",
                 "policyDefinitionReferenceId": "r-aaa", "parameters": {}},
                {"policyDefinitionId": "/providers/.../policyDefinitions/bbb",
                 "policyDefinitionReferenceId": "r-bbb", "parameters": {}},
            ]
        }
    }


def test_parameterized_references_flags_only_required():
    req = {"aaa": {"logAnalytics": {"type": "String"}}}
    refs = core.parameterized_references(_sample_initiative_with_param_builtin(), req)
    assert len(refs) == 1
    assert refs[0]["guid"] == "aaa"
    assert refs[0]["referenceId"] == "r-aaa"
    assert "logAnalytics" in refs[0]["required"]


def test_apply_parameter_resolutions_supplies_value():
    req = {"aaa": {"listOfAllowedLocations": {"type": "Array"}}}
    resolved, unresolved = core.apply_parameter_resolutions(
        _sample_initiative_with_param_builtin(),
        required_by_guid=req,
        values={"aaa": {"listOfAllowedLocations": "eastus, westus"}},
    )
    assert unresolved == []
    defs = resolved["properties"]["policyDefinitions"]
    aaa = next(d for d in defs if d["policyDefinitionReferenceId"] == "r-aaa")
    assert aaa["parameters"]["listOfAllowedLocations"] == {"value": ["eastus", "westus"]}
    assert len(defs) == 2  # bbb untouched, aaa kept


def test_apply_parameter_resolutions_excludes():
    req = {"aaa": {"logAnalytics": {"type": "String"}}}
    resolved, unresolved = core.apply_parameter_resolutions(
        _sample_initiative_with_param_builtin(),
        required_by_guid=req,
        exclude=["aaa"],
    )
    assert unresolved == []
    refs = [d["policyDefinitionReferenceId"] for d in resolved["properties"]["policyDefinitions"]]
    assert refs == ["r-bbb"]  # aaa dropped, bbb kept


def test_apply_parameter_resolutions_reports_unresolved():
    req = {"aaa": {"logAnalytics": {"type": "String"}}}
    resolved, unresolved = core.apply_parameter_resolutions(
        _sample_initiative_with_param_builtin(),
        required_by_guid=req,
    )
    assert len(unresolved) == 1
    assert unresolved[0]["guid"] == "aaa"
    assert unresolved[0]["missing"] == ["logAnalytics"]
    # unresolved ref is left OUT of the body (never silently deployed broken)
    refs = [d["policyDefinitionReferenceId"] for d in resolved["properties"]["policyDefinitions"]]
    assert refs == ["r-bbb"]


# --------------------------------------------------------------------------- #
# deploy/validate body builders
# --------------------------------------------------------------------------- #

def test_build_validate_body():
    b = core.build_validate_body("/subscriptions/s", "n", {"a": 1})
    assert b == {
        "scope": "/subscriptions/s",
        "initiative_name": "n",
        "initiative_body": {"a": 1},
        "check_references": True,
    }


def test_build_deploy_body_defaults_audit_only():
    b = core.build_deploy_body("/subscriptions/s", "n", {"x": 1})
    assert b["enforce_mode"] is False  # audit-only default
    assert b["assign"] is False
    assert b["location"] == "eastus"
    assert b["assignment_display_name"] == "n"


def test_build_deploy_body_enforce_and_assign():
    b = core.build_deploy_body(
        "/subscriptions/s", "n", {}, assign=True, enforce_mode=True, location="westeurope"
    )
    assert b["assign"] is True
    assert b["enforce_mode"] is True
    assert b["location"] == "westeurope"


# --------------------------------------------------------------------------- #
# scope helpers
# --------------------------------------------------------------------------- #

def test_is_valid_scope():
    assert core.is_valid_scope("/subscriptions/123")
    assert core.is_valid_scope("/providers/Microsoft.Management/managementGroups/mg")
    assert not core.is_valid_scope("subscriptions/123")
    assert not core.is_valid_scope("")


def test_parse_and_choose_scope():
    payload = {
        "scopes": [
            {"id": "sub1", "display": "Prod", "scope": "/subscriptions/sub1"},
            {"id": "sub2", "display": "Dev", "scope": "/subscriptions/sub2"},
        ]
    }
    scopes = core.parse_scopes(payload)
    assert len(scopes) == 2
    assert core.choose_scope(scopes, "Dev")["id"] == "sub2"
    assert core.choose_scope(scopes, "sub1")["display"] == "Prod"
    assert core.choose_scope(scopes, "nope") is None


# --------------------------------------------------------------------------- #
# multipart encoding
# --------------------------------------------------------------------------- #

def test_encode_multipart_roundtrip_shape():
    body, ctype = core.encode_multipart(
        {"min_confidence": "0.5"},
        "pdf_file",
        "reg.pdf",
        b"%PDF-1.4 fake",
        boundary="BOUND",
    )
    assert ctype == "multipart/form-data; boundary=BOUND"
    text = body.decode("latin-1")
    assert 'name="min_confidence"' in text
    assert 'name="pdf_file"; filename="reg.pdf"' in text
    assert "Content-Type: application/pdf" in text
    assert "%PDF-1.4 fake" in text
    assert text.strip().endswith("--BOUND--")


def test_auth_headers():
    assert core.auth_headers("t") == {"Authorization": "Bearer t"}
    assert core.auth_headers(None) == {}


# --------------------------------------------------------------------------- #
# CLI base-url resolution
# --------------------------------------------------------------------------- #

def test_resolve_base_url_prefers_flag(monkeypatch):
    monkeypatch.setenv("CIQ_BASE_URL", "https://env")
    ns = ciq.build_parser().parse_args(["health", "--base-url", "https://flag/"])
    assert ciq.resolve_base_url(ns) == "https://flag"


def test_resolve_base_url_env(monkeypatch):
    monkeypatch.setenv("CIQ_BASE_URL", "https://env/")
    ns = ciq.build_parser().parse_args(["health"])
    assert ciq.resolve_base_url(ns) == "https://env"


def test_resolve_base_url_via_az(monkeypatch):
    monkeypatch.delenv("CIQ_BASE_URL", raising=False)
    monkeypatch.setattr(ciq, "_az", lambda args: "fe.example.net")
    ns = ciq.build_parser().parse_args(
        ["health", "--frontend-app", "ca-fe", "--resource-group", "rg"]
    )
    assert ciq.resolve_base_url(ns) == "https://fe.example.net"


def test_resolve_base_url_errors(monkeypatch):
    monkeypatch.delenv("CIQ_BASE_URL", raising=False)
    monkeypatch.delenv("CIQ_FRONTEND_APP", raising=False)
    monkeypatch.delenv("CIQ_RESOURCE_GROUP", raising=False)
    ns = ciq.build_parser().parse_args(["health"])
    with pytest.raises(ciq.CiqError):
        ciq.resolve_base_url(ns)


# --------------------------------------------------------------------------- #
# CLI command wiring (HTTP mocked)
# --------------------------------------------------------------------------- #

def test_cmd_run_waits_until_complete(monkeypatch, tmp_path, capsys):
    pdf = tmp_path / "reg.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    calls = {"n": 0}

    def fake_request(method, url, token, **kw):
        if url.endswith("/pipeline/run"):
            return {"job_id": "job-123"}
        if "/pipeline/status/" in url:
            calls["n"] += 1
            if calls["n"] < 2:
                return {"status": "mapping_policies", "progress": 50}
            return {"status": "completed", "progress": 100}
        raise AssertionError(url)

    monkeypatch.setattr(ciq, "_request", fake_request)
    monkeypatch.setattr(ciq, "get_token", lambda: "tok")

    ns = ciq.build_parser().parse_args(
        ["run", "--base-url", "https://f", "--pdf", str(pdf), "--poll-interval", "0"]
    )
    rc = ciq.cmd_run(ns)
    assert rc == 0
    assert "completed" in capsys.readouterr().out


def test_cmd_deploy_builds_audit_only_body(monkeypatch, capsys):
    captured = {}

    def fake_post(base, path, token, body, **kw):
        captured["path"] = path
        captured["body"] = body
        return {"status": "deployed"}

    monkeypatch.setattr(ciq, "post_json", fake_post)
    monkeypatch.setattr(ciq, "get_token", lambda: "tok")
    monkeypatch.setattr(
        ciq,
        "get_json",
        lambda base, path, token, **kw: {"files": {"initiative": {"properties": {"displayName": "SAMA"}}}},
    )

    ns = ciq.build_parser().parse_args(
        [
            "deploy",
            "--base-url",
            "https://f",
            "--job-id",
            "j1",
            "--scope",
            "/subscriptions/sub",
            "--assign",
        ]
    )
    rc = ciq.cmd_deploy(ns)
    assert rc == 0
    assert captured["body"]["enforce_mode"] is False
    assert captured["body"]["assign"] is True
    assert captured["body"]["initiative_name"] == "sama"


def test_request_raises_ciqerror_on_http_error(monkeypatch):
    class FakeHTTPError(ciq.urllib.error.HTTPError):
        def __init__(self):
            super().__init__("http://x", 401, "Unauthorized", {}, io.BytesIO(b'{"detail":"no"}'))

    def boom(req, timeout=0):
        raise FakeHTTPError()

    monkeypatch.setattr(ciq.urllib.request, "urlopen", boom)
    with pytest.raises(ciq.CiqError) as exc:
        ciq._request("GET", "http://x", "tok")
    assert "401" in str(exc.value)
