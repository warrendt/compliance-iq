"""
Policy version service.

Manages immutable, per-user policy-initiative version history in the
``policy-versions`` Cosmos container (partitioned by ``/userId``).

Versions are never mutated. ``revert_to_version`` does not roll back in place —
it creates a *new* version that copies the target's ``artifact_payload`` and
records lineage, preserving the full audit trail.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.db.cosmos_client import cosmos_client
from app.models.db_models import PolicyVersionDocument

logger = logging.getLogger(__name__)


def _container() -> str:
    return cosmos_client.POLICY_VERSIONS


def _require_db() -> None:
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")


async def _ensure() -> None:
    await cosmos_client.ensure_container(
        _container(),
        partition_key_paths=["/userId"],
    )


async def _next_version_number(user_id: str) -> int:
    """Return the next version number for a user (max existing + 1).

    Uses a lightweight aggregate query so we don't read every prior payload.
    """
    rows = await cosmos_client.query_documents(
        _container(),
        query="SELECT VALUE MAX(c.version_number) FROM c WHERE c.userId = @userId",
        parameters=[{"name": "@userId", "value": user_id}],
        partition_key=user_id,
    )
    current_max = rows[0] if rows else None
    if current_max is None:
        return 1
    return int(current_max) + 1


async def create_version(
    user_id: str,
    artifact_payload: Dict[str, Any],
    parent_version: Optional[int] = None,
    status: str = "active",
    source_comparison_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create and persist a new immutable policy version. Returns the stored doc."""
    _require_db()
    await _ensure()

    version_number = await _next_version_number(user_id)

    doc = PolicyVersionDocument(
        userId=user_id,
        version_number=version_number,
        parent_version=parent_version,
        artifact_payload=artifact_payload or {},
        status=status,
        sourceComparisonId=source_comparison_id,
        metadata=metadata or {},
    )
    body = doc.model_dump(mode="json")

    result = await cosmos_client.insert_document(_container(), body)
    logger.info(
        "policy_version_created",
        extra={"userId": user_id, "version_number": version_number},
    )
    return result


async def list_versions(user_id: str) -> List[Dict[str, Any]]:
    """Return all versions for a user, oldest first."""
    _require_db()
    await _ensure()

    return await cosmos_client.query_documents(
        _container(),
        query=(
            "SELECT * FROM c WHERE c.userId = @userId "
            "ORDER BY c.version_number ASC"
        ),
        parameters=[{"name": "@userId", "value": user_id}],
        partition_key=user_id,
    )


async def get_version(user_id: str, version_id: str) -> Optional[Dict[str, Any]]:
    """Return a single version document by id, or None if not found."""
    _require_db()
    await _ensure()

    return await cosmos_client.get_document(_container(), version_id, partition_key=user_id)


async def revert_to_version(user_id: str, target_version_id: str) -> Dict[str, Any]:
    """Revert by creating a NEW version that copies the target's payload.

    The target document is never mutated. Raises 404 if the target is missing.
    """
    target = await get_version(user_id, target_version_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target version not found")

    target_number = target.get("version_number")
    new_version = await create_version(
        user_id=user_id,
        artifact_payload=target.get("artifact_payload", {}),
        parent_version=target_number,
        status="active",
        source_comparison_id=target.get("sourceComparisonId"),
        metadata={
            "reverted_from_id": target_version_id,
            "reverted_from_version": target_number,
        },
    )
    logger.info(
        "policy_version_reverted",
        extra={
            "userId": user_id,
            "from_version": target_number,
            "new_version": new_version.get("version_number"),
        },
    )
    return new_version
