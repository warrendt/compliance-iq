"""
Policy version service.

Manages immutable, per-user policy-initiative version history in the
``policy-versions`` Cosmos container (partitioned by ``/userId``).

Versions are never mutated. ``revert_to_version`` does not roll back in place —
it creates a *new* version that copies the target's ``artifact_payload`` and
records lineage, preserving the full audit trail.
"""

import logging
import json
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


def _policy_name(metadata: Dict[str, Any], artifact_payload: Dict[str, Any]) -> str:
    """Select the policy name that owns a semantic-version stream."""
    if name := metadata.get("policy_name"):
        return str(name)

    source = metadata.get("source", "initiative")
    framework_name = artifact_payload.get(
        "framework_name",
        metadata.get("framework_name", "initiative"),
    )
    if source == "slz_initiative":
        return f"{framework_name} SLZ"
    return str(artifact_payload.get("initiative_id") or framework_name)


def _version_stream(metadata: Dict[str, Any], artifact_payload: Dict[str, Any]) -> str:
    """Build a stable type-and-name key that isolates version histories."""
    source = str(metadata.get("source", "initiative"))
    normalized_name = "".join(
        char.lower() if char.isalnum() else "-"
        for char in _policy_name(metadata, artifact_payload)
    ).strip("-")
    return f"{source}:{normalized_name or 'initiative'}"


def _definition_identities(artifact_payload: Dict[str, Any]) -> frozenset[str]:
    """Return stable policy-definition identities from every initiative file."""
    identities: set[str] = set()
    for file in artifact_payload.get("files", []):
        if not str(file.get("name", "")).endswith("_initiative.json"):
            continue
        try:
            definition = json.loads(file.get("content", "{}"))
        except (TypeError, json.JSONDecodeError):
            continue
        for policy in definition.get("properties", {}).get("policyDefinitions", []):
            policy_id = policy.get("policyDefinitionId", "")
            reference_id = policy.get("policyDefinitionReferenceId", "")
            identities.add(f"{file['name']}:{policy_id}:{reference_id}")
    return frozenset(identities)


def _semantic_tuple(value: str) -> tuple[int, int, int]:
    """Parse a semantic version stored by this service."""
    parts = value.split(".")
    if len(parts) != 3:
        return (1, 0, 0)
    try:
        major, minor, patch = (int(part) for part in parts)
        return major, minor, patch
    except ValueError:
        return (1, 0, 0)


def _semantic_version_for(document: Dict[str, Any]) -> tuple[int, int, int]:
    """Read a semantic version, treating older version records as 1.0.0."""
    return _semantic_tuple(str(document.get("semantic_version", "1.0.0")))


def _next_semantic_version(
    previous: Optional[Dict[str, Any]],
    artifact_payload: Dict[str, Any],
) -> tuple[str, str]:
    """Classify a policy change as major, minor, or patch."""
    if previous is None:
        return "1.0.0", "initial"

    major, minor, patch = _semantic_version_for(previous)
    previous_definitions = _definition_identities(previous.get("artifact_payload", {}))
    current_definitions = _definition_identities(artifact_payload)

    if previous_definitions - current_definitions:
        return f"{major + 1}.0.0", "major"
    if current_definitions - previous_definitions:
        return f"{major}.{minor + 1}.0", "minor"
    return f"{major}.{minor}.{patch + 1}", "patch"


async def _latest_version_in_stream(
    user_id: str,
    version_stream: str,
    source: str,
    framework_name: str,
) -> Optional[Dict[str, Any]]:
    """Load the newest version in a stream, including pre-semver records."""
    rows = await cosmos_client.query_documents(
        _container(),
        query=(
            "SELECT TOP 1 * FROM c WHERE c.userId = @userId AND "
            "(c.version_stream = @versionStream OR "
            "(NOT IS_DEFINED(c.version_stream) AND c.metadata.source = @source "
            "AND c.metadata.framework_name = @frameworkName)) "
            "ORDER BY c.timestamp DESC"
        ),
        parameters=[
            {"name": "@userId", "value": user_id},
            {"name": "@versionStream", "value": version_stream},
            {"name": "@source", "value": source},
            {"name": "@frameworkName", "value": framework_name},
        ],
        partition_key=user_id,
    )
    return rows[0] if rows and isinstance(rows[0], dict) else None


def _add_legacy_semantic_versions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Present older numeric records as independent semantic-version streams."""
    legacy_groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if row.get("semantic_version"):
            continue
        metadata = row.get("metadata") or {}
        stream = _version_stream(metadata, {})
        legacy_groups.setdefault(stream, []).append(row)

    for group in legacy_groups.values():
        for index, row in enumerate(sorted(group, key=lambda item: item.get("timestamp", ""))):
            row["semantic_version"] = f"1.0.{index}"
            row["version_stream"] = _version_stream(row.get("metadata") or {}, {})
    return rows


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

    version_metadata = dict(metadata or {})
    policy_name = _policy_name(version_metadata, artifact_payload)
    version_metadata["policy_name"] = policy_name
    version_stream = _version_stream(version_metadata, artifact_payload)
    previous = await _latest_version_in_stream(
        user_id=user_id,
        version_stream=version_stream,
        source=str(version_metadata.get("source", "initiative")),
        framework_name=str(artifact_payload.get("framework_name", "")),
    )
    semantic_version, change_type = _next_semantic_version(previous, artifact_payload)
    version_metadata["version_change"] = change_type
    version_number = await _next_version_number(user_id)

    doc = PolicyVersionDocument(
        userId=user_id,
        version_number=version_number,
        semantic_version=semantic_version,
        version_stream=version_stream,
        parent_version=parent_version,
        artifact_payload=artifact_payload or {},
        status=status,
        sourceComparisonId=source_comparison_id,
        metadata=version_metadata,
    )
    body = doc.model_dump(mode="json")

    result = await cosmos_client.insert_document(_container(), body)
    logger.info(
        "policy_version_created",
        extra={
            "userId": user_id,
            "version_number": version_number,
            "semantic_version": semantic_version,
            "version_stream": version_stream,
        },
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
            "ORDER BY c.timestamp ASC"
        ),
        parameters=[{"name": "@userId", "value": user_id}],
        partition_key=user_id,
    )


async def list_version_summaries(user_id: str) -> List[Dict[str, Any]]:
    """Return lightweight version metadata (no artifact payloads), newest first.

    Avoids returning the full ``artifact_payload`` (potentially large file bundles)
    for every version when only the history list is needed.
    """
    _require_db()
    await _ensure()

    rows = await cosmos_client.query_documents(
        _container(),
        query=(
            "SELECT c.id, c.version_number, c.semantic_version, c.version_stream, "
            "c.parent_version, c.status, c.sourceComparisonId, c.metadata, c.timestamp "
            "FROM c WHERE c.userId = @userId ORDER BY c.timestamp DESC"
        ),
        parameters=[{"name": "@userId", "value": user_id}],
        partition_key=user_id,
    )
    return _add_legacy_semantic_versions(rows)


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
            **(target.get("metadata") or {}),
            "reverted_from_id": target_version_id,
            "reverted_from_version": target_number,
            "reverted_from_semantic_version": target.get("semantic_version", "1.0.0"),
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
