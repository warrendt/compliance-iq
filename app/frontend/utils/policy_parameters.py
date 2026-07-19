"""Pure, UI-agnostic helpers for opt-in parameterized built-in inclusion.

Kept separate from the Streamlit page so the inclusion logic can be unit-tested
without a Streamlit runtime. A parameterized built-in (one with a required
parameter that has no default, e.g. a Recovery Services vault name/region) is
excluded from a generated initiative by default because ARM rejects the policy
set with ``MissingPolicyParameter``. The operator can opt in by supplying every
required value; only then is the built-in included, with the values baked in as
literal reference parameters.
"""

from typing import Any, Dict, List


def satisfied_parameter_values(
    requirements: List[Dict[str, Any]],
    raw: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Return only the built-ins whose every required parameter has a value.

    Args:
        requirements: the backend ``parameterized_requirements`` list; each item
            has ``policy_id`` and ``parameters`` (``{name: {type, ...}}``).
        raw: operator-supplied values collected from the UI, keyed by
            ``policy_id`` then parameter name.

    Returns:
        ``{policy_id: {param: value}}`` containing only built-ins for which
        *every* required parameter has a non-blank value. Partially-filled
        built-ins are omitted (they stay excluded), matching the backend's
        all-or-nothing inclusion so the emitted initiative stays deployable.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for req in requirements:
        policy_id = req.get("policy_id", "")
        params = req.get("parameters") or {}
        if not policy_id or not params:
            continue
        vals = raw.get(policy_id, {})
        if all(str(vals.get(p, "")).strip() for p in params):
            out[policy_id] = {p: vals[p] for p in params}
    return out
