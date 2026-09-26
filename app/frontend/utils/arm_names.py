"""Frontend mirror of the backend's ARM policy resource-name rules.

Lets ``4_Export_Policy.py`` offer a default initiative name the tenant will
actually accept, instead of discovering the limit only when ARM rejects the
deploy. See ``app/backend/app/services/policy_deploy_service.py`` for the
authoritative definitions this mirrors.
"""

import hashlib
import re

# Characters ARM rejects in a policy resource name.
_INVALID_NAME_CHARS = set('<>*%&:\\?/#')
_MGMT_GROUP_PREFIX = "/providers/microsoft.management/managementgroups/"

# The 128 quoted throughout the Azure docs is the **display name** limit; a
# policy resource name is capped at 64, and at only 24 under a management group.
MAX_POLICY_NAME_LEN = 64
MAX_POLICY_NAME_LEN_MG = 24
_NAME_HASH_LEN = 6


def is_management_group_scope(scope: str) -> bool:
    """True when *scope* addresses a management group."""
    return (scope or "").strip().rstrip("/").lower().startswith(_MGMT_GROUP_PREFIX)


def max_policy_name_length(scope: str) -> int:
    """Longest ARM policy resource name permitted at *scope*."""
    return MAX_POLICY_NAME_LEN_MG if is_management_group_scope(scope) else MAX_POLICY_NAME_LEN


def arm_policy_name(source: str, scope: str = "", *, suffix: str = "") -> str:
    """Derive an ARM-valid policy resource name from *source*.

    A deterministic digest is appended whenever the name has to be shortened, so
    two different frameworks cannot collapse onto one name and silently
    overwrite each other's initiative on deploy.
    """
    limit = max_policy_name_length(scope) - len(suffix)
    if limit < 1:
        raise ValueError(
            f"suffix {suffix!r} leaves no room for a name at scope {scope!r}"
        )

    normalized = "".join(
        "-" if (ch in _INVALID_NAME_CHARS or ch.isspace()) else ch
        for ch in (source or "").strip().lower()
    )
    slug = re.sub(r"-{2,}", "-", normalized).strip("-. ")
    if not slug:
        slug = "initiative"

    if len(slug) > limit:
        digest = hashlib.sha256((source or "").strip().encode()).hexdigest()[:_NAME_HASH_LEN]
        keep = max(1, limit - _NAME_HASH_LEN - 1)
        slug = f"{slug[:keep].rstrip('-. ')}-{digest}"

    return f"{slug}{suffix}"
