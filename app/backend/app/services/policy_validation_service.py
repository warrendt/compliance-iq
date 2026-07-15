"""
Validate AI-proposed Azure Policy definition GUIDs.

Two modes:

* **ARM** — as the signed-in user, GET each built-in policy definition from
  Azure Resource Manager (delegated Entra ID token, same on-behalf-of pattern
  as ``PolicyDeployService``). A 200 confirms the GUID exists tenant-wide; a 404
  proves the model hallucinated it. Requires the caller's ARM-audience token.
* **Offline** — check GUIDs against the bundled known-good MCSB policy index
  (``data/mcsb/azure_builtin_policy_index.json``). Unknown GUIDs are flagged as
  *unverified* rather than dropped, so nothing is silently discarded.

Every mapping's ``azure_policy_ids`` is first cleaned to well-formed,
de-duplicated GUIDs (removing noise such as ``"See documentation"``).

Verified against Azure docs: built-in policy definitions are read with
``GET /providers/Microsoft.Authorization/policyDefinitions/{guid}``
(api-version ``2023-04-01``); the name of a built-in is its GUID.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_ARM_BASE = "https://management.azure.com"
_API_VERSION = "2023-04-01"
_TIMEOUT = 15.0

# Canonical Azure Policy definition GUID (built-in name).
GUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Non-GUID noise the Microsoft Learn client used to emit as a fake policy id.
_NOISE_IDS = {"see documentation", "n/a", "none", ""}

_INDEX_PATH = (
    Path(__file__).resolve().parent.parent
    / "data" / "mcsb" / "azure_builtin_policy_index.json"
)

# Process-lifetime caches. Built-in policy existence is tenant-global and
# effectively static, so caching across requests is safe and avoids re-querying
# ARM for the same GUID on every mapping job.
_known_good: Optional[frozenset] = None
_existence_cache: dict = {}


class PolicyValidationAuthError(Exception):
    """ARM rejected the caller's token (401/403) — cannot validate as the user."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def clean_policy_ids(ids: Iterable[str]) -> List[str]:
    """Return well-formed, de-duplicated GUIDs, order preserved.

    Drops empty strings, ``"See documentation"`` style noise, and anything that
    is not a canonical policy GUID.
    """
    seen = set()
    cleaned: List[str] = []
    for raw in ids or []:
        candidate = (raw or "").strip()
        if candidate.lower() in _NOISE_IDS or not GUID_RE.match(candidate):
            continue
        key = candidate.lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(candidate)
    return cleaned


def load_known_good_guids() -> frozenset:
    """Load the bundled known-good MCSB policy GUID set (lower-cased)."""
    global _known_good
    if _known_good is None:
        try:
            data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
            _known_good = frozenset(g.lower() for g in data.get("guids", []))
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not load known-good policy index %s: %s", _INDEX_PATH, exc)
            _known_good = frozenset()
    return _known_good


def probe_guid() -> Optional[str]:
    """A deterministic real built-in GUID to probe ARM reachability with."""
    known = load_known_good_guids()
    return next(iter(sorted(known)), None)


# ---------------------------------------------------------------------------
# ARM service (delegated user token)
# ---------------------------------------------------------------------------

class PolicyValidationService:
    """Check Azure Policy definition existence via ARM as the signed-in user."""

    def __init__(self, access_token: str):
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def policy_definition_exists(self, guid: str) -> bool:
        """True if the built-in policy definition GUID exists in ARM.

        Raises PolicyValidationAuthError on 401/403 so callers can fall back to
        offline validation instead of silently treating everything as missing.
        """
        key = guid.lower()
        if key in _existence_cache:
            return _existence_cache[key]

        url = (
            f"{_ARM_BASE}/providers/Microsoft.Authorization"
            f"/policyDefinitions/{guid}?api-version={_API_VERSION}"
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=self._headers)

        if resp.status_code == 200:
            _existence_cache[key] = True
            return True
        if resp.status_code == 404:
            _existence_cache[key] = False
            return False
        if resp.status_code in (401, 403):
            raise PolicyValidationAuthError(
                f"ARM denied policy read ({resp.status_code}); "
                "sign in with an account that can read Azure Policy."
            )
        resp.raise_for_status()
        return False

    async def can_validate(self) -> Tuple[bool, str]:
        """Preflight: can this user read Azure Policy definitions from ARM?"""
        guid = probe_guid()
        if not guid:
            return False, "No known-good policy GUID available to probe ARM."
        try:
            await self.policy_definition_exists(guid)
            return True, "Azure Resource Manager reachable with your permissions."
        except PolicyValidationAuthError as exc:
            return False, str(exc)
        except Exception as exc:  # noqa: BLE001
            return False, f"ARM preflight failed: {exc}"

    async def partition_guids(
        self, guids: List[str], concurrency: int = 5
    ) -> Tuple[List[str], List[str]]:
        """Split *guids* into (existing, missing) using concurrent ARM lookups."""
        if not guids:
            return [], []
        semaphore = asyncio.Semaphore(concurrency)

        async def check(g: str) -> Tuple[str, bool]:
            async with semaphore:
                return g, await self.policy_definition_exists(g)

        results = await asyncio.gather(*(check(g) for g in guids))
        existing = [g for g, ok in results if ok]
        missing = [g for g, ok in results if not ok]
        return existing, missing


# ---------------------------------------------------------------------------
# Mapping annotation
# ---------------------------------------------------------------------------

def annotate_offline(mappings: list) -> list:
    """Clean GUIDs and flag those outside the bundled known-good MCSB set.

    Unknown GUIDs are kept in ``azure_policy_ids`` but also listed in
    ``unverified_policy_ids`` so the UI can badge them — nothing is dropped.
    """
    known = load_known_good_guids()
    for mapping in mappings:
        cleaned = clean_policy_ids(mapping.azure_policy_ids)
        mapping.azure_policy_ids = cleaned
        mapping.unverified_policy_ids = [g for g in cleaned if g.lower() not in known]
        mapping.invalid_policy_ids = []
        mapping.policy_validation_mode = "offline"
    return mappings


async def annotate_arm(mappings: list, validator: PolicyValidationService) -> list:
    """Validate GUIDs against ARM; drop non-existent ones into ``invalid_policy_ids``.

    Raises PolicyValidationAuthError if ARM denies access (caller should fall
    back to :func:`annotate_offline`).
    """
    per_mapping = [(m, clean_policy_ids(m.azure_policy_ids)) for m in mappings]
    union = clean_policy_ids(g for _m, ids in per_mapping for g in ids)
    _existing, missing = await validator.partition_guids(union)
    missing_set = {g.lower() for g in missing}

    for mapping, ids in per_mapping:
        mapping.azure_policy_ids = [g for g in ids if g.lower() not in missing_set]
        mapping.invalid_policy_ids = [g for g in ids if g.lower() in missing_set]
        mapping.unverified_policy_ids = []
        mapping.policy_validation_mode = "arm"
    return mappings
