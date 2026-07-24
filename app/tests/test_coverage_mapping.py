"""Acceptance tests for the control coverage taxonomy.

The AI mapping engine over-attached Azure Policy IDs to process/legal/governance
controls Azure cannot enforce (UAE run: ~44 of 76 policy-attached controls forced
onto an MCSB "Governance & Strategy" catch-all). These tests pin the deterministic
guarantee: control_type is carried through, non-enforceable controls lose their
policy IDs and are excluded from the initiative, and "Regulatory Compliance"
placeholder built-ins are stripped.
"""

import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.models import ControlMapping
from app.services import coverage
from app.services.policy_service import PolicyGenerationService

REAL_GUID = "18adea5e-f416-4d0f-8aa8-d24321e3e274"
REGCOMPLIANCE_GUID = "aaaaaaaa-0000-0000-0000-000000000001"


class _FakeCatalog:
    """Duck-typed catalog: REAL_GUID enforceable, REGCOMPLIANCE_GUID not."""

    available = True

    def exists(self, name):
        return True

    def is_non_includable(self, name):
        return False

    def is_non_enforceable(self, name):
        guid = (name or "").strip().rstrip("/").rsplit("/", 1)[-1]
        return guid == REGCOMPLIANCE_GUID

    def requires_parameters(self, name):
        return False

    def get(self, name):
        return None

    def get_required_parameters(self, name):
        return {}


def _mapping(
    control_id,
    policy_ids,
    *,
    control_type=None,
    coverage_category=None,
    confidence=0.9,
    name=None,
    reasoning="Relevant control",
):
    return ControlMapping(
        external_control_id=control_id,
        external_control_name=name or f"Control {control_id}",
        mcsb_control_id="GS-1",
        mcsb_control_name="Governance and strategy",
        mcsb_domain="Governance",
        confidence_score=confidence,
        reasoning=reasoning,
        azure_policy_ids=policy_ids,
        mapping_type="conceptual",
        control_type=control_type,
        coverage_category=coverage_category,
    )


# ── Acceptance criterion 1: process controls get no policy ────────────────────

def test_process_control_gets_no_policy():
    mapping = _mapping(
        "LEGAL-1",
        [REAL_GUID],
        control_type="Governance",
        name="Acceptable Legal Jurisdictions",
        reasoning="Defines permitted legal jurisdictions for data.",
    )
    coverage.apply_coverage(mapping, mapping.control_type, _FakeCatalog())
    assert mapping.coverage_category == coverage.COVERAGE_C
    assert mapping.azure_enforceable is False
    assert mapping.azure_policy_ids == []


def test_technical_control_keeps_policy():
    mapping = _mapping(
        "ENC-1",
        [REAL_GUID],
        control_type="Technical",
        name="Encryption at rest",
        reasoning="Require storage encryption with customer keys.",
    )
    coverage.apply_coverage(mapping, mapping.control_type, _FakeCatalog())
    assert mapping.coverage_category == coverage.COVERAGE_A
    assert mapping.azure_enforceable is True
    assert mapping.azure_policy_ids == [REAL_GUID]


def test_process_control_with_technical_text_keeps_policy():
    """A process-typed control whose text is clearly technical is not over-stripped."""
    mapping = _mapping(
        "OPS-9",
        [REAL_GUID],
        control_type="Operational",
        name="Operational logging",
        reasoning="Enable diagnostic logging and retention on all resources.",
    )
    coverage.apply_coverage(mapping, mapping.control_type, _FakeCatalog())
    assert mapping.coverage_category == coverage.COVERAGE_A
    assert mapping.azure_policy_ids == [REAL_GUID]


# ── Acceptance criterion 2: Regulatory-Compliance placeholders filtered ───────

def test_regcompliance_policy_filtered():
    # Even a technical control must not keep a non-enforceable placeholder GUID.
    mapping = _mapping(
        "ENC-2",
        [REAL_GUID, REGCOMPLIANCE_GUID],
        control_type="Technical",
        name="Encryption",
        reasoning="Require encryption.",
    )
    coverage.apply_coverage(mapping, mapping.control_type, _FakeCatalog())
    assert mapping.coverage_category == coverage.COVERAGE_A
    assert mapping.azure_policy_ids == [REAL_GUID]
    assert REGCOMPLIANCE_GUID not in mapping.azure_policy_ids


def test_regcompliance_policy_stripped_in_policy_service():
    service = PolicyGenerationService()
    defs, _groups, _inv, _ni, _pz, _rq, non_enforceable = (
        service._create_policy_definitions(
            [_mapping("CTRL-1", [REAL_GUID, REGCOMPLIANCE_GUID])],
            catalog=_FakeCatalog(),
        )
    )
    ids = [d.policy_definition_id for d in defs]
    assert f"/providers/Microsoft.Authorization/policyDefinitions/{REAL_GUID}" in ids
    assert all(REGCOMPLIANCE_GUID not in pid for pid in ids)
    assert non_enforceable == [REGCOMPLIANCE_GUID]


# ── Acceptance criterion 3: initiative excludes non-A controls ────────────────

def test_initiative_excludes_non_A():
    service = PolicyGenerationService()
    mappings = [
        _mapping("A-1", [REAL_GUID], coverage_category=coverage.COVERAGE_A),
        _mapping("C-1", [], coverage_category=coverage.COVERAGE_C),
        _mapping("D-1", [], coverage_category=coverage.COVERAGE_D),
    ]
    filtered, _warnings = service._filter_mappings(
        mappings, min_confidence=0.5, include_all=False
    )
    kept = {m.external_control_id for m in filtered}
    assert kept == {"A-1"}


def test_legacy_mappings_not_coverage_gated():
    """coverage_category=None (legacy) falls back to confidence-only gating."""
    service = PolicyGenerationService()
    mappings = [_mapping("LEGACY-1", [REAL_GUID], coverage_category=None)]
    filtered, _warnings = service._filter_mappings(
        mappings, min_confidence=0.5, include_all=False
    )
    assert [m.external_control_id for m in filtered] == ["LEGACY-1"]


# ── Acceptance criterion 4: control_type propagated ───────────────────────────

def test_control_type_propagated():
    mapping = _mapping("X-1", [REAL_GUID], control_type="Contractual")
    assert mapping.control_type == "Contractual"  # carried on the model
    coverage.apply_coverage(mapping, "Contractual", _FakeCatalog())
    assert mapping.control_type == "Contractual"
    assert mapping.coverage_category == coverage.COVERAGE_C


# ── Manual register + coverage summary ────────────────────────────────────────

def test_manual_register_and_summary():
    mappings = [
        _mapping("A-1", [REAL_GUID], coverage_category=coverage.COVERAGE_A),
        _mapping("C-1", [], coverage_category=coverage.COVERAGE_C, control_type="Governance"),
        _mapping("D-1", [], coverage_category=coverage.COVERAGE_D),
    ]
    rows = coverage.manual_register_rows(mappings)
    assert {r["control_id"] for r in rows} == {"C-1", "D-1"}

    summary = coverage.coverage_summary(mappings)
    assert summary["total"] == 3
    assert summary["A_AzurePolicy"] == 1
    assert summary["azure_enforceable"] == 1
    assert summary["azure_enforceable_pct"] == 33.3

    csv_text = coverage.manual_controls_csv(mappings)
    assert "control_id" in csv_text.splitlines()[0]
    assert "C-1" in csv_text and "D-1" in csv_text and "A-1" not in csv_text


def test_generate_response_carries_manual_register_section():
    """The generate response surfaces non-Azure controls as a separate section
    while keeping them out of the deployable initiative."""
    from app.models import PolicyGenerationRequest

    service = PolicyGenerationService()
    mappings = [
        _mapping("A-1", [REAL_GUID], coverage_category=coverage.COVERAGE_A),
        _mapping("C-1", [], coverage_category=coverage.COVERAGE_C, control_type="Governance"),
        _mapping("D-1", [], coverage_category=coverage.COVERAGE_D),
    ]
    request = PolicyGenerationRequest(
        framework_name="Test Framework",
        framework_version="v1.0",
        mappings=mappings,
        min_confidence_threshold=0.5,
        include_all_policies=False,
    )
    response = service.generate_initiative(request)

    # Manual register is a separate, structured section on the response.
    manual_ids = {m.control_id for m in response.manual_controls}
    assert manual_ids == {"C-1", "D-1"}
    assert all(m.coverage_category != coverage.COVERAGE_A for m in response.manual_controls)

    # Coverage summary reconciles.
    assert response.coverage_summary["total"] == 3
    assert response.coverage_summary["A_AzurePolicy"] == 1

    # The excluded controls are NOT in the deployable initiative.
    azure = response.initiative.to_azure_json()
    groups = {
        g["name"]
        for g in azure["properties"].get("policyDefinitionGroups", [])
    }
    assert "C-1" not in groups and "D-1" not in groups


def test_attestation_keyword_routes_to_D():
    mapping = _mapping(
        "PHYS-1",
        [],
        control_type="Operational",
        name="Physical security of data centre",
        reasoning="Microsoft operates physical security of the data centre.",
    )
    coverage.apply_coverage(mapping, mapping.control_type, _FakeCatalog())
    assert mapping.coverage_category == coverage.COVERAGE_D
