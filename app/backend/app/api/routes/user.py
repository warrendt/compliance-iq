"""
User profile and history endpoints.

Provides per-user profile management (read/update) and history queries
covering uploads, AI mappings, and policy exports.  All endpoints require
a valid user identity resolved by the ``get_current_user`` dependency.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth.azure_ad_auth import User, get_current_user
from app.db.cosmos_client import cosmos_client

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["user"])

_PROFILE_CONTAINER = "user-profiles"
_AUDIT_CONTAINER = "audit-logs"
_UPLOADS_CONTAINER = "user-uploads"
_MAPPINGS_CONTAINER = "mapping-results"
_ARTIFACTS_CONTAINER = "generated-artifacts"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class UserProfileResponse(BaseModel):
    """Public user profile."""
    userId: str
    displayName: str = ""
    email: str = ""
    preferredPlatform: str = "azure_defender"
    uploadCount: int = 0
    mappingCount: int = 0
    exportCount: int = 0
    lastActive: Optional[str] = None


class UserProfileUpdateRequest(BaseModel):
    """Fields the user may update in their profile."""
    displayName: Optional[str] = None
    preferredPlatform: Optional[str] = None


class HistoryItem(BaseModel):
    """A single history event."""
    id: str
    type: str  # 'upload' | 'mapping' | 'export'
    timestamp: str
    summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_profile(user: User) -> Dict[str, Any]:
    """Return the Cosmos DB profile document, creating it on first access."""
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")

    await cosmos_client.ensure_container(
        _PROFILE_CONTAINER,
        partition_key_paths=["/userId"],
    )

    doc = await cosmos_client.get_document(_PROFILE_CONTAINER, user.email, user.email)
    if doc is None:
        doc = {
            "id": user.email,
            "userId": user.email,
            "displayName": user.name,
            "email": user.email,
            "preferredPlatform": "azure_defender",
            "uploadCount": 0,
            "mappingCount": 0,
            "exportCount": 0,
            "lastActive": datetime.now(timezone.utc).isoformat(),
        }
        await cosmos_client.upsert_document(_PROFILE_CONTAINER, doc)
    return doc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Return the current user's profile, creating it if it does not exist."""
    doc = await _get_or_create_profile(user)
    return UserProfileResponse(
        userId=doc.get("userId", user.email),
        displayName=doc.get("displayName", user.name),
        email=doc.get("email", user.email),
        preferredPlatform=doc.get("preferredPlatform", "azure_defender"),
        uploadCount=doc.get("uploadCount", 0),
        mappingCount=doc.get("mappingCount", 0),
        exportCount=doc.get("exportCount", 0),
        lastActive=doc.get("lastActive"),
    )


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    request: Request,
    body: UserProfileUpdateRequest,
    user: User = Depends(get_current_user),
):
    """Update mutable profile fields (displayName, preferredPlatform)."""
    doc = await _get_or_create_profile(user)

    if body.displayName is not None:
        doc["displayName"] = body.displayName
    if body.preferredPlatform is not None:
        doc["preferredPlatform"] = body.preferredPlatform

    doc["lastActive"] = datetime.now(timezone.utc).isoformat()
    await cosmos_client.upsert_document(_PROFILE_CONTAINER, doc)

    logger.info("profile_updated", extra={"userId": user.email})
    return UserProfileResponse(**{
        k: doc.get(k, "")
        for k in UserProfileResponse.model_fields
    })


@router.get("/history", response_model=List[HistoryItem])
async def get_history(
    request: Request,
    limit: int = 50,
    event_type: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """Return a unified activity history (uploads + mappings + exports) for the user.

    Query params:
    - ``limit``: Max number of events (default 50, max 200).
    - ``event_type``: Optional filter — ``upload``, ``mapping``, or ``export``.
    """
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")

    limit = min(limit, 200)

    await cosmos_client.ensure_container(
        _AUDIT_CONTAINER,
        partition_key_paths=["/userId"],
        default_ttl=7776000,
    )

    type_filter = ""
    params: List[Dict[str, Any]] = [{"name": "@userId", "value": user.email}]
    if event_type:
        type_filter = " AND c.resourceType = @resourceType"
        params.append({"name": "@resourceType", "value": event_type})

    query = (
        f"SELECT TOP {limit} c.id, c.action, c.resourceType, c.metadata, c.timestamp "
        f"FROM c WHERE c.userId = @userId{type_filter} "
        f"ORDER BY c.timestamp DESC"
    )

    try:
        items = await cosmos_client.query_documents(
            _AUDIT_CONTAINER,
            query=query,
            parameters=params,
            partition_key=user.email,
        )
    except Exception:
        items = []

    results: List[HistoryItem] = []
    for item in items:
        ts = item.get("timestamp", "")
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        meta = item.get("metadata", {})
        action = item.get("action", item.get("resourceType", "unknown"))
        summary = meta.get("summary", action)
        results.append(HistoryItem(
            id=item.get("id", ""),
            type=item.get("resourceType", "unknown"),
            timestamp=str(ts),
            summary=summary,
            metadata=meta,
        ))
    return results


@router.get("/uploads", response_model=List[Dict[str, Any]])
async def get_uploads(
    request: Request,
    limit: int = 50,
    user: User = Depends(get_current_user),
):
    """Return the user's uploaded file records."""
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")

    limit = min(limit, 200)

    await cosmos_client.ensure_container(
        _UPLOADS_CONTAINER,
        partition_key_paths=["/userId"],
        default_ttl=2592000,
    )

    query = (
        f"SELECT TOP {limit} c.id, c.fileName, c.fileSize, c.fileType, "
        f"c.rowCount, c.columnNames, c.timestamp "
        f"FROM c WHERE c.userId = @userId ORDER BY c.timestamp DESC"
    )

    try:
        items = await cosmos_client.query_documents(
            _UPLOADS_CONTAINER,
            query=query,
            parameters=[{"name": "@userId", "value": user.email}],
            partition_key=user.email,
        )
    except Exception:
        items = []

    return items


@router.get("/mappings", response_model=List[Dict[str, Any]])
async def get_mappings(
    request: Request,
    limit: int = 50,
    user: User = Depends(get_current_user),
):
    """Return the user's AI mapping results (most recent first)."""
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")

    limit = min(limit, 200)

    await cosmos_client.ensure_container(
        _MAPPINGS_CONTAINER,
        partition_key_paths=["/userId", "/date"],
        default_ttl=2592000,
    )

    query = (
        f"SELECT TOP {limit} c.id, c.controlId, c.controlName, c.framework, "
        f"c.confidence, c.timestamp "
        f"FROM c WHERE c.userId = @userId ORDER BY c.timestamp DESC"
    )

    try:
        items = await cosmos_client.query_documents(
            _MAPPINGS_CONTAINER,
            query=query,
            parameters=[{"name": "@userId", "value": user.email}],
        )
    except Exception:
        items = []

    return items


@router.get("/exports", response_model=List[Dict[str, Any]])
async def get_exports(
    request: Request,
    limit: int = 50,
    user: User = Depends(get_current_user),
):
    """Return the user's policy export records (most recent first)."""
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")

    limit = min(limit, 200)

    await cosmos_client.ensure_container(
        _ARTIFACTS_CONTAINER,
        partition_key_paths=["/session_id"],
        default_ttl=2592000,
    )

    query = (
        f"SELECT TOP {limit} c.id, c.artifactType, c.framework, "
        f"c.controlCount, c.fileName, c.fileSize, c.timestamp "
        f"FROM c WHERE c.userId = @userId ORDER BY c.timestamp DESC"
    )

    try:
        items = await cosmos_client.query_documents(
            _ARTIFACTS_CONTAINER,
            query=query,
            parameters=[{"name": "@userId", "value": user.email}],
        )
    except Exception:
        items = []

    return items
