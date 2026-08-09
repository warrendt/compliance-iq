"""Initiatives are real identifiers, and one real identifier is not a GUID.

Two findings drive this file, both measured against the live Azure control
plane rather than assumed:

1. **Azure ships compliance coverage as initiatives, not loose definitions.**
   Microsoft cloud security benchmark, NIST SP 800-53 Rev. 5, ISO 27001:2013
   and CIS Foundations v2.0.0 - the four initiatives in the analyst workbook -
   are policy *set* definitions. A catalog holding definitions only could never
   say "you already run an initiative that covers this", and would report a
   perfectly real initiative GUID as an unresolvable identifier.

2. **A real built-in policy definition name is not always GUID-shaped.**
   ``17k78e20-9358-41c9-923c-fb736d382a12`` - "Transparent Data Encryption on
   SQL databases should be enabled" - contains a ``k``. It was recorded as a
   typo in the plan for this work; ``az policy definition show`` returns it as
   ``policyType: BuiltIn``. It is real, live and deployable.

   That inverts the conclusion. Four call sites validated policy identifiers by
   GUID regex and would have silently stripped this genuine policy from the
   initiative - the same silent-drop failure the validation exists to prevent,
   aimed at a correct answer instead of a hallucinated one. It is the only
   non-GUID-shaped name among 2,269 initiative members, which is exactly what
   makes it dangerous: a rule that is right 2,268 times out of 2,269 is not
   noticed until it costs a customer a control.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pytest  # noqa: E402

from app.services.policy_catalog_service import get_policy_catalog_service  # noqa: E402

# Verified live: az policy definition show --name <this> -> policyType BuiltIn.
NON_GUID_BUILTIN = "17k78e20-9358-41c9-923c-fb736d382a12"

# The four initiatives the analyst workbook cites, by GUID.
WORKBOOK_INITIATIVES = {
    "1f3afdf9-d0c9-4c3d-847f-89da613e70a8": "Microsoft cloud security benchmark",
    "179d1daa-458f-4e47-8086-2a68d0d6c38f": "NIST SP 800-53 Rev. 5",
    "89c6cddc-1c73-4ac1-b19c-54d1a15a42f2": "ISO 27001:2013",
    "06f19060-9e68-4070-92ca-f15cc126059e": "CIS Microsoft Azure Foundations Benchmark v2.0.0",
}


@pytest.fixture(scope="module")
def catalog():
    return get_policy_catalog_service()


# ── The non-GUID built-in ────────────────────────────────────────────


def test_the_non_guid_builtin_is_in_the_catalog(catalog):
    assert catalog.exists(NON_GUID_BUILTIN)
    entry = catalog.get(NON_GUID_BUILTIN)
    assert "Transparent Data Encryption" in entry["display_name"]


def test_the_non_guid_builtin_survives_policy_service_validation():
    """The site that strips identifiers before they reach the initiative."""
    from app.services.policy_service import _is_valid_policy_guid

    assert _is_valid_policy_guid(NON_GUID_BUILTIN)
    assert _is_valid_policy_guid(
        f"/providers/Microsoft.Authorization/policyDefinitions/{NON_GUID_BUILTIN}"
    )


def test_format_validation_still_rejects_a_hallucinated_title():
    """The format check keeps its job: catching things that are not identifiers
    at all, which is what it was actually good for."""
    from app.services.policy_service import _is_valid_policy_guid

    assert not _is_valid_policy_guid("Ensure encryption is enabled")
    assert not _is_valid_policy_guid("")
    assert not _is_valid_policy_guid("not-a-policy-id")


def test_policy_cache_does_not_discard_the_non_guid_builtin():
    """It resolves from the catalog, so filtering it out on format would lose
    details for a policy the catalog can describe perfectly."""
    from app.services import policy_cache_service

    cat = policy_cache_service.get_policy_catalog_service()
    assert cat.identifier_exists(NON_GUID_BUILTIN)
    assert not policy_cache_service.GUID_RE.match(NON_GUID_BUILTIN)


def test_it_is_the_only_non_guid_shaped_name(catalog):
    """A regression alarm, not a constant. If Azure ships another, the sweep
    that finds it should be this test rather than a customer's missing control.
    """
    import re

    guid = re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    odd = [d["name"] for d in catalog._definitions if not guid.match(d["name"])]
    assert odd == [NON_GUID_BUILTIN], odd


# ── Initiatives ──────────────────────────────────────────────────────


def test_initiatives_are_loaded(catalog):
    assert catalog.initiatives_available
    assert catalog.initiative_count > 100


def test_every_workbook_initiative_resolves(catalog):
    """All four were unresolvable before this change - the catalog held
    definitions only, so a real initiative GUID looked like a bad identifier."""
    for guid, expected in WORKBOOK_INITIATIVES.items():
        entry = catalog.get_initiative(guid)
        assert entry is not None, guid
        assert entry["display_name"] == expected


def test_an_initiative_guid_is_not_a_definition_guid(catalog):
    """They are separate ARM resource types. ``exists`` must stay honest about
    what it checks; ``identifier_exists`` is the one that spans both."""
    mcsb = "1f3afdf9-d0c9-4c3d-847f-89da613e70a8"
    assert not catalog.exists(mcsb)
    assert catalog.initiative_exists(mcsb)
    assert catalog.identifier_exists(mcsb)


def test_identifier_exists_still_rejects_an_invented_guid(catalog):
    assert not catalog.identifier_exists("00000000-0000-0000-0000-000000000000")
    assert not catalog.identifier_exists("")


def test_initiatives_accept_a_full_arm_id(catalog):
    mcsb = "1f3afdf9-d0c9-4c3d-847f-89da613e70a8"
    assert catalog.initiative_exists(
        f"/providers/Microsoft.Authorization/policySetDefinitions/{mcsb}"
    )


def test_membership_answers_already_covered_by_an_initiative(catalog):
    """The product claim this enables: "you do not need to assign this
    separately, it ships inside an initiative you already run"."""
    mcsb = catalog.get_initiative("1f3afdf9-d0c9-4c3d-847f-89da613e70a8")
    member = mcsb["policy_definition_names"][0]
    containing = {i["name"] for i in catalog.initiatives_containing(member)}
    assert "1f3afdf9-d0c9-4c3d-847f-89da613e70a8" in containing


def test_a_definition_in_no_initiative_reports_none_not_an_error(catalog):
    assert catalog.initiatives_containing("00000000-0000-0000-0000-000000000000") == []


def test_initiative_membership_keeps_the_non_guid_builtin(catalog):
    """The generator must not filter members on GUID format either, or an
    initiative would understate the coverage it actually gives."""
    containing = catalog.initiatives_containing(NON_GUID_BUILTIN)
    assert containing, "the one non-GUID-shaped built-in vanished from every initiative"


def test_every_initiative_declares_a_consistent_member_count(catalog):
    for init in catalog._initiatives:
        assert init["policy_definition_count"] == len(init["policy_definition_names"])


# ── The generator ────────────────────────────────────────────────────


def test_the_generator_does_not_filter_members_on_guid_format():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from generate_policy_catalog import normalize_initiatives

    out = normalize_initiatives([
        {
            "name": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "display_name": "Test initiative",
            "description": "",
            "policyDefinitions": [
                {
                    "policyDefinitionId": (
                        "/providers/Microsoft.Authorization/policyDefinitions/"
                        + NON_GUID_BUILTIN
                    )
                },
            ],
        }
    ])
    assert out[0]["policy_definition_names"] == [NON_GUID_BUILTIN]


def test_the_generator_deduplicates_members():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from generate_policy_catalog import normalize_initiatives

    ref = "/providers/Microsoft.Authorization/policyDefinitions/" + NON_GUID_BUILTIN
    out = normalize_initiatives([
        {
            "name": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "display_name": "Test initiative",
            "policyDefinitions": [
                {"policyDefinitionId": ref},
                {"policyDefinitionId": ref},
            ],
        }
    ])
    assert out[0]["policy_definition_count"] == 1


def test_the_generator_skips_an_initiative_with_no_display_name():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from generate_policy_catalog import normalize_initiatives

    assert normalize_initiatives([{"name": "x", "display_name": ""}]) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
