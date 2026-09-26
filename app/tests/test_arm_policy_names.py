"""Tests for ARM policy resource-name derivation.

Regression cover for a deploy failure where an initiative named after a long
framework — "National Cybersecurity Policy Framework (NCPF) for South Africa",
63 characters — was accepted by validation and then rejected by ARM:

    InvalidPolicyAssignmentName: ... must not exceed '64' characters

The 128 quoted throughout the Azure docs is the *display name* limit. A policy
resource name is capped at 64, and at only 24 under a management group, and the
derived ``-assignment`` suffix eats another 11 of that budget.

Run:
    cd app && PYTHONPATH=backend:frontend python -m pytest tests/test_arm_policy_names.py -q
"""

import pytest

from app.services.policy_deploy_service import (
    ASSIGNMENT_NAME_SUFFIX,
    MAX_POLICY_NAME_LEN,
    MAX_POLICY_NAME_LEN_MG,
    arm_policy_name,
    is_management_group_scope,
    max_policy_name_length,
)

_SUB = "/subscriptions/00000000-0000-0000-0000-000000000000"
_MG = "/providers/Microsoft.Management/managementGroups/my-mg"
# The exact name that triggered the production failure.
_NCPF = "National Cybersecurity Policy Framework (NCPF) for South Africa"


def test_subscription_and_management_group_limits():
    assert max_policy_name_length(_SUB) == MAX_POLICY_NAME_LEN == 64
    assert max_policy_name_length(_MG) == MAX_POLICY_NAME_LEN_MG == 24
    assert is_management_group_scope(_MG)
    assert not is_management_group_scope(_SUB)


def test_short_name_is_slugified_but_otherwise_untouched():
    assert arm_policy_name("UAE NCSP", _SUB) == "uae-ncsp"


def test_long_name_is_truncated_within_the_limit():
    name = arm_policy_name(_NCPF, _SUB)
    assert len(name) <= MAX_POLICY_NAME_LEN
    assert " " not in name


def test_assignment_suffix_is_reserved_not_overflowed():
    """The regression: base fit 64 but base + '-assignment' did not."""
    name = arm_policy_name(_NCPF, _SUB, suffix=ASSIGNMENT_NAME_SUFFIX)
    assert name.endswith(ASSIGNMENT_NAME_SUFFIX)
    assert len(name) <= MAX_POLICY_NAME_LEN


def test_management_group_scope_uses_the_24_char_cap():
    assert len(arm_policy_name(_NCPF, _MG)) <= MAX_POLICY_NAME_LEN_MG
    assigned = arm_policy_name(_NCPF, _MG, suffix=ASSIGNMENT_NAME_SUFFIX)
    assert len(assigned) <= MAX_POLICY_NAME_LEN_MG
    assert assigned.endswith(ASSIGNMENT_NAME_SUFFIX)


def test_illegal_characters_are_replaced():
    name = arm_policy_name("ISO/IEC 27001:2022 #A&B", _SUB)
    assert not set(name).intersection('<>*%&:\\?/#')
    assert "--" not in name
    assert not name.startswith("-") and not name.endswith("-")


def test_truncated_names_stay_distinct_and_deterministic():
    """Truncation alone would let two frameworks overwrite each other.

    Deploying is an idempotent PUT, so a collision silently replaces an
    unrelated initiative. Redeploying the same framework must still target the
    same resource, so the name has to be stable too.
    """
    prefix = "National Cybersecurity Policy Framework for the Republic of "
    a = arm_policy_name(prefix + "South Africa", _SUB)
    b = arm_policy_name(prefix + "South Sudan", _SUB)
    assert a != b
    assert a == arm_policy_name(prefix + "South Africa", _SUB)


def test_empty_name_falls_back_rather_than_producing_an_invalid_name():
    assert arm_policy_name("   ", _SUB) == "initiative"
    assert arm_policy_name("###", _SUB) == "initiative"


def test_suffix_longer_than_the_limit_is_rejected():
    with pytest.raises(ValueError):
        arm_policy_name("anything", _MG, suffix="-" + "x" * 40)


def test_frontend_mirror_matches_the_backend():
    """utils/arm_names.py is a mirror; drift would reintroduce the bug in the UI."""
    from utils import arm_names

    for scope in (_SUB, _MG):
        for source in (_NCPF, "UAE NCSP", "ISO/IEC 27001:2022 #A&B", "  "):
            assert arm_names.arm_policy_name(source, scope) == arm_policy_name(
                source, scope
            )
        assert arm_names.max_policy_name_length(scope) == max_policy_name_length(scope)
