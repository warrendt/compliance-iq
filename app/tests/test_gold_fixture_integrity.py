"""The gold fixture must not quietly disagree with the live Azure catalog.

The fixture is a flattening of the analyst workbook, and it had dropped one
policy identifier during transcription: ``17k78e20-9358-41c9-923c-fb736d382a12``
on controls 2.3.2.1 and 3.3.2.2. It was assumed to be a typo, because it
contains a ``k``. It is not - ``az policy definition show`` returns it as
``policyType: BuiltIn``, "Transparent Data Encryption on SQL databases should be
enabled".

The drop was visible the whole time, as two rows carrying 3 effects against 2
policy identifiers. That misalignment was read as an error in the workbook. It
was evidence of a silent drop in the transcription - which is precisely the
failure mode this product exists to prevent, reproduced inside the fixture used
to prove the product prevents it.

These tests assert **rules**, never counts. The workbook is one worked example
of the method on one framework; its distribution is a property of that document
and nothing else. What generalises is that identifiers resolve, effects align,
and the two output axes stay independent.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pytest  # noqa: E402

from app.services.policy_catalog_service import get_policy_catalog_service  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "ncsp_v2_gold_mapping.json"

TDE = "17k78e20-9358-41c9-923c-fb736d382a12"
DROPPED_FROM = ("2.3.2.1", "3.3.2.2")

POLICY_BEARING = {"A_AzurePolicy", "B_AzureConfig"}


@pytest.fixture(scope="module")
def controls():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["controls"]


@pytest.fixture(scope="module")
def catalog():
    return get_policy_catalog_service()


def test_the_dropped_identifier_is_restored(controls):
    restored = [c for c in controls if c["control_id"] in DROPPED_FROM]
    assert len(restored) == len(DROPPED_FROM)
    for c in restored:
        assert TDE in c["policy_definition_ids"], c["control_id"]


def test_effects_align_one_to_one_with_policy_identifiers(controls):
    """The misalignment that revealed the drop. Effects are positional, so a
    row where they disagree cannot say which policy carries which effect."""
    misaligned = [
        c["control_id"]
        for c in controls
        if c["policy_definition_ids"]
        and len(c["policy_definition_ids"]) != len(c["effects"])
    ]
    assert misaligned == [], misaligned


def test_the_restored_identifier_sits_where_its_effect_says(controls, catalog):
    """Position was derived from the catalog's effects, not chosen to make the
    counts work. If it were merely appended the effects would misdescribe it."""
    for c in controls:
        if c["control_id"] not in DROPPED_FROM:
            continue
        idx = c["policy_definition_ids"].index(TDE)
        assert c["effects"][idx] == catalog.get(TDE)["effect"], c["control_id"]


def test_every_fixture_identifier_resolves_in_the_live_catalog(controls, catalog):
    """The rule the product depends on. An identifier that resolves nowhere
    cannot be deployed, and one that is rejected on format is worse - it is a
    correct answer thrown away."""
    unresolved = sorted({
        pid
        for c in controls
        for pid in c["policy_definition_ids"]
        if not catalog.identifier_exists(pid)
    })
    assert unresolved == [], unresolved


def test_only_policy_bearing_categories_carry_identifiers(controls):
    """The workbook's structural rule: A and B carry Azure Policy, C and D
    never do. This is what generalises across frameworks; the counts do not."""
    offenders = [
        c["control_id"]
        for c in controls
        if c["policy_definition_ids"] and c["coverage_category"] not in POLICY_BEARING
    ]
    assert offenders == [], offenders


def test_responsibility_and_category_are_independent_axes(controls):
    """The Coverage Summary states it outright: category describes HOW a control
    is met, not WHO owns it. If every process control were customer-owned the
    axes would be redundant and the coupling the code used to have would be
    harmless. They are not."""
    ms_process = [
        c["control_id"]
        for c in controls
        if c["coverage_category"] == "C_Process" and c["responsibility"] == "Microsoft"
    ]
    assert ms_process, "expected Microsoft-owned process controls; the axes must not collapse"


def test_control_id_is_the_join_key_and_is_unique(controls):
    ids = [c["control_id"] for c in controls]
    assert len(ids) == len(set(ids))
    assert all(i.strip() for i in ids)


def test_no_identifier_is_duplicated_within_a_control(controls):
    dupes = [
        c["control_id"]
        for c in controls
        if len(c["policy_definition_ids"]) != len(set(c["policy_definition_ids"]))
    ]
    assert dupes == [], dupes


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
