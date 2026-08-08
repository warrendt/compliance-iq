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
    # D is compliant by inheritance from Microsoft's attestation: out of the
    # initiative, but not a coverage gap. A + D count as compliant; C does not.
    assert summary["inherited_compliant"] == 1
    assert summary["compliant"] == 2
    assert summary["compliant_pct"] == 66.7

    csv_text = coverage.manual_controls_csv(mappings)
    assert "control_id" in csv_text.splitlines()[0]
    assert "C-1" in csv_text and "D-1" in csv_text and "A-1" not in csv_text


def test_microsoft_attested_controls_are_compliant_not_gaps():
    """D never enters the mapping, yet still counts as compliant.

    Regression: the summary only credited A_AzurePolicy, so Microsoft-operated
    controls the customer cannot configure were reported as a coverage gap.
    """
    mappings = [
        _mapping("D-1", [], coverage_category=coverage.COVERAGE_D),
        _mapping("D-2", [], coverage_category=coverage.COVERAGE_D),
    ]
    summary = coverage.coverage_summary(mappings)

    # Not in the mapping — nothing is Azure-Policy enforceable here.
    assert summary["azure_enforceable"] == 0
    assert summary["azure_enforceable_pct"] == 0.0
    assert all(not m.azure_policy_ids for m in mappings)

    # Still fully compliant.
    assert summary["compliant"] == 2
    assert summary["compliant_pct"] == 100.0

    # And the register says so, rather than implying an outstanding action.
    reasons = {r["reason"] for r in coverage.manual_register_rows(mappings)}
    assert all("no customer action required" in r for r in reasons)


def test_b_and_c_remain_open_actions():
    """Only D is inherited-compliant; B and C stay outside the compliant count."""
    mappings = [
        _mapping("B-1", [], coverage_category=coverage.COVERAGE_B),
        _mapping("C-1", [], coverage_category=coverage.COVERAGE_C),
    ]
    summary = coverage.coverage_summary(mappings)
    assert summary["inherited_compliant"] == 0
    assert summary["compliant"] == 0
    assert summary["compliant_pct"] == 0.0


def test_coverage_summary_empty_mappings_do_not_divide_by_zero():
    summary = coverage.coverage_summary([])
    assert summary["total"] == 0
    assert summary["compliant"] == 0
    assert summary["compliant_pct"] == 0.0
    assert summary["azure_enforceable_pct"] == 0.0


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


def test_deploy_readme_reports_attested_controls_as_compliant():
    """The bundle README must not present category D as a coverage gap."""
    from app.api.routes.policy import _deploy_readme

    counts = coverage.coverage_summary(
        [
            _mapping("A-1", [REAL_GUID], coverage_category=coverage.COVERAGE_A),
            _mapping("C-1", [], coverage_category=coverage.COVERAGE_C),
            _mapping("D-1", [], coverage_category=coverage.COVERAGE_D),
        ]
    )
    readme = _deploy_readme("Test", "Test Framework", False, counts)["content"]

    assert "66.7%" in readme  # A + D compliant
    assert "compliant by inheritance" in readme
    assert "no customer remediation" in readme


# -- Blind classification takes precedence over the keyword heuristics ---------


class _Classification:
    """Duck-typed stand-in for ControlClassification."""

    def __init__(self, category, responsibility="Customer", reason="", evidence=""):
        self.coverage_category = category
        self.responsibility = responsibility
        self.reason = reason
        self.evidence_source = evidence


def test_classification_demotes_a_control_that_retrieved_policies():
    """The point of classifying blind.

    A governance control can lexically resemble a technical one and retrieve
    plausible policies. Without this rule the keyword path would call it
    enforceable purely because retrieval succeeded, which is exactly the false
    confidence the rework exists to remove.
    """
    mapping = _mapping(
        "GOV-1",
        [REAL_GUID],
        control_type="Technical",
        name="Cryptographic key management policy",
        reasoning="Encryption key lifecycle must be documented and approved.",
    )
    coverage.apply_coverage(
        mapping,
        mapping.control_type,
        _FakeCatalog(),
        _Classification(coverage.COVERAGE_C, reason="Documented policy, not a setting."),
    )
    assert mapping.coverage_category == coverage.COVERAGE_C
    assert mapping.azure_enforceable is False
    assert mapping.azure_policy_ids == []


def test_classification_rescues_a_control_the_extractor_mistyped():
    """control_type is one upstream signal and must not be fatal.

    Before the classification stage, a technical control typed "Governance" by
    the extractor could never be mapped: the anchoring guard suppressed
    retrieval and the coverage layer stripped its policies.
    """
    mapping = _mapping(
        "ENC-2",
        [REAL_GUID],
        control_type="Governance",
        name="Storage encryption",
        reasoning="Data at rest must be encrypted.",
    )
    coverage.apply_coverage(
        mapping,
        mapping.control_type,
        _FakeCatalog(),
        _Classification(coverage.COVERAGE_A),
    )
    assert mapping.coverage_category == coverage.COVERAGE_A
    assert mapping.azure_policy_ids == [REAL_GUID]


def test_ab_split_is_settled_by_evidence_not_by_the_classifier():
    """Measured: the blind stage recovers only 12.5% of gold A controls.

    Whether a built-in definition exists is a fact about the catalog, not about
    the control text, so a classification of B still becomes A when enforceable
    IDs survive, and a classification of A degrades to B when none do.
    """
    promoted = _mapping("X-1", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(
        promoted, "Technical", _FakeCatalog(), _Classification(coverage.COVERAGE_B)
    )
    assert promoted.coverage_category == coverage.COVERAGE_A

    demoted = _mapping("X-2", [], control_type="Technical")
    coverage.apply_coverage(
        demoted, "Technical", _FakeCatalog(), _Classification(coverage.COVERAGE_A)
    )
    assert demoted.coverage_category == coverage.COVERAGE_B
    assert demoted.azure_enforceable is False


def test_classification_populates_the_gold_workbook_fields():
    mapping = _mapping("P-1", [], control_type="Governance")
    coverage.apply_coverage(
        mapping,
        "Governance",
        _FakeCatalog(),
        _Classification(
            coverage.COVERAGE_C,
            responsibility="Customer",
            reason="Supplier due diligence is a contractual activity.",
            evidence="Signed supplier assurance questionnaires in the GRC register.",
        ),
    )
    assert mapping.responsibility == "Customer"
    assert mapping.coverage_reason.startswith("Supplier due diligence")
    assert "GRC register" in mapping.evidence_source
    assert mapping.enforcement_plane == coverage.PLANE_MANUAL


def test_manual_register_prefers_the_specific_reason():
    """The gold Reason column is per-control; canned text is a fallback only."""
    mapping = _mapping("P-2", [], control_type="Governance")
    coverage.apply_coverage(
        mapping,
        "Governance",
        _FakeCatalog(),
        _Classification(
            coverage.COVERAGE_C, reason="Board oversight cannot be queried."
        ),
    )
    rows = coverage.manual_register_rows([mapping])
    assert rows[0]["reason"] == "Board oversight cannot be queried."

    bare = _mapping("P-3", [], control_type="Governance")
    coverage.apply_coverage(bare, "Governance", _FakeCatalog())
    assert "not Azure-enforceable" in coverage.manual_register_rows([bare])[0]["reason"]


# -- Deterministic enrichment: effects and enforcement plane -------------------


def test_enforcement_plane_distinguishes_blocking_from_reporting():
    """Deny blocks a deployment; Audit only reports it.

    The gold mapping records these separately because they are materially
    different promises, and conflating them overstates coverage.
    """
    assert coverage.enforcement_plane_for(["Deny"]) == coverage.PLANE_DEPLOY
    assert coverage.enforcement_plane_for(["AuditIfNotExists"]) == coverage.PLANE_RUNTIME
    assert coverage.enforcement_plane_for(["deployIfNotExists"]) == coverage.PLANE_DEPLOY
    assert coverage.enforcement_plane_for(["Deny", "Audit"]) == coverage.PLANE_BOTH
    assert coverage.enforcement_plane_for([]) == coverage.PLANE_MANUAL
    assert coverage.enforcement_plane_for(["Manual"]) == coverage.PLANE_MANUAL


def test_effects_are_read_from_the_catalog_not_invented():
    """Asking a model to recall a policy effect invites confident errors.

    An effect determines whether a control is blocked or merely observed, so it
    is resolved from the catalog snapshot only.
    """

    class _EffectCatalog(_FakeCatalog):
        def get(self, name):
            return {"effect": "Deny"}

    mapping = _mapping("ENC-3", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(mapping, "Technical", _EffectCatalog())
    assert mapping.policy_effects == ["Deny"]
    assert mapping.policy_type == "Built-in"
    assert mapping.enforcement_plane == coverage.PLANE_DEPLOY


def test_non_enforceable_controls_report_no_policy_type():
    mapping = _mapping("P-4", [], control_type="Governance")
    coverage.apply_coverage(mapping, "Governance", _FakeCatalog())
    assert mapping.policy_type == "N/A"
    assert mapping.policy_effects == []
