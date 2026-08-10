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

def _grounded_d(control_id, name=None):
    """A category D mapping whose attestation claim actually resolved.

    Since only grounded D counts towards ``compliant``, tests about the compliant
    figure have to say which kind of D they mean. Bare ``coverage_category=D``
    is now the *unevidenced* case, on purpose.
    """
    from app.services.attestation_catalog_service import GROUNDED

    mapping = _mapping(control_id, [], coverage_category=coverage.COVERAGE_D, name=name)
    mapping.attestation = {
        "status": GROUNDED,
        "citation": "ISO/IEC 27001:2022 clause 9.2 (Internal audit)",
        "retrieval": "Download the certificate from the Service Trust Portal.",
    }
    return mapping


def test_manual_register_and_summary():
    mappings = [
        _mapping("A-1", [REAL_GUID], coverage_category=coverage.COVERAGE_A),
        _mapping("C-1", [], coverage_category=coverage.COVERAGE_C, control_type="Governance"),
        _grounded_d("D-1"),
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
    """D never enters the initiative, and counts as compliant only once cited.

    This test previously asserted that *any* D control was compliant and that
    the register told the reader "no customer action required". That was the
    false-pass behaviour: it made the compliant percentage a function of how
    many controls the model was willing to label ``D_MicrosoftAttestation``,
    with no check that Microsoft attests anything of the sort.

    The invariant now is: the category is a claim, a grounded citation is
    evidence, and only evidence counts.
    """
    from app.services.attestation_catalog_service import GROUNDED

    grounded = _mapping("D-1", [], coverage_category=coverage.COVERAGE_D)
    grounded.attestation = {
        "status": GROUNDED,
        "citation": "SOC 2 Type II criterion CC6.4 (Restricted physical access)",
        "retrieval": "Download the report from the Service Trust Portal.",
    }
    unresolved = _mapping("D-2", [], coverage_category=coverage.COVERAGE_D)

    summary = coverage.coverage_summary([grounded, unresolved])

    # Neither is in the initiative — nothing here is Azure-Policy enforceable.
    assert summary["azure_enforceable"] == 0
    assert summary["azure_enforceable_pct"] == 0.0
    assert not grounded.azure_policy_ids and not unresolved.azure_policy_ids

    # Only the cited one is compliant.
    assert summary["D_MicrosoftAttestation"] == 2
    assert summary["compliant"] == 1
    assert summary["attestation_gaps"] == 1

    rows = {r["control_id"]: r["reason"] for r in coverage.manual_register_rows([grounded, unresolved])}
    # The cited control hands over the citation...
    assert "CC6.4" in rows["D-1"]
    # ...and the uncited one admits it is unevidenced rather than passing.
    assert "unevidenced" in rows["D-2"]
    assert "no customer action required" not in rows["D-2"]


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
            _grounded_d("D-1"),
        ]
    )
    readme = _deploy_readme("Test", "Test Framework", False, counts)["content"]

    assert "66.7%" in readme  # A + grounded D compliant
    assert "compliant by inheritance" in readme
    assert "no customer remediation" in readme


def test_deploy_readme_names_ungrounded_attestations_rather_than_counting_them():
    """The bundle is the artefact a regulator sees. An unattested control must
    not silently inflate the compliant figure, and must be named as an item to
    escalate."""
    from app.api.routes.policy import _deploy_readme

    counts = coverage.coverage_summary(
        [
            _mapping("A-1", [REAL_GUID], coverage_category=coverage.COVERAGE_A),
            _grounded_d("D-1"),
            _mapping("D-2", [], coverage_category=coverage.COVERAGE_D),  # never grounded
        ]
    )
    assert counts["compliant"] == 2 and counts["attestation_gaps"] == 1

    readme = _deploy_readme("Test", "Test Framework", False, counts)["content"]
    assert "66.7%" in readme  # not 100% — the ungrounded control does not count
    assert "could not be grounded" in readme
    assert "escalate commercially" in readme


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
        evidence_source=None,
    ):
        self.coverage_category = category
        self.responsibility = responsibility
        self.reason = reason
        # ``evidence`` is the original short-hand; ``evidence_source`` matches
        # the real ControlClassification field name and reads better in the
        # attestation tests, where the claim being validated is the subject.
        self.evidence_source = evidence_source if evidence_source is not None else evidence
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


def test_effects_align_one_to_one_with_the_policy_ids_on_the_row():
    """A reader must be able to tell which policy denies and which only audits.

    The analyst workbook lists effects ";"-separated and positionally aligned
    with the identifiers on the same row, and its 41 policy-bearing rows have
    zero length mismatches. The code deduplicated the effects, so three ids that
    all audited collapsed to a single "Audit" and the row said nothing at all
    about the second and third policies. Measured live on NCA CCC: six controls
    emitted more ids than effects.
    """

    class _MixedCatalog(_FakeCatalog):
        effects = {
            "11111111-1111-1111-1111-111111111111": "Audit",
            "22222222-2222-2222-2222-222222222222": "Audit",
            "33333333-3333-3333-3333-333333333333": "Deny",
        }

        def get(self, name):
            guid = (name or "").strip().rstrip("/").rsplit("/", 1)[-1]
            if guid not in self.effects:
                return None
            return {"effect": self.effects[guid]}

    ids = list(_MixedCatalog.effects) + ["44444444-4444-4444-4444-444444444444"]
    mapping = _mapping("ENC-9", ids, control_type="Technical")
    coverage.apply_coverage(mapping, "Technical", _MixedCatalog())

    assert len(mapping.policy_effects) == len(mapping.azure_policy_ids)
    # Duplicates are kept: position carries the meaning, not the distinct set.
    assert mapping.policy_effects[:3] == ["Audit", "Audit", "Deny"]
    # An id the catalog cannot resolve is named, not silently blank - a blank
    # effect reads as "this policy does nothing".
    assert mapping.policy_effects[3] == coverage.EFFECT_UNKNOWN
    # Audit reports at run-time and Deny blocks at deploy-time, so a row
    # carrying both is honestly described as covering both planes.
    assert mapping.enforcement_plane == coverage.PLANE_BOTH


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
    """An identifier that is not an identifier at all must be named, not dropped.

    This was previously written around ``17k78e20-9358-41c9-923c-fb736d382a12``
    from the analyst's workbook, on the belief that the letter 'k' made it a
    typo and that catching it was the thesis of the product. That belief was
    wrong: ``az policy definition show`` returns it as ``policyType: BuiltIn``.
    It is a real, live policy, and the test above now locks the opposite rule.

    The principle it was reaching for is sound and still holds - a rejected
    identifier must be reported on the control it came from, never quietly
    removed - so it is asserted here against something that genuinely is not an
    identifier, which is what the format check is actually good for.
    """
    malformed = "not-a-policy-identifier"

    class _KnowsOnlyReal(_FakeCatalog):
        def exists(self, name):
            guid = (name or "").strip().rstrip("/").rsplit("/", 1)[-1]
            return guid in (REAL_GUID, REGCOMPLIANCE_GUID)

    catalog = _KnowsOnlyReal()
    assert coverage.classify_policy_id(malformed, catalog) == coverage.ID_MALFORMED

    mapping = _mapping("GUID-1", [REAL_GUID, malformed], control_type="Technical")
    coverage.apply_coverage(mapping, "Technical", catalog)

    # The valid one survives...
    assert mapping.azure_policy_ids == [REAL_GUID]
    # ...and the bad one is named, with the reason, on the control it came
    # from — the difference between a reported gap and a silent loss.
    assert len(mapping.dropped_policy_ids) == 1
    dropped = mapping.dropped_policy_ids[0]
    assert dropped["policy_id"] == malformed
    assert dropped["reason"] == coverage.ID_MALFORMED
    assert dropped["detail"]

    rows = coverage.dropped_policy_rows([mapping])
    assert rows and rows[0]["control_id"] == "GUID-1"
    assert rows[0]["policy_id"] == malformed


def test_a_real_builtin_that_is_not_guid_shaped_is_not_called_malformed():
    """The correction, locked so it cannot be re-broken.

    ``17k78e20-9358-41c9-923c-fb736d382a12`` contains a 'k' and is a real,
    live, deployable Azure built-in. The format check ran before the catalog
    and rejected it as malformed, discarding a correct answer and reporting a
    genuine control as unenforceable. The catalog is asked first now.
    """
    real_but_odd = "17k78e20-9358-41c9-923c-fb736d382a12"

    class _KnowsIt(_FakeCatalog):
        def exists(self, name):
            return name == real_but_odd or super().exists(name)

        def get(self, name):
            if name == real_but_odd:
                return {
                    "display_name": "Transparent Data Encryption on SQL databases should be enabled",
                    "description": "",
                    "effect": "AuditIfNotExists",
                }
            return super().get(name)

    catalog = _KnowsIt()
    assert coverage.classify_policy_id(real_but_odd, catalog) == coverage.ID_OK

    mapping = _mapping("GUID-2", [real_but_odd], control_type="Technical")
    coverage.apply_coverage(mapping, "Technical", catalog)

    assert mapping.azure_policy_ids == [real_but_odd]
    assert mapping.dropped_policy_ids == []


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


# ---------------------------------------------------------------------------
# Category D grounding -- the attestation must be cited, never asserted
# ---------------------------------------------------------------------------
class _FakeAttestations:
    """Minimal stand-in with the one method ``apply_attestation`` consumes."""

    def __init__(self, citation):
        self._citation = citation

    def resolve(self, claim):
        self._citation.raw_claim = claim
        return self._citation


def _citation(**kwargs):
    from app.services.attestation_catalog_service import AttestationCitation

    return AttestationCitation(**kwargs)


def test_a_grounded_d_control_hands_over_an_auditable_citation():
    """D's whole deliverable is the citation, so it must reach the register."""
    from app.services.attestation_catalog_service import GROUNDED

    mapping = _mapping("3.1.1.1", [], control_type="Governance")
    coverage.apply_coverage(
        mapping,
        "Governance",
        None,
        _Classification(
            coverage.COVERAGE_D,
            evidence_source="ATTESTED BY: ISO/IEC 27001:2022 clause 9.2",
        ),
        attestations=_FakeAttestations(
            _citation(
                status=GROUNDED,
                basis_kind="certification_clause",
                scheme_name="ISO/IEC 27001:2022",
                clause="9.2.2",
                clause_title="Internal Audit Programme",
                clause_label="clause",
                clause_verified=True,
                evidence_document="ISO/IEC 27001:2022 certificate",
                evidence_location="https://servicetrust.microsoft.com/viewpage/ISO",
                access_condition="Downloadable without an NDA",
                retrieval="Download it from the Service Trust Portal.",
            )
        ),
    )

    assert mapping.attestation_gap is False
    assert mapping.attestation["clause_verified"] is True
    # The customer is told what to get, from where, and on what terms.
    assert "certificate" in mapping.evidence_source
    assert "servicetrust" in mapping.evidence_source
    assert "NDA" in mapping.evidence_source

    row = coverage.manual_register_rows([mapping])[0]
    assert row["attestation_status"] == GROUNDED
    assert row["attestation_citation"]
    assert row["attestation_access"]


def test_an_ungrounded_d_control_is_declared_a_gap_not_a_pass():
    """The sovereign case, and the sharpest form of the honesty requirement.

    The workbook's control 3.1.3.4 requires UAE national security clearance for
    operations personnel; ISO/IEC 27001 and SOC 2 attest *screening*, not UAE
    clearance. Reporting it as "Microsoft attested" would hand a UAE customer a
    false pass on precisely the sovereign requirement their regulator examines
    hardest -- and the regulator, not the customer, would be the one to find out.
    """
    from app.services.attestation_catalog_service import UNATTESTED

    mapping = _mapping("3.1.3.4", [], control_type="Governance")
    coverage.apply_coverage(
        mapping,
        "Governance",
        None,
        _Classification(
            coverage.COVERAGE_D,
            reason="The NCSP requires UAE security clearance for operations personnel.",
            evidence_source="ATTESTED BY: UAE National Security Clearance Programme",
        ),
        attestations=_FakeAttestations(
            _citation(
                status=UNATTESTED,
                reason="Microsoft attests personnel screening, not UAE national clearance",
            )
        ),
    )

    assert mapping.attestation_gap is True
    assert "No Microsoft attestation grounds this requirement" in mapping.evidence_source

    # The control-specific requirement survives into the reason, because
    # "no attestation covers this" is only actionable if the reader knows what.
    reason = coverage.manual_register_rows([mapping])[0]["reason"]
    assert "UAE security clearance" in reason
    assert "Escalate" in reason

    gaps = coverage.attestation_gap_rows([mapping])
    assert [g["control_id"] for g in gaps] == ["3.1.3.4"]
    assert gaps[0]["action"]


def test_an_ungrounded_d_control_is_excluded_from_the_compliant_count():
    """The number the customer reads first must not be inflated by a claim.

    ``D_MicrosoftAttestation`` is a *category*; only a validated citation is
    *evidence*. Counting the two the same way is how an unattested sovereign
    requirement becomes a green tick.
    """
    from app.services.attestation_catalog_service import GROUNDED, UNATTESTED

    grounded = _mapping("D-ok", [], control_type="Governance")
    coverage.apply_coverage(
        grounded, "Governance", None,
        _Classification(coverage.COVERAGE_D, evidence_source="SOC 2 CC6.4"),
        attestations=_FakeAttestations(
            _citation(status=GROUNDED, scheme_name="SOC 2 Type II", clause="CC6.4",
                      clause_title="Restricted physical access", clause_verified=True)
        ),
    )
    ungrounded = _mapping("D-gap", [], control_type="Governance")
    coverage.apply_coverage(
        ungrounded, "Governance", None,
        _Classification(coverage.COVERAGE_D, evidence_source="Microsoft operates this"),
        attestations=_FakeAttestations(
            _citation(status=UNATTESTED, reason="no scheme was named")
        ),
    )

    summary = coverage.coverage_summary([grounded, ungrounded])
    assert summary["D_MicrosoftAttestation"] == 2
    assert summary["attestation_gaps"] == 1
    assert summary["inherited_compliant"] == 1  # not 2
    assert summary["compliant"] == 1


def test_a_bare_microsoft_operates_this_claim_never_reads_as_evidence():
    """This is what the product emits today, and it grounds nothing."""
    mapping = _mapping("3.9.9.9", [], control_type="Governance")
    coverage.apply_coverage(
        mapping, "Governance", None,
        _Classification(coverage.COVERAGE_D, evidence_source="Microsoft operates this control"),
    )
    assert mapping.attestation_gap is True
    assert "Microsoft operates this control" not in (mapping.evidence_source or "")


def test_c_controls_are_not_given_attestations():
    """Only D claims attestation. A process control's evidence is the customer's."""
    mapping = _mapping("2.1.1.1", [], control_type="Governance")
    coverage.apply_coverage(
        mapping, "Governance", None,
        _Classification(coverage.COVERAGE_C, evidence_source="Customer GRC records"),
    )
    assert mapping.attestation is None
    assert mapping.attestation_gap is False
    assert mapping.evidence_source == "Customer GRC records"
    assert coverage.attestation_gap_rows([mapping]) == []


def test_an_unavailable_attestation_catalog_fails_towards_the_gap():
    """A missing snapshot must degrade to an admitted gap, never to a silent pass.

    Two ways the catalog can be unavailable: not passed at all (deployment or
    wiring fault), and present but unable to ground the claim. Both have to land
    on the same side, because the alternative is a control that reads as
    Microsoft-attested purely because the evidence source failed to load.
    """
    # 1. No catalog supplied at all.
    no_catalog = _mapping("D-1", [], control_type="Governance")
    no_catalog.coverage_category = coverage.COVERAGE_D
    coverage.apply_attestation(no_catalog, attestations=None)
    assert coverage.attestation_is_grounded(no_catalog) is False
    assert [r["control_id"] for r in coverage.attestation_gap_rows([no_catalog])] == ["D-1"]

    # 2. Catalog present, but it cannot ground the claim.
    unresolvable = _mapping("D-2", [], control_type="Governance")
    unresolvable.coverage_category = coverage.COVERAGE_D
    coverage.apply_attestation(unresolvable, attestations=_FakeAttestations(
        _citation(status="unattested", reason="the attestation catalog is unavailable")
    ))
    assert unresolvable.attestation_gap is True
    assert coverage.attestation_is_grounded(unresolvable) is False


def test_the_generic_microsoft_operated_sentence_is_gone():
    """Every D row used to carry the same sentence, which told an auditor nothing
    and read as a pass. It must no longer be reachable for a grounded control."""
    from app.services.attestation_catalog_service import GROUNDED

    mapping = _mapping("D-1", [], control_type="Governance")
    coverage.apply_coverage(
        mapping, "Governance", None,
        _Classification(coverage.COVERAGE_D, evidence_source="SOC 2 CC6.4"),
        attestations=_FakeAttestations(
            _citation(status=GROUNDED, scheme_name="SOC 2 Type II", clause="CC6.4",
                      clause_title="Restricted physical access", clause_label="criterion",
                      clause_verified=True, retrieval="Download it from the STP.")
        ),
    )
    reason = coverage.manual_register_rows([mapping])[0]["reason"]
    assert "no customer action required" not in reason
    assert "CC6.4" in reason


def test_the_manual_register_csv_carries_the_attestation_columns():
    """The register is the artefact handed to the auditor; the citation has to be in it."""
    from app.services.attestation_catalog_service import GROUNDED

    mapping = _mapping("D-1", [], control_type="Governance")
    coverage.apply_coverage(
        mapping, "Governance", None,
        _Classification(coverage.COVERAGE_D, evidence_source="SOC 2 CC6.4"),
        attestations=_FakeAttestations(
            _citation(status=GROUNDED, scheme_name="SOC 2 Type II", clause="CC6.4",
                      clause_title="Restricted physical access", clause_verified=True,
                      evidence_document="Azure SOC 2 Type II report",
                      access_condition="Requires the Microsoft NDA")
        ),
    )
    csv_text = coverage.manual_controls_csv([mapping])
    header = csv_text.splitlines()[0]
    for column in (
        "attestation_status", "attestation_basis", "attestation_citation",
        "attestation_document", "attestation_location", "attestation_access",
        "attestation_gap",
    ):
        assert column in header
    assert "Azure SOC 2 Type II report" in csv_text


# -- Responsibility and coverage category are independent axes -----------------
#
# The source workbook is explicit: "Coverage category is independent of
# responsibility: it describes HOW a control is met, not WHO owns it." Its own
# rows prove the point -- 30 of its 71 process/organisational controls are
# Microsoft-owned, and every one of its A and B controls is too. Code that
# derives one from the other cannot express any of that.


def test_a_process_control_can_be_microsoft_owned():
    """The combination the old coupling could not represent at all.

    Microsoft runs process controls: datacentre access procedures, personnel
    screening, its own incident response. Forcing C to Customer hands the
    customer 30 pieces of work that are not theirs.
    """
    mapping = _mapping("PHY-1", [], control_type="Process")
    coverage.apply_coverage(
        mapping,
        mapping.control_type,
        _FakeCatalog(),
        _Classification(
            coverage.COVERAGE_C,
            responsibility="Microsoft",
            reason="Microsoft operates datacentre visitor procedures.",
        ),
    )
    assert mapping.coverage_category == coverage.COVERAGE_C
    assert mapping.responsibility == "Microsoft"


def test_an_azure_enforced_control_can_be_microsoft_owned():
    """Every A and B row in the gold workbook is Microsoft-owned, so the axes
    do not even correlate in the direction the coupling assumed."""
    mapping = _mapping("DP-1", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(
        mapping,
        mapping.control_type,
        _FakeCatalog(),
        _Classification(coverage.COVERAGE_A, responsibility="Microsoft"),
    )
    assert mapping.azure_enforceable is True
    assert mapping.responsibility == "Microsoft"


def test_a_process_control_can_be_customer_owned():
    mapping = _mapping("GRC-1", [], control_type="Process")
    coverage.apply_coverage(
        mapping,
        mapping.control_type,
        _FakeCatalog(),
        _Classification(coverage.COVERAGE_C, responsibility="Customer"),
    )
    assert mapping.responsibility == "Customer"


def test_responsibility_is_not_invented_when_the_classifier_is_silent():
    """Guessing an owner is worse than admitting the question was not answered:
    a wrong owner sends work to the wrong party and looks authoritative."""
    mapping = _mapping("GRC-2", [], control_type="Process")
    coverage.apply_coverage(
        mapping,
        mapping.control_type,
        _FakeCatalog(),
        _Classification(coverage.COVERAGE_C, responsibility=""),
    )
    assert mapping.responsibility is None


def test_an_attested_control_defaults_to_microsoft():
    """The one permitted fallback, and it is a definition rather than an
    inference: D *means* Microsoft operates it and the customer cannot
    configure it. The reverse inferences are deliberately absent."""
    mapping = _mapping("ATT-1", [], control_type="Process")
    coverage.apply_coverage(
        mapping,
        mapping.control_type,
        _FakeCatalog(),
        _Classification(coverage.COVERAGE_D, responsibility=""),
    )
    assert mapping.responsibility == "Microsoft"


def test_the_classification_prompt_does_not_derive_responsibility_from_category():
    """A regression lock on the prompt itself. The old wording said
    responsibility was "Microsoft for D_MicrosoftAttestation controls", which
    taught the model to read one axis off the other."""
    from app.services.control_classification_service import (
        CLASSIFICATION_SYSTEM_PROMPT,
    )

    lowered = CLASSIFICATION_SYSTEM_PROMPT.lower()
    assert "independent" in lowered
    assert "how a control is met" in lowered
    assert "who owns it" in lowered
    # It must positively invite the combination the coupling forbade.
    assert "process control can be microsoft" in lowered


# -- A control needing a custom policy is told to author one -------------------


def test_a_control_with_no_built_in_is_told_a_custom_definition_is_needed():
    """"N/A" is right for a control Azure was never going to enforce. For one
    that is in scope and came back empty it is an unexplained blank: the control
    *should* have a policy and does not, so the answer is to author one.
    """
    mapping = _mapping("DP-9", [], control_type="Technical")
    coverage.apply_coverage(
        mapping,
        mapping.control_type,
        _FakeCatalog(),
        _Classification(coverage.COVERAGE_A),
    )
    assert mapping.coverage_gap is True
    assert mapping.policy_type == coverage.CUSTOM_POLICY_REQUIRED

    (row,) = coverage.coverage_gap_rows([mapping])
    assert "custom" in row["remediation"].lower()
    assert row["policy_type"] == coverage.CUSTOM_POLICY_REQUIRED


def test_a_process_control_is_not_told_to_author_a_custom_policy():
    """C is not a coverage gap. Telling the customer to write a policy for
    "conduct annual security awareness training" is worse than saying nothing.
    """
    mapping = _mapping("TRN-1", [], control_type="Process")
    coverage.apply_coverage(
        mapping,
        mapping.control_type,
        _FakeCatalog(),
        _Classification(coverage.COVERAGE_C),
    )
    assert mapping.coverage_gap is False
    assert mapping.policy_type == "N/A"
    assert coverage.coverage_gap_rows([mapping]) == []


def test_a_gap_with_a_known_outside_step_names_that_step_in_the_remedy():
    mapping = _mapping("IAM-4", [], control_type="Technical")
    coverage.apply_coverage(
        mapping,
        mapping.control_type,
        _FakeCatalog(),
        _Classification(
            coverage.COVERAGE_B,
            outside_step="Entra Conditional Access policy requiring compliant devices",
        ),
    )
    (row,) = coverage.coverage_gap_rows([mapping])
    assert "Conditional Access" in row["remediation"]


def test_a_covered_control_keeps_its_built_in_policy_type():
    mapping = _mapping("DP-3", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(
        mapping,
        mapping.control_type,
        _FakeCatalog(),
        _Classification(coverage.COVERAGE_A),
    )
    assert mapping.policy_type == "Built-in"
    assert coverage.coverage_gap_rows([mapping]) == []


# -- Provenance: what verified this mapping, and when --------------------------
#
# The workbook Legend documents a "Verification Date & Source" column and warns
# that region and service availability changes without customer notice. Neither
# existed in the product. A regulator asking how the system knows a policy
# exists needs the catalog snapshot the identifier was checked against;
# without it the answer is "the system said so".


def test_every_mapping_records_when_it_was_verified():
    mapping = _mapping("DP-3", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(
        mapping, mapping.control_type, _FakeCatalog(), _Classification(coverage.COVERAGE_A)
    )
    assert mapping.verified_at
    assert mapping.verified_at.startswith("20")


def test_a_mapping_records_the_catalog_snapshot_it_resolved_against():
    class _DatedCatalog(_FakeCatalog):
        snapshot_date = "2026-08-08T16:31:29+00:00"
        source = "snapshot(2467)"

    mapping = _mapping("DP-3", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(
        mapping, mapping.control_type, _DatedCatalog(), _Classification(coverage.COVERAGE_A)
    )
    assert mapping.catalog_snapshot_date == "2026-08-08T16:31:29+00:00"
    assert "2467" in mapping.verification_source
    assert "2026-08-08" in mapping.verification_source
    assert not mapping.provenance_blocker


def test_an_undated_catalog_is_a_declared_blocker_not_a_silent_omission():
    """An undated catalog means nobody can say whether the cited definitions
    still exist. Leaving the field empty for a reader to notice is the same
    failure as a silently dropped GUID."""
    mapping = _mapping("DP-3", [REAL_GUID], control_type="Technical")
    coverage.apply_coverage(
        mapping, mapping.control_type, _FakeCatalog(), _Classification(coverage.COVERAGE_A)
    )
    assert mapping.provenance_blocker
    assert "Re-verify" in mapping.provenance_blocker


def test_provenance_reaches_the_manual_register():
    """A C or D row needs provenance as much as an enforced one -- more, since
    nothing about it can be re-derived from a policy definition."""
    mapping = _mapping("GRC-1", [], control_type="Process")
    coverage.apply_coverage(
        mapping, mapping.control_type, _FakeCatalog(), _Classification(coverage.COVERAGE_C)
    )
    (row,) = coverage.manual_register_rows([mapping])
    assert row["verified_at"]
    assert row["verification_source"]


def test_a_process_control_still_carries_provenance_without_a_catalog():
    mapping = _mapping("GRC-2", [], control_type="Process")
    coverage.apply_coverage(
        mapping, mapping.control_type, None, _Classification(coverage.COVERAGE_C)
    )
    assert mapping.verified_at
    assert mapping.provenance_blocker
