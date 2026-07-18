"""
Policy Cache Service.
Caches Azure Policy detail lookups in Cosmos DB with Microsoft Learn fallback.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from urllib.parse import quote

from app.db import cosmos_client
from app.services.microsoft_learn_client import get_microsoft_learn_client
from app.services.policy_catalog_service import get_policy_catalog_service

logger = logging.getLogger(__name__)

GUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _portal_definition_url(policy_id: str) -> str:
    """Build a stable Azure Portal deep link to a built-in policy definition."""
    definition_id = f"/providers/Microsoft.Authorization/policyDefinitions/{policy_id}"
    encoded = quote(definition_id, safe="")
    return (
        "https://portal.azure.com/#view/Microsoft_Azure_Policy/"
        f"PolicyDetailBlade/definitionId/{encoded}"
    )


class PolicyCacheService:
    """Caches Azure Policy details — Cosmos first, Microsoft Learn fallback."""

    def __init__(self):
        self.container = cosmos_client.POLICY_CACHE
        self.learn_client = get_microsoft_learn_client()

    async def get_policy_details(
        self, policy_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Batch-lookup policy details.

        Returns a dict keyed by policy_id with fields:
          policy_id, display_name, description, learn_url, cached_at
        Missing / invalid IDs are silently skipped.
        """
        # Validate & deduplicate
        valid_ids = list({pid for pid in policy_ids if GUID_RE.match(pid)})
        if not valid_ids:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        miss_ids: List[str] = []

        # --- 1. Local catalog pass (authoritative for built-in policies) ---
        # The 2.5k built-in definition snapshot carries readable display names
        # and descriptions in-memory, so it resolves the vast majority of GUIDs
        # instantly without a Cosmos round-trip or a flaky Learn search.
        catalog = get_policy_catalog_service()
        for pid in valid_ids:
            definition = catalog.get(pid)
            if definition:
                results[pid] = self._from_catalog(pid, definition)
            else:
                miss_ids.append(pid)

        if not miss_ids:
            logger.info("policy_catalog_hit_all", extra={"count": len(results)})
            return results

        # --- 2. Cosmos cache hit pass (custom / non-catalog GUIDs) ---
        remaining: List[str] = []
        if cosmos_client.database:
            for pid in miss_ids:
                try:
                    doc = await cosmos_client.get_document(
                        self.container, pid, partition_key=pid
                    )
                    if doc:
                        results[pid] = self._doc_to_detail(doc)
                    else:
                        remaining.append(pid)
                except Exception:
                    remaining.append(pid)
        else:
            remaining = miss_ids
        miss_ids = remaining

        if not miss_ids:
            logger.info("policy_cache_hit_all", extra={"count": len(results)})
            return results

        # --- 3. Microsoft Learn fallback for remaining misses ---
        logger.info(
            "policy_cache_miss",
            extra={"hit": len(results), "miss": len(miss_ids)},
        )
        for pid in miss_ids:
            detail = await self._fetch_from_learn(pid)
            if detail:
                results[pid] = detail
                await self._store_in_cache(pid, detail)

        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _from_catalog(policy_id: str, definition: Dict[str, str]) -> Dict[str, Any]:
        """Build a detail dict from a local catalog definition."""
        return {
            "policy_id": policy_id,
            "display_name": definition.get("display_name", ""),
            "description": definition.get("description", ""),
            "category": definition.get("category", ""),
            "learn_url": _portal_definition_url(policy_id),
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
    async def _fetch_from_learn(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Search Microsoft Learn for a single policy by GUID."""
        try:
            policies = await self.learn_client.search_azure_policies(
                control_name=policy_id,
                description=f"Azure Policy definition {policy_id}",
                domain=None,
            )
            for p in policies:
                if p.get("policy_id") == policy_id:
                    return {
                        "policy_id": policy_id,
                        "display_name": p.get("policy_name", ""),
                        "description": p.get("description", ""),
                        "learn_url": p.get("learn_url", ""),
                        "cached_at": datetime.now(timezone.utc).isoformat(),
                    }
            # No exact match — store a stub so we don't keep searching
            return {
                "policy_id": policy_id,
                "display_name": f"Policy {policy_id}",
                "description": "",
                "learn_url": f"https://learn.microsoft.com/en-us/azure/governance/policy/",
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.warning(f"Learn lookup failed for {policy_id}: {e}")
            return None

    async def _store_in_cache(self, policy_id: str, detail: Dict[str, Any]) -> None:
        """Upsert policy detail into Cosmos cache."""
        if not cosmos_client.database:
            return
        try:
            doc = {
                "id": policy_id,
                "policy_id": policy_id,
                **detail,
            }
            await cosmos_client.upsert_document(self.container, doc)
        except Exception as e:
            logger.warning(f"Failed to cache policy {policy_id}: {e}")

    @staticmethod
    def _doc_to_detail(doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "policy_id": doc.get("policy_id", doc.get("id", "")),
            "display_name": doc.get("display_name", ""),
            "description": doc.get("description", ""),
            "category": doc.get("category", ""),
            "learn_url": doc.get("learn_url", ""),
            "cached_at": doc.get("cached_at", ""),
        }


# Singleton
_service: Optional[PolicyCacheService] = None


def get_policy_cache_service() -> PolicyCacheService:
    global _service
    if _service is None:
        _service = PolicyCacheService()
    return _service
