"""Frontend mirror of the backend's coverage taxonomy constants.

Keeps ``2_AI_Mapping.py``, ``3_Review_Edit.py`` and ``4_Export_Policy.py``
agreeing on which controls are "policy mappings" (Azure covers them, an
initiative entry is constructed) versus the "manual register" (Azure cannot
address them at all - process/legal/contractual or Microsoft-attested), and on
which controls' confidence_score is a real match-quality signal rather than a
fixed 0.0 placeholder. See ``app/backend/app/services/coverage.py`` for the
authoritative definitions this mirrors.
"""

from typing import Any, Dict

COVERAGE_A = "A_AzurePolicy"
COVERAGE_B = "B_AzureConfig"
COVERAGE_C = "C_Process"
COVERAGE_D = "D_MicrosoftAttestation"

# Categories Azure actually covers - these carry azure_policy_ids and appear
# in the generated initiative.
POLICY_BEARING_CATEGORIES = frozenset({COVERAGE_A, COVERAGE_B})

# Categories Azure cannot address at all - no initiative entry is constructed
# for these, so they do not belong in a "review the Azure Policy mapping"
# workflow. They still need tracking (manual attestation, process evidence),
# just not alongside confidence scores and sovereignty verdicts that never
# applied to them.
NON_POLICY_CATEGORIES = frozenset({COVERAGE_C, COVERAGE_D})


def is_policy_mapping(mapping: Dict[str, Any]) -> bool:
    """True when Azure covers this control - it belongs in "Policy Mappings".

    ``coverage_category`` of ``None`` (legacy/unclassified mappings, or a
    mapping the coverage stage never touched) is treated as a policy mapping
    for backward compatibility, matching the backend's own convention (see
    ``coverage_summary``'s "unclassified" bucket).
    """
    category = mapping.get("coverage_category")
    return category not in NON_POLICY_CATEGORIES


def is_manual_register(mapping: Dict[str, Any]) -> bool:
    """True when this control belongs in the Manual Register (C/D only)."""
    return mapping.get("coverage_category") in NON_POLICY_CATEGORIES


def confidence_eligible(mapping: Dict[str, Any]) -> bool:
    """True when confidence_score is a real match-quality signal.

    C_Process/D_MicrosoftAttestation controls never attempt an Azure Policy
    match, so their confidence_score is a fixed 0.0 placeholder rather than a
    graded assessment - averaging it in with A/B controls' genuine scores
    misrepresents how well the actual mapping work went.
    """
    return is_policy_mapping(mapping)
