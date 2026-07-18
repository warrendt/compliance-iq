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
from app.services import activity_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["user"])

_PROFILE_CONTAINER = "user-profiles"
_AUDIT_CONTAINER = "audit-logs"
_UPLOADS_CONTAINER = "user-uploads"
_MAPPINGS_CONTAINER = "mapping-results"
_ARTIFACTS_CONTAINER = "generated-artifacts"
_ARTIFACTS_TTL = 7776000  # 90 days — matches activity_service._ARTIFACT_TTL_SECONDS


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
    else:
        # Hide low-value background session autosaves ("session.saved") from the
        # user-facing activity feed; they are noise, not meaningful actions.
        # (Still queryable explicitly via ?event_type=session.)
        type_filter = " AND c.resourceType <> 'session'"

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
        f"c.category, c.version, c.controlCount, "
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


@router.get("/uploads/{upload_id}", response_model=Dict[str, Any])
async def get_upload_detail(
    request: Request,
    upload_id: str,
    user: User = Depends(get_current_user),
):
    """Return a single stored control set including its parsed ``controls``.

    Scoped to control sets (``category == 'controls'``) so the workspace can
    rebuild a downloadable CSV. USER_UPLOADS is partitioned by ``/userId`` so
    this is an authorization-safe point read; identity is re-verified anyway.
    """
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        doc = await cosmos_client.get_document(
            _UPLOADS_CONTAINER, upload_id, user.email
        )
    except Exception:
        doc = None

    if (
        not doc
        or doc.get("userId") != user.email
        or doc.get("category") != activity_service.CATEGORY_CONTROLS
    ):
        raise HTTPException(status_code=404, detail="Control set not found")

    return {
        "id": doc.get("id"),
        "fileName": doc.get("fileName", ""),
        "version": doc.get("version", 1),
        "controls": doc.get("controls") or [],
        "columnNames": doc.get("columnNames") or [],
        "rowCount": doc.get("rowCount", 0),
        "controlCount": doc.get("controlCount", 0),
        "timestamp": doc.get("timestamp", ""),
    }
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
        # mapping-results uses a composite partition key (/userId, /date).
        # Querying across all dates for the user requires a cross-partition
        # scan, so no single partition_key value is passed here.
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
        default_ttl=_ARTIFACTS_TTL,
    )

    query = (
        f"SELECT TOP {limit} c.id, c.session_id, c.artifactType, c.framework, "
        f"c.controlCount, c.fileName, c.fileSize, c.contentAvailable, c.timestamp "
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


@router.get("/exports/{export_id}", response_model=Dict[str, Any])
async def get_export_detail(
    request: Request,
    export_id: str,
    session_id: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """Return a single export artifact including its downloadable ``content``.

    GENERATED_ARTIFACTS is partitioned by ``/session_id``; when the caller knows
    the session id (from the list projection) we do an efficient point read,
    otherwise we fall back to a cross-partition lookup by id. Identity is always
    re-verified against the authenticated principal before returning content, so
    a user can never download another user's artifact.
    """
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")

    doc: Optional[Dict[str, Any]] = None
    if session_id:
        try:
            doc = await cosmos_client.get_document(
                _ARTIFACTS_CONTAINER, export_id, session_id
            )
        except Exception:
            doc = None
    if doc is None:
        try:
            items = await cosmos_client.query_documents(
                _ARTIFACTS_CONTAINER,
                query="SELECT * FROM c WHERE c.id = @id AND c.userId = @userId",
                parameters=[
                    {"name": "@id", "value": export_id},
                    {"name": "@userId", "value": user.email},
                ],
            )
            doc = items[0] if items else None
        except Exception:
            doc = None

    if not doc or doc.get("userId") != user.email:
        raise HTTPException(status_code=404, detail="Export not found")

    content = doc.get("content") or ""
    return {
        "id": doc.get("id"),
        "fileName": doc.get("fileName", ""),
        "framework": doc.get("framework", ""),
        "artifactType": doc.get("artifactType", ""),
        "content": content,
        "hasContent": bool(content),
        "contentSkippedReason": doc.get("contentSkippedReason", ""),
        "timestamp": doc.get("timestamp", ""),
    }


# ---------------------------------------------------------------------------
# Activity recording (write) endpoints
#
# The frontend orchestrates the pipeline and knows when each milestone happens,
# so it posts here at each step. Identity is ALWAYS taken from the authenticated
# principal (never the request body), so a client cannot forge another user's
# activity. All recording is best-effort inside activity_service.
# ---------------------------------------------------------------------------

class RecordUploadRequest(BaseModel):
    """Record an uploaded document or a loaded control set."""
    fileName: str
    fileType: str = "text/csv"
    category: str = activity_service.CATEGORY_DOCUMENT  # 'document' | 'controls'
    fileSize: int = 0
    rowCount: int = 0
    columnNames: List[str] = Field(default_factory=list)
    controls: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecordMappingsRequest(BaseModel):
    """Record a batch of AI mapping results."""
    framework: str
    mappings: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecordExportRequest(BaseModel):
    """Record a generated/exported policy artifact."""
    framework: str
    artifactType: str = "initiative"
    controlCount: int = 0
    fileName: str = ""
    fileSize: int = 0
    sessionId: Optional[str] = None
    content: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecordActivityRequest(BaseModel):
    """Record a generic activity (e.g. an edit) into the unified feed."""
    action: str
    resourceType: str = "edit"
    summary: str
    resourceId: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.post("/uploads", status_code=201)
async def record_upload(
    request: Request,
    body: RecordUploadRequest,
    user: User = Depends(get_current_user),
):
    """Record a document upload or control-set load for the current user."""
    category = (
        activity_service.CATEGORY_CONTROLS
        if body.category == activity_service.CATEGORY_CONTROLS
        else activity_service.CATEGORY_DOCUMENT
    )
    doc = await activity_service.record_upload(
        user,
        file_name=body.fileName,
        file_type=body.fileType,
        category=category,
        file_size=body.fileSize,
        row_count=body.rowCount,
        column_names=body.columnNames,
        controls=body.controls,
        metadata=body.metadata,
    )
    return {"status": "recorded", "id": doc.get("id"), "version": doc.get("version")}


@router.post("/mappings", status_code=201)
async def record_mappings(
    request: Request,
    body: RecordMappingsRequest,
    user: User = Depends(get_current_user),
):
    """Record a batch of AI mapping results for the current user."""
    written = await activity_service.record_mappings(
        user,
        framework=body.framework,
        mappings=body.mappings,
        metadata=body.metadata,
    )
    return {"status": "recorded", "written": written, "received": len(body.mappings)}


@router.post("/exports", status_code=201)
async def record_export(
    request: Request,
    body: RecordExportRequest,
    user: User = Depends(get_current_user),
):
    """Record a generated/exported policy artifact for the current user."""
    doc = await activity_service.record_export(
        user,
        framework=body.framework,
        artifact_type=body.artifactType,
        control_count=body.controlCount,
        file_name=body.fileName,
        file_size=body.fileSize,
        session_id=body.sessionId,
        content=body.content,
        metadata=body.metadata,
    )
    return {"status": "recorded", "id": doc.get("id")}


@router.post("/activity", status_code=201)
async def record_activity(
    request: Request,
    body: RecordActivityRequest,
    user: User = Depends(get_current_user),
):
    """Record a generic activity (e.g. an edit) into the unified history feed."""
    await activity_service.record_activity(
        user,
        action=body.action,
        resource_type=body.resourceType,
        summary=body.summary,
        resource_id=body.resourceId,
        metadata=body.metadata,
    )
    return {"status": "recorded"}
