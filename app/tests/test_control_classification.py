"""Regression tests for the coverage-classification stage.

Requirement 2 of the mapping rework is the claim that the engine tells a
policy-enforceable control from an operational one. These tests hold that claim
to a measured floor, replaying ``ncsp_v2_classifications.json`` — real
``gpt-5.6-sol`` output captured through ``ControlClassificationService`` — so the
numbers are reproducible in CI with no credentials.

Measured on the 137-control NCSP v2.0 gold mapping (frozen run):

| metric                                   | value | baseline |
|------------------------------------------|-------|----------|
| in-scope accuracy (A/B collapsed)        | 71.5% | 51.8%    |
| exact 4-class accuracy                   | 56.9% | 51.8%    |
| enforceable controls kept in scope       | 80.0% | —        |
| skipped controls that are genuinely manual | 89.4% | —        |

Two results shaped the design and are worth stating plainly:

**The blind stage cannot separate A from B, and should not be asked to.** It
recovered 12.5% of gold ``A_AzurePolicy`` controls while keeping 80% of all
enforceable controls in scope — because whether a built-in definition exists is a
fact about the catalog, not about the control text. ``resolve_coverage``
therefore settles the A/B split *after* retrieval, on evidence. Exact 4-class
accuracy is reported for completeness but is the wrong metric for this stage.

**The two error directions are not equally costly.** A control wrongly called
manual is lost: retrieval never runs and no mapping is produced. A control
wrongly kept in scope is recoverable: retrieval runs, finds nothing enforceable,
and it lands in ``B_AzureConfig`` rather than in the initiative. The prompt is
calibrated accordingly — see the note at the end of
``CLASSIFICATION_SYSTEM_PROMPT`` for the loosened-D experiment that was measured
and rejected.

Floors sit below the measured values to absorb model non-determinism (~3
percentage points of run-to-run variance was observed across four live runs).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import classification_eval as ce  # noqa: E402


@pytest.fixture(scope="module")
def gold():
    return ce.load_gold()


@pytest.fixture(scope="module")
def predictions():
    frozen = ce.load_frozen()
    if not frozen:
        pytest.skip("no frozen classifications fixture")
    return {
        control_id: result["coverage_category"]
        for control_id, result in frozen.items()
        if result.get("coverage_category")
    }


@pytest.fixture(scope="module")
def matrix(gold, predictions):
    return ce.confusion_matrix(gold, predictions)


def test_gold_split_matches_the_workbook(gold):
    """Guard the fixture itself: the expert's split is the yardstick."""
    counts = {}
    for control in gold:
        counts[control["coverage_category"]] = (
            counts.get(control["coverage_category"], 0) + 1
        )
    assert counts == {
        "A_AzurePolicy": 24,
        "B_AzureConfig": 21,
        "C_Process": 71,
        "D_MicrosoftAttestation": 21,
    }
    assert len(gold) == 137


def test_every_gold_control_was_classified(gold, predictions):
    """No silent gaps: a skipped control would flatter every other metric."""
    assert len(predictions) == len(gold)


def test_in_scope_accuracy_beats_the_majority_baseline(matrix, gold):
    """The stage must earn its LLM call.

    Always answering ``C_Process`` scores 51.8% on this fixture, so anything at
    or below that is a classifier that has learned nothing.
    """
    measured = ce.scope_accuracy(matrix)
    baseline = ce.majority_baseline(gold)
    assert measured > baseline + 0.10, (
        f"in-scope accuracy {measured:.1%} vs baseline {baseline:.1%}\n"
        + ce.report(matrix)
    )


def test_in_scope_accuracy_floor(matrix):
    """Measured 71.5%; floor allows for model non-determinism."""
    assert ce.scope_accuracy(matrix) >= 0.65, ce.report(matrix)


def test_enforceable_controls_are_not_dropped(matrix):
    """The unrecoverable error: an enforceable control never reaches retrieval.

    Measured 36 of 45 gold-enforceable controls kept in scope (80.0%).
    """
    counts = ce.enforceability_confusion(matrix)
    kept = counts["true_enforceable"]
    total = kept + counts["false_manual"]
    assert kept / total >= 0.70, (
        f"only {kept}/{total} enforceable controls kept in scope\n"
        + ce.report(matrix)
    )


def test_skipped_controls_are_genuinely_manual(matrix):
    """Retrieval is skipped for C/D, so that decision must be trustworthy.

    Measured 76 of 85 skipped controls genuinely non-enforceable (89.4%).
    """
    counts = ce.enforceability_confusion(matrix)
    correct = counts["true_manual"]
    total = correct + counts["false_manual"]
    assert correct / total >= 0.80, ce.report(matrix)


def test_process_controls_are_recognised(matrix):
    """The largest and most consequential category: 71 of 137 gold controls.

    Forcing a policy onto these is the false confidence this rework removes.
    Measured 78.9%.
    """
    assert ce.per_class_recall(matrix)["C_Process"] >= 0.70, ce.report(matrix)


def test_reasons_are_substantive_and_distinct():
    """The gold's ``Reason`` column is the reasoning quality bar.

    A register whose every row repeats the same sentence is worthless, so check
    both that reasons exist and that they are not boilerplate.
    """
    frozen = ce.load_frozen()
    if not frozen:
        pytest.skip("no frozen classifications fixture")
    reasons = [r.get("reason", "") for r in frozen.values()]
    assert all(len(r) > 80 for r in reasons), "some reasons are too short to justify anything"
    assert len(set(reasons)) == len(reasons), "reasons are not control-specific"


def test_evidence_source_is_always_populated():
    """A "no policy" answer is only actionable if it says what evidences it."""
    frozen = ce.load_frozen()
    if not frozen:
        pytest.skip("no frozen classifications fixture")
    missing = [cid for cid, r in frozen.items() if not r.get("evidence_source")]
    assert not missing, f"controls with no evidence source: {missing}"


def test_responsibility_values_are_from_the_allowed_set():
    frozen = ce.load_frozen()
    if not frozen:
        pytest.skip("no frozen classifications fixture")
    allowed = {"Customer", "Microsoft", "Shared"}
    seen = {r.get("responsibility") for r in frozen.values()}
    assert seen <= allowed, f"unexpected responsibility values: {seen - allowed}"


def test_microsoft_responsibility_tracks_attestation():
    """"Microsoft" responsibility and D_MicrosoftAttestation should agree.

    They are two statements of the same judgement, so disagreement means the
    model is answering the two fields independently rather than coherently.
    """
    frozen = ce.load_frozen()
    if not frozen:
        pytest.skip("no frozen classifications fixture")
    inconsistent = [
        cid
        for cid, r in frozen.items()
        if r.get("responsibility") == "Microsoft"
        and r.get("coverage_category") != "D_MicrosoftAttestation"
    ]
    assert not inconsistent, f"Microsoft-owned but not attested: {inconsistent}"
