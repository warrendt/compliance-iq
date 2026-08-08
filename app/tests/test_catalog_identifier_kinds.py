"""An identifier that resolves to nothing is not automatically an error.

Three different things were all being reported as "no such policy":

* a definition Microsoft has **withdrawn** - the customer needs a migration;
* a **Microsoft Managed Control** (``policyType: Static``) - the customer needs
  nothing, because Microsoft operates and attests it;
* an identifier that genuinely **does not exist** - the citation is wrong.

Only the third is a defect in the mapping. Collapsing all three into one answer
turned Microsoft attestation into apparent broken data, which is exactly the
kind of confidently-wrong output this product exists to avoid.

Measured on the shipped catalog: all 327 initiative members that the
definitions array cannot resolve are Static managed controls. Not one is a
deprecation and not one is unexplained.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services import coverage
from app.services.policy_catalog_service import get_policy_catalog_service

CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "backend" / "app" / "data" / "policy_catalog" / "azure_policy_catalog.json"
)


@pytest.fixture(scope="module")
def raw():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog():
    c = get_policy_catalog_service()
    c.load()
    return c


def test_the_catalog_carries_both_indices(raw):
    assert raw["deprecated_count"] == len(raw["deprecated"]) > 0
    assert raw["managed_control_count"] == len(raw["managed_controls"]) > 0


def test_no_withdrawn_or_managed_definition_leaks_into_the_recommendable_corpus(raw):
    """Neither index may ever be recommended - that is why they are separate."""
    definitions = {d["name"] for d in raw["definitions"]}
    assert definitions.isdisjoint({d["name"] for d in raw["deprecated"]})
    assert definitions.isdisjoint({d["name"] for d in raw["managed_controls"]})


def test_every_initiative_member_can_be_accounted_for(raw):
    """The rule: nothing an initiative references is left unexplained.

    Asserted as a rule rather than a count so it keeps holding as Azure ships
    and retires policies.
    """
    definitions = {d["name"] for d in raw["definitions"]}
    deprecated = {d["name"] for d in raw["deprecated"]}
    managed = {d["name"] for d in raw["managed_controls"]}

    members = set()
    for initiative in raw["initiatives"]:
        members.update(initiative["policy_definition_names"])

    unexplained = members - definitions - deprecated - managed
    assert not unexplained, f"{len(unexplained)} initiative members unaccounted for"


def test_a_managed_control_is_reported_as_attestation_not_as_missing(catalog):
    managed = "0004bbf0-5099-4179-869e-e9ffe5fb0945"  # Microsoft Managed Control 1599
    assert catalog.is_managed_control(managed)
    assert not catalog.exists(managed), "it must never become recommendable"
    assert "Managed Control" in catalog.managed_control_display_name(managed)

    assert coverage.classify_policy_id(managed, catalog) == coverage.ID_MANAGED_CONTROL
    assert coverage.classify_policy_id(managed, catalog) != coverage.ID_UNKNOWN


def test_a_withdrawn_definition_is_reported_as_withdrawn(catalog):
    withdrawn = "001802d1-4969-4c82-a700-c29c6c6f9bbd"  # [Deprecated]: Web Sockets
    assert catalog.is_deprecated(withdrawn)
    assert not catalog.exists(withdrawn)
    assert catalog.deprecated_display_name(withdrawn).startswith("[Deprecated]")

    assert coverage.classify_policy_id(withdrawn, catalog) == coverage.ID_DEPRECATED


def test_something_genuinely_absent_is_still_reported_as_absent(catalog):
    """The distinction only means anything if the third case still fires."""
    fabricated = "deadbeef-0000-0000-0000-00000000dead"
    assert not catalog.is_managed_control(fabricated)
    assert not catalog.is_deprecated(fabricated)
    assert coverage.classify_policy_id(fabricated, catalog) == coverage.ID_UNKNOWN


def test_each_rejection_reason_can_explain_itself():
    """A drop the customer cannot act on is only half a report."""
    for reason in (
        coverage.ID_DEPRECATED,
        coverage.ID_MANAGED_CONTROL,
        coverage.ID_UNKNOWN,
        coverage.ID_MALFORMED,
        coverage.ID_NON_ENFORCEABLE,
        coverage.ID_EMPTY,
    ):
        assert coverage.ID_REJECTION_MESSAGES.get(reason)


def test_none_of_these_are_emitted_as_enforcement(catalog):
    """Whatever the reason, none of them may reach the initiative."""
    real = "404c3081-a854-4457-ae30-26a93ef643f9"
    candidates = [
        real,
        "0004bbf0-5099-4179-869e-e9ffe5fb0945",   # managed control
        "001802d1-4969-4c82-a700-c29c6c6f9bbd",   # withdrawn
        "deadbeef-0000-0000-0000-00000000dead",   # absent
    ]
    kept, dropped = coverage.partition_policy_ids(candidates, catalog)

    assert kept == [real]
    assert {d["reason"] for d in dropped} == {
        coverage.ID_MANAGED_CONTROL,
        coverage.ID_DEPRECATED,
        coverage.ID_UNKNOWN,
    }
    # ...and each one says why, on the identifier it came from.
    assert all(d["policy_id"] and d["detail"] for d in dropped)
