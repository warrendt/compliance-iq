"""The catalog has to be inspectable from outside the container.

Everything the mapping engine claims rests on which catalog snapshot it is
standing on, and until now that was only visible by shelling into a running
replica. These two routes make it answerable over the API, which is also how
the deployed build gets verified rather than assumed.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.policy_catalog_service import get_policy_catalog_service


@pytest.fixture(scope="module")
def catalog():
    c = get_policy_catalog_service()
    c.load()
    return c


def test_status_reports_definitions_initiatives_and_snapshot(catalog):
    assert catalog.count > 2000, "the shipped corpus is definitions-wide, not a menu"
    assert catalog.initiative_count > 0
    assert catalog.initiatives_available is True
    assert catalog.snapshot_date, "an undated catalog cannot be defended to an auditor"


def test_lookup_resolves_a_definition(catalog):
    known = "404c3081-a854-4457-ae30-26a93ef643f9"  # secure transfer to storage
    assert catalog.identifier_exists(known)
    assert catalog.get(known)["display_name"]


def test_lookup_resolves_the_real_policy_that_is_not_guid_shaped(catalog):
    """The correction, checked against the shipped artifact rather than a stub.

    A format-first rule called this malformed and dropped it. It is a live
    BuiltIn, so the catalog has to be able to say so.
    """
    odd = "17k78e20-9358-41c9-923c-fb736d382a12"
    assert catalog.identifier_exists(odd)
    assert "encryption" in catalog.get(odd)["display_name"].lower()


def test_lookup_reports_initiative_membership(catalog):
    mcsb = "1f3afdf9-d0c9-4c3d-847f-89da613e70a8"
    assert catalog.initiative_exists(mcsb)
    members = catalog.get_initiative(mcsb)["policy_definition_names"]
    assert len(members) > 100

    # ...and the relationship is navigable in both directions, which is what
    # lets the product say "already covered by an initiative you run".
    some_member = next(m for m in members if catalog.exists(m))
    assert mcsb in [i["name"] for i in catalog.initiatives_containing(some_member)]


def test_an_unknown_identifier_is_reported_as_unknown(catalog):
    assert not catalog.identifier_exists("deadbeef-0000-0000-0000-00000000dead")
    assert catalog.get("deadbeef-0000-0000-0000-00000000dead") is None
