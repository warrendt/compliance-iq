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


def test_only_c_stays_an_open_customer_action():
    """C is the only open customer action; B is covered, D is inherited.

    B was previously counted with C as "not compliant" because the code stripped
    its policies. B is *partial Azure coverage* — it emits policies and enters
    the initiative — so it belongs on the covered side of the ledger, with the
    outside step named rather than the whole control written off.
    """
    mappings = [
        _mapping("B-1", [], coverage_category=coverage.COVERAGE_B),
        _mapping("C-1", [], coverage_category=coverage.COVERAGE_C),
    ]
    summary = coverage.coverage_summary(mappings)
    assert summary["inherited_compliant"] == 0
    assert summary["azure_enforceable"] == 1  # B counts as covered by Azure
    assert summary["azure_partial"] == 1
    assert summary["compliant"] == 1
    assert summary["compliant_pct"] == 50.0

    # And only C is routed to the manual register.
    rows = coverage.manual_register_rows(mappings)
    assert {r["control_id"] for r in rows} == {"C-1"}


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

    def __init__(
        self,
        category,
        responsibility="Customer",
        reason="",
        evidence="",
        outside_step="",
    ):
        self.coverage_category = category
        self.responsibility = responsibility
        self.reason = reason
        self.evidence_source = evidence
        self.outside_step = outside_step

    @property
    def requires_outside_step(self):
        return bool((self.outside_step or "").strip())


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
    """Measured: the blind stage put 19 of 24 gold-A controls in B.

    Whether a built-in definition exists is a fact about the catalog, not about
    the control text, so a classification of B still becomes A when enforceable
    IDs survive and nothing is outstanding outside Azure Policy.
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
    # Still in scope for Azure — the split describes how the control is covered,
    # it does not decide whether Azure covers it at all.
    assert demoted.azure_enforceable is True
    # ...but the fact that nothing was retrieved is reported, not absorbed into
    # the category label. This is the defect the old derivation created: a recall
    # miss was indistinguishable from a considered judgement of "B".
    assert demoted.coverage_gap is True


def test_partial_coverage_is_decided_by_the_named_outside_step():
    """What actually makes a control category B.

    In the gold mapping 18 of 21 B controls carry policy IDs, several with Deny.
    So B is *Azure coverage plus a remaining step*, not absent coverage — and
    deriving B from "retrieval found nothing" would make it unreachable. The
    classification is asked for the missing step directly, which is a question
    it can answer from the control text, unlike the A/B label itself.
    """
    partial = _mapping("CA-1", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(
        partial,
        "Technical",
        _FakeCatalog(),
        _Classification(
            coverage.COVERAGE_A,  # even an A verdict yields to the outstanding step
            outside_step="Entra Conditional Access policy requiring compliant devices",
        ),
    )
    assert partial.coverage_category == coverage.COVERAGE_B
    # Partial, not uncovered: it keeps its policies and enters the initiative.
    assert partial.azure_policy_ids == [REAL_GUID]
    assert partial.azure_enforceable is True
    assert partial.coverage_gap is False
    # And the customer is told what to go and configure.
    assert partial.outside_step.startswith("Entra Conditional Access")
    assert "Entra Conditional Access" in coverage._reason_for(partial)


def test_absent_outside_step_preserves_the_previously_measured_behaviour():
    """The new signal degrades to the old rule when it is not supplied.

    Guards against the change silently regressing a measured baseline: with no
    outside_step, a control that retrieved policies is still A.
    """
    mapping = _mapping("X-3", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(
        mapping,
        "Technical",
        _FakeCatalog(),
        _Classification(coverage.COVERAGE_B, outside_step=""),
    )
    assert mapping.coverage_category == coverage.COVERAGE_A
    assert mapping.outside_step is None


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


def test_available_effects_records_stricter_options_the_default_hides():
    """A policy defaulting to Audit but permitting Deny is not "Audit only".

    The gold workbook records the effect the expert *intends to assign*, which is
    often stricter than the catalog default. Reporting only the default would tell
    a reviewer a control can be observed when it can in fact be blocked, so the
    permitted set is surfaced alongside the default rather than collapsed into it.
    """

    class _ParameterisedCatalog(_FakeCatalog):
        def get(self, name):
            return {"effect": "Audit", "allowed_effects": ["Audit", "Deny", "Disabled"]}

    mapping = _mapping("ENC-9", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(mapping, "Technical", _ParameterisedCatalog())

    assert mapping.policy_effects == ["Audit"]
    assert mapping.available_effects == ["Audit", "Deny", "Disabled"]
    # The plane follows the default: nothing blocks until someone parameterises it.
    assert mapping.enforcement_plane == coverage.PLANE_RUNTIME


def test_available_effects_is_empty_for_non_parameterised_policies():
    """Most definitions hardcode their effect; absence must not read as "any effect"."""

    class _FixedCatalog(_FakeCatalog):
        def get(self, name):
            return {"effect": "Deny"}

    mapping = _mapping("ENC-10", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(mapping, "Technical", _FixedCatalog())
    assert mapping.available_effects == []


def test_available_effects_unions_across_multiple_policies():
    class _MixedCatalog(_FakeCatalog):
        def get(self, name):
            return {"effect": "Audit", "allowed_effects": ["Audit", "Deny"]}

    mapping = _mapping("ENC-11", [REAL_GUID, REAL_GUID], control_type="Technical")
    coverage.apply_coverage(mapping, "Technical", _MixedCatalog())
    assert mapping.available_effects == ["Audit", "Deny"]


def test_non_enforceable_controls_report_no_available_effects():
    mapping = _mapping("P-9", [], control_type="Governance")
    coverage.apply_coverage(mapping, "Governance", _FakeCatalog())
    assert mapping.available_effects == []


def test_available_effects_survive_the_real_catalog_service():
    """Regression: the in-memory index dropped ``allowed_effects`` on ingest.

    Every other available_effects test uses a fake catalog whose ``get()``
    returns the field directly, so they all passed while the shipped service
    returned definitions without it and the feature was dead in production.
    This test goes through the real ``PolicyCatalogService`` so the gap cannot
    reopen.
    """
    from app.services.policy_catalog_service import get_policy_catalog_service

    catalog = get_policy_catalog_service()
    catalog.load()

    guid = next(
        (
            definition["name"]
            for definition in catalog._definitions
            if "Deny" in (definition.get("allowed_effects") or ())
        ),
        None,
    )
    assert guid, "catalog snapshot carries no Deny-capable definition to test against"

    expected = catalog.get(guid)["allowed_effects"]
    assert expected, "picked a definition with empty allowed_effects"

    mapping = _mapping("ENC-12", [guid], control_type="Technical")
    coverage.apply_coverage(mapping, "Technical", catalog)

    assert mapping.available_effects == expected


def test_hallucinated_policy_ids_are_not_treated_as_enforceable():
    """A GUID the catalog has never seen must not survive as enforcement.

    Otherwise the mapping contradicts itself: azure_enforceable=True with no
    effects and a manual enforcement plane, because enrichment cannot find the
    definition it claims to be enforced by.
    """
    from app.services.policy_catalog_service import get_policy_catalog_service

    catalog = get_policy_catalog_service()
    catalog.load()

    fabricated = "deadbeef-0000-0000-0000-00000000dead"
    assert not catalog.exists(fabricated)

    mapping = _mapping("ENC-13", [fabricated], control_type="Technical")
    coverage.apply_coverage(mapping, "Technical", catalog)

    assert mapping.azure_policy_ids == []
    assert mapping.coverage_category != coverage.COVERAGE_A


# ── The A/B emission rule, and honest reporting of what was lost ──────────────

def test_b_controls_keep_their_policies():
    """A and B are identical for policy emission.

    The previous code cleared azure_policy_ids for every category except A,
    which deleted real enforcement from every B control on every framework.
    B is *partial* Azure coverage — substantially covered by Azure Policy or
    Entra configuration, with a remaining step outside Azure Policy — not
    absent coverage. The gold mapping makes this concrete: 18 of its 21 B
    controls carry policy IDs, several with Deny.
    """
    mapping = _mapping("B-KEEP", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(
        mapping,
        "Technical",
        _FakeCatalog(),
        _Classification(
            coverage.COVERAGE_B,
            outside_step="Entra Conditional Access session controls",
        ),
    )
    assert mapping.coverage_category == coverage.COVERAGE_B
    assert mapping.azure_policy_ids == [REAL_GUID]
    assert mapping.azure_enforceable is True
    assert mapping.coverage_gap is False


def test_c_and_d_never_emit_policies():
    """The one thing that must never regress: non-Azure controls stay out."""
    for category in (coverage.COVERAGE_C, coverage.COVERAGE_D):
        mapping = _mapping(f"{category}-1", [REAL_GUID], control_type="Governance")
        coverage.apply_coverage(
            mapping, "Governance", _FakeCatalog(), _Classification(category)
        )
        assert mapping.coverage_category == category
        assert mapping.azure_policy_ids == []
        assert mapping.azure_enforceable is False
        # Not a gap: nothing was expected here, so flagging one would be noise.
        assert mapping.coverage_gap is False


def test_categories_carry_their_analyst_facing_names():
    """The A_/B_/C_/D_ codes are identifiers; the workbook's names are the output.

    'Azure/Entra config - partial' in particular: the word "partial" is the whole
    meaning of category B, and reading it as "no policy" is what caused the
    stripping bug.
    """
    assert coverage.coverage_display_name(coverage.COVERAGE_A) == "Azure Policy enforced"
    assert (
        coverage.coverage_display_name(coverage.COVERAGE_B)
        == "Azure/Entra config - partial"
    )
    assert coverage.coverage_display_name(coverage.COVERAGE_C) == "Process / organisational"
    assert coverage.coverage_display_name(coverage.COVERAGE_D) == "Microsoft attested"

    mapping = _mapping("DISP-1", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(mapping, "Technical", _FakeCatalog())
    assert mapping.coverage_display == "Azure Policy enforced"


def test_malformed_guid_is_reported_not_silently_dropped():
    """The thesis case, taken verbatim from the analyst's own workbook.

    17k78e20-... appears on two controls in the source mapping; the letter 'k'
    is not hexadecimal. Its JSON transcription discarded it without a word,
    leaving a row whose effects no longer lined up with its policies. That is
    precisely the failure this product exists to prevent, so the identifier is
    a permanent test case: it must be rejected *and reported*, never removed
    quietly.
    """
    malformed = "17k78e20-9358-41c9-923c-fb736d382a12"
    assert coverage.classify_policy_id(malformed, _FakeCatalog()) == coverage.ID_MALFORMED

    mapping = _mapping("GUID-1", [REAL_GUID, malformed], control_type="Technical")
    coverage.apply_coverage(mapping, "Technical", _FakeCatalog())

    # The valid one survives...
    assert mapping.azure_policy_ids == [REAL_GUID]
    # ...and the mistyped one is named, with the reason, on the control it came
    # from — the difference between a reported gap and a silent loss.
    assert len(mapping.dropped_policy_ids) == 1
    dropped = mapping.dropped_policy_ids[0]
    assert dropped["policy_id"] == malformed
    assert dropped["reason"] == coverage.ID_MALFORMED
    assert dropped["detail"]

    rows = coverage.dropped_policy_rows([mapping])
    assert rows and rows[0]["control_id"] == "GUID-1"
    assert rows[0]["policy_id"] == malformed


def test_hallucinated_guid_is_reported_as_absent_from_the_catalog():
    fabricated = "deadbeef-0000-0000-0000-00000000dead"

    class _StrictCatalog(_FakeCatalog):
        def exists(self, name):
            guid = (name or "").strip().rstrip("/").rsplit("/", 1)[-1]
            return guid != fabricated

    mapping = _mapping("GUID-2", [fabricated], control_type="Technical")
    coverage.apply_coverage(
        mapping, "Technical", _StrictCatalog(), _Classification(coverage.COVERAGE_A)
    )

    assert mapping.azure_policy_ids == []
    assert [d["reason"] for d in mapping.dropped_policy_ids] == [coverage.ID_UNKNOWN]
    # In scope for Azure, nothing usable retrieved: an explicit gap.
    assert mapping.coverage_gap is True


def test_retrieval_miss_surfaces_as_a_gap_rather_than_a_category():
    """A recall failure must not disguise itself as a considered judgement.

    Under the old derivation, "in scope for Azure but retrieval found nothing"
    was written out as category B with no policies — identical on the page to a
    control an analyst had deliberately judged partially covered.
    """
    mapping = _mapping("GAP-1", [], control_type="Technical")
    coverage.apply_coverage(
        mapping, "Technical", _FakeCatalog(), _Classification(coverage.COVERAGE_A)
    )
    assert mapping.coverage_gap is True

    rows = coverage.coverage_gap_rows([mapping])
    assert len(rows) == 1
    assert rows[0]["control_id"] == "GAP-1"
    assert "no candidate policy was retrieved" in rows[0]["reason"]

    summary = coverage.coverage_summary([mapping])
    assert summary["coverage_gaps"] == 1


def test_responsibility_is_independent_of_coverage_category():
    """Two axes, not one.

    The source workbook states it plainly: the category describes HOW a control
    is met, not WHO owns it — and 30 of its process/organisational controls are
    Microsoft-owned. Inferring one axis from the other would misattribute every
    one of them.
    """
    mapping = _mapping("ORTH-1", [], control_type="Governance")
    coverage.apply_coverage(
        mapping,
        "Governance",
        _FakeCatalog(),
        _Classification(
            coverage.COVERAGE_C,
            reason="Microsoft operates the process on the customer's behalf.",
            responsibility="Microsoft",
        ),
    )
    assert mapping.coverage_category == coverage.COVERAGE_C
    assert mapping.responsibility == "Microsoft"


def test_gold_b_rows_are_reproducible_in_shape():
    """The workbook's own B rows must be expressible by this engine.

    Not a count target — a shape check. 18 of the gold mapping's 21
    ``B_AzureConfig`` controls carry policy definition IDs, and several carry
    Deny effects on the SLZ deploy-time plane. Before this fix the engine could
    not produce such a row at all: B was defined as "retrieval found nothing",
    so a B control with three Deny policies was unrepresentable.
    """
    mapping = _mapping("2.3.2.2", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(
        mapping,
        "Technical",
        _FakeCatalog(),
        _Classification(
            coverage.COVERAGE_B,
            outside_step="External Key Management (EKM) key lifecycle procedures",
        ),
    )
    assert mapping.coverage_category == coverage.COVERAGE_B
    assert mapping.coverage_display == "Azure/Entra config - partial"
    assert mapping.azure_policy_ids  # carries enforcement, like the gold row
    assert mapping.azure_enforceable is True
    assert mapping.coverage_gap is False
    assert mapping.outside_step

    # And it belongs in the initiative, not the manual register.
    assert coverage.manual_register_rows([mapping]) == []
    assert coverage.coverage_gap_rows([mapping]) == []
    summary = coverage.coverage_summary([mapping])
    assert summary["azure_partial"] == 1
    assert summary["azure_enforceable"] == 1
