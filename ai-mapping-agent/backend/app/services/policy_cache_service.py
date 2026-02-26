"""
Policy Cache Service.
Caches Azure Policy detail lookups in Cosmos DB with Microsoft Learn fallback.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.db import cosmos_client
from app.services.microsoft_learn_client import get_microsoft_learn_client

logger = logging.getLogger(__name__)

GUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
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

        # --- 1. Cosmos cache hit pass ---
        if cosmos_client.database:
            for pid in valid_ids:
                try:
                    doc = await cosmos_client.get_document(
                        self.container, pid, partition_key=pid
                    )
                    if doc:
                        results[pid] = self._doc_to_detail(doc)
                    else:
                        miss_ids.append(pid)
                except Exception:
                    miss_ids.append(pid)
        else:
            miss_ids = valid_ids

        if not miss_ids:
            logger.info("policy_cache_hit_all", extra={"count": len(results)})
            return results

        # --- 2. Microsoft Learn fallback for cache misses ---
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
                        "cached_at": datetime.utcnow().isoformat(),
                    }
            # No exact match — store a stub so we don't keep searching
            return {
                "policy_id": policy_id,
                "display_name": f"Policy {policy_id}",
                "description": "",
                "learn_url": f"https://learn.microsoft.com/en-us/azure/governance/policy/",
                "cached_at": datetime.utcnow().isoformat(),
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
