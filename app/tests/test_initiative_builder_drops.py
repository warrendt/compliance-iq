"""The initiative builder must never drop an identifier without saying so.

ARM rejects malformed and non-existent policy definition IDs, so dropping them
is unavoidable - the whole deployment fails otherwise. Dropping them *silently*
is the defect this product exists to prevent, and the analyst gold workbook
demonstrates it: it contains the mistyped GUID
``17k78e20-9358-41c9-923c-fb736d382a12`` (the letter ``k`` is not hexadecimal),
and the transcription into JSON silently discarded it, leaving output that
still looked complete.

A control that lost its enforcement must not read the same as one that never
needed any.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.pipeline.initiative_builder import _build_policies  # noqa: E402
from app.pipeline.models import AzurePolicyMapping, ControlPolicyMapping  # noqa: E402

REAL_GUID = "404c3081-a854-4457-ae30-26a93ef643f9"
ABSENT_GUID = "7595c971-233d-4bcf-bd18-596129188c49"
# The mistyped identifier from the analyst workbook. Kept verbatim as a
# permanent test case rather than corrected, because correcting it would delete
# the evidence of the failure mode.
MALFORMED_GUID = "17k78e20-9358-41c9-923c-fb736d382a12"


class _Catalog:
    def __init__(self, known=(REAL_GUID,), available=True):
        self._known = set(known)
        self._available = available

    def exists(self, name):
        return name in self._known

    def available(self):
        return self._available


def _mapping(control_id, policy_ids):
    return ControlPolicyMapping(
        control_id=control_id,
        control_title=f"Control {control_id}",
        domain="Data Protection",
        mcsb_control_id="DP-3",
        mcsb_control_name="Encrypt data in transit",
        confidence_score=0.9,
        mapping_rationale="Relevant",
        azure_policies=[
            AzurePolicyMapping(
                policy_definition_id=pid,
                policy_name=f"Policy {pid}",
                policy_description="",
                relevance="high",
            )
            for pid in policy_ids
        ],
        is_automatable=True,
    )


def test_a_malformed_identifier_is_dropped_and_named():
    mapping = _mapping("C-1", [REAL_GUID, MALFORMED_GUID])

    refs = _build_policies([mapping], catalog=_Catalog())

    # It must not reach ARM...
    assert [r["PolicyDefinitionReferenceId"] for r in refs] == [REAL_GUID]
    # ...and it must not vanish.
    assert mapping.dropped_policy_ids == [
        {"policy_id": MALFORMED_GUID, "reason": "malformed"}
    ]


def test_a_well_formed_identifier_absent_from_the_catalog_is_named():
    """This is the hallucinated-GUID case: correct shape, no such policy."""
    mapping = _mapping("C-1", [REAL_GUID, ABSENT_GUID])

    refs = _build_policies([mapping], catalog=_Catalog())

    assert [r["PolicyDefinitionReferenceId"] for r in refs] == [REAL_GUID]
    assert mapping.dropped_policy_ids == [
        {"policy_id": ABSENT_GUID, "reason": "not_in_catalog"}
    ]


def test_a_control_that_loses_every_policy_says_so():
    """The worst case: the control still appears in the initiative groups, but
    enforces nothing. Without a record it is indistinguishable from a control
    that never needed a policy."""
    mapping = _mapping("C-1", [MALFORMED_GUID, ABSENT_GUID])

    refs = _build_policies([mapping], catalog=_Catalog())

    assert refs == []
    assert {d["reason"] for d in mapping.dropped_policy_ids} == {
        "malformed", "not_in_catalog"
    }


def test_drops_are_not_recorded_twice():
    """The same identifier can arrive against a control more than once; the
    report should read as a set of problems, not a tally of loop iterations."""
    mapping = _mapping("C-1", [MALFORMED_GUID, MALFORMED_GUID])

    _build_policies([mapping], catalog=_Catalog())

    assert len(mapping.dropped_policy_ids) == 1


def test_a_valid_mapping_records_nothing():
    mapping = _mapping("C-1", [REAL_GUID])

    _build_policies([mapping], catalog=_Catalog())

    assert mapping.dropped_policy_ids == []


def test_an_unavailable_catalog_falls_back_to_format_checking_only():
    """Regression: ``enforce_existence`` read the bound ``available`` method
    rather than calling it, so it was always True. With a catalog that had
    failed to load, ``exists()`` returns False for everything and *every*
    policy was dropped - producing an empty but apparently successful
    initiative. The documented fallback never ran."""
    mapping = _mapping("C-1", [REAL_GUID, ABSENT_GUID, MALFORMED_GUID])

    refs = _build_policies([mapping], catalog=_Catalog(known=(), available=False))

    # Both well-formed GUIDs survive; only the malformed one is rejected.
    assert {r["PolicyDefinitionReferenceId"] for r in refs} == {REAL_GUID, ABSENT_GUID}
    assert mapping.dropped_policy_ids == [
        {"policy_id": MALFORMED_GUID, "reason": "malformed"}
    ]
