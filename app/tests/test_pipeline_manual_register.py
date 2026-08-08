"""The initiative says what Azure enforces. These artifacts say what it does not.

Three separate files rather than one, because they answer three different
questions and each has a different reader:

  Manual register     - controls the customer must satisfy by other means.
  Coverage gaps       - controls that should have had a policy and got none.
                        These are recall failures, not judgements about the
                        control, and conflating them with the register would
                        hide that.
  Dropped identifiers - every GUID discarded on the way, and why. The gold
                        workbook contains a mistyped GUID that its own
                        transcription silently dropped, leaving output that
                        still looked complete.
"""

import csv
import os
import sys
from pathlib import Path

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pytest  # noqa: E402

from app.pipeline.initiative_builder import build_initiative_artifacts  # noqa: E402
from app.pipeline.models import (  # noqa: E402
    AzurePolicyMapping,
    ControlExtractionResult,
    ControlPolicyMapping,
    ExtractedControl,
    ValidationReport,
)

REAL_GUID = "0961003e-5a0a-4549-abde-af6a37f2724d"


def _control(control_id, title="A control"):
    return ExtractedControl(
        control_id=control_id,
        control_title=title,
        control_description="A requirement.",
        domain="Data Protection",
        control_type="Technical",
    )


def _mapping(control_id, **kwargs):
    base = dict(
        control_id=control_id,
        control_title="A control",
        domain="Data Protection",
        mcsb_control_id="DP-3",
        mcsb_control_name="Encrypt data",
        confidence_score=0.9,
        mapping_rationale="Relevant",
        is_automatable=False,
    )
    base.update(kwargs)
    return ControlPolicyMapping(**base)


def _build(tmp_path, controls, mappings):
    extraction = ControlExtractionResult(
        framework_name="Test Framework",
        controls=controls,
        summary="A framework.",
    )
    return build_initiative_artifacts(
        extraction=extraction,
        mappings=mappings,
        validation=ValidationReport(
            is_valid=True,
            total_controls=len(controls),
            automatable_controls=sum(1 for m in mappings if m.is_automatable),
            manual_controls=sum(1 for m in mappings if not m.is_automatable),
            unique_policies=0,
            avg_confidence=0.9,
        ),
        output_dir=str(tmp_path),
    )


def _rows(files, suffix):
    path = next(f for f in files if f.endswith(suffix))
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_process_and_attested_controls_reach_the_manual_register(tmp_path):
    files = _build(
        tmp_path,
        [_control("C-1"), _control("C-2"), _control("C-3")],
        [
            _mapping("C-1", coverage_category="C_Process"),
            _mapping("C-2", coverage_category="D_MicrosoftAttestation"),
            _mapping(
                "C-3",
                coverage_category="A_AzurePolicy",
                azure_enforceable=True,
                is_automatable=True,
                azure_policies=[
                    AzurePolicyMapping(
                        policy_definition_id=REAL_GUID,
                        policy_name="A policy",
                        policy_description="",
                        relevance="high",
                    )
                ],
            ),
        ],
    )

    rows = _rows(files, "_Manual_Register.csv")
    assert {r["control_id"] for r in rows} == {"C-1", "C-2"}


def test_a_partial_control_is_not_listed_as_manual(tmp_path):
    """B is partial Azure coverage, not an absence of it. Listing it as a manual
    control tells the customer to do work Azure is already doing."""
    files = _build(
        tmp_path,
        [_control("C-1")],
        [
            _mapping(
                "C-1",
                coverage_category="B_AzureConfig",
                azure_enforceable=True,
                outside_step="Conditional Access policy",
            )
        ],
    )

    assert _rows(files, "_Manual_Register.csv") == []


def test_every_register_row_carries_a_substantive_reason(tmp_path):
    files = _build(
        tmp_path,
        [_control("C-1")],
        [
            _mapping(
                "C-1",
                coverage_category="C_Process",
                coverage_reason="Requires a signed supplier contract clause.",
            )
        ],
    )

    (row,) = _rows(files, "_Manual_Register.csv")
    assert "supplier contract" in row["reason"]


def test_an_ungrounded_attestation_is_named_as_a_gap_not_a_pass(tmp_path):
    """The sovereign case: a requirement no Microsoft attestation covers must be
    escalated, not absorbed into a generic 'Microsoft-attested' pass."""
    files = _build(
        tmp_path,
        [_control("C-1")],
        [
            _mapping(
                "C-1",
                coverage_category="D_MicrosoftAttestation",
                coverage_reason="Requires UAE national security clearance for operations staff.",
                attestation_gap=True,
                attestation={
                    "status": "unattested",
                    "reason": "no scheme attests national security clearance",
                },
            )
        ],
    )

    (row,) = _rows(files, "_Manual_Register.csv")
    assert row["attestation_gap"] == "True"
    assert "clearance" in row["reason"]
    assert "Escalate" in row["reason"]


def test_a_grounded_attestation_carries_its_citation_and_location(tmp_path):
    files = _build(
        tmp_path,
        [_control("C-1")],
        [
            _mapping(
                "C-1",
                coverage_category="D_MicrosoftAttestation",
                attestation={
                    "status": "grounded",
                    "basis_kind": "certification_clause",
                    "citation": "ISO/IEC 27001:2022 clause 9.2",
                    "evidence_document": "ISO/IEC 27001 certificate",
                    "evidence_location": "https://servicetrust.microsoft.com",
                    "access_condition": "no NDA required",
                },
            )
        ],
    )

    (row,) = _rows(files, "_Manual_Register.csv")
    assert row["attestation_citation"] == "ISO/IEC 27001:2022 clause 9.2"
    assert row["attestation_location"] == "https://servicetrust.microsoft.com"
    assert row["attestation_access"] == "no NDA required"
    assert row["attestation_gap"] == "False"


def test_a_control_that_retrieved_nothing_is_reported_as_a_gap(tmp_path):
    """In scope for Azure but empty-handed. Reporting this separately is what
    stops a recall miss from hiding inside a category label."""
    files = _build(
        tmp_path,
        [_control("C-1")],
        [
            _mapping(
                "C-1",
                coverage_category="A_AzurePolicy",
                azure_enforceable=True,
                coverage_gap=True,
            )
        ],
    )

    (row,) = _rows(files, "_Coverage_Gaps.csv")
    assert row["control_id"] == "C-1"
    assert "no candidate policy" in row["reason"]


def test_a_covered_control_is_not_reported_as_a_gap(tmp_path):
    files = _build(
        tmp_path,
        [_control("C-1")],
        [
            _mapping(
                "C-1",
                coverage_category="A_AzurePolicy",
                azure_enforceable=True,
                is_automatable=True,
                azure_policies=[
                    AzurePolicyMapping(
                        policy_definition_id=REAL_GUID,
                        policy_name="A policy",
                        policy_description="",
                        relevance="high",
                    )
                ],
            )
        ],
    )

    assert _rows(files, "_Coverage_Gaps.csv") == []


def test_a_malformed_identifier_is_reported_rather_than_discarded(tmp_path):
    """The workbook's own mistyped GUID, kept verbatim. 'k' is not hexadecimal.

    This is the failure mode the product exists to prevent: an identifier that
    quietly vanishes leaves output that still looks complete.
    """
    files = _build(
        tmp_path,
        [_control("2.3.2.1")],
        [
            _mapping(
                "2.3.2.1",
                coverage_category="A_AzurePolicy",
                azure_enforceable=True,
                is_automatable=True,
                azure_policies=[
                    AzurePolicyMapping(
                        policy_definition_id="17k78e20-9358-41c9-923c-fb736d382a12",
                        policy_name="A policy",
                        policy_description="",
                        relevance="high",
                    )
                ],
            )
        ],
    )

    (row,) = _rows(files, "_Dropped_Policy_IDs.csv")
    assert row["policy_id"] == "17k78e20-9358-41c9-923c-fb736d382a12"
    assert row["control_id"] == "2.3.2.1"
    assert row["reason"]


def test_the_reports_are_written_even_when_they_are_empty(tmp_path):
    """An absent file is ambiguous between 'nothing to report' and 'this step
    did not run'. A header with no rows is not."""
    files = _build(
        tmp_path,
        [_control("C-1")],
        [
            _mapping(
                "C-1",
                coverage_category="A_AzurePolicy",
                azure_enforceable=True,
                is_automatable=True,
                azure_policies=[
                    AzurePolicyMapping(
                        policy_definition_id=REAL_GUID,
                        policy_name="A policy",
                        policy_description="",
                        relevance="high",
                    )
                ],
            )
        ],
    )

    for suffix in (
        "_Manual_Register.csv",
        "_Coverage_Gaps.csv",
        "_Dropped_Policy_IDs.csv",
    ):
        path = next(f for f in files if f.endswith(suffix))
        assert Path(path).exists()
        assert Path(path).read_text(encoding="utf-8").strip()


def test_legacy_mappings_without_a_category_do_not_crash_the_reports(tmp_path):
    """Mappings persisted before the taxonomy existed still deserialise, so the
    reports have to tolerate them."""
    files = _build(tmp_path, [_control("C-1")], [_mapping("C-1")])

    assert _rows(files, "_Manual_Register.csv") == []
    assert _rows(files, "_Coverage_Gaps.csv") == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
