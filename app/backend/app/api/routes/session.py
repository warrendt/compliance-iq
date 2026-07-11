"""
Session persistence endpoints — save and restore critical frontend session
state so that controls, mappings, and policy decisions survive page
navigation and browser refreshes.

State is persisted to Cosmos DB in the ``user-sessions`` container.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.azure_ad_auth import User, get_current_user
from app.db.cosmos_client import cosmos_client
from app.services import audit_service

import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session", tags=["session"])

CONTAINER_NAME = "user-sessions"
SESSION_TTL_SECONDS = 604800  # 7 days


# ── Models ────────────────────────────────────────────────────────────────

class SessionSaveRequest(BaseModel):
    """Payload for saving session state."""

    session_id: str = Field(..., description="Unique session identifier")
    controls: list = Field(default_factory=list)
    mappings: list = Field(default_factory=list)
    framework_name: str = ""
    policy_decisions: dict = Field(default_factory=dict)
    generated_policy: Optional[Dict[str, Any]] = None
    selected_platform: str = "azure_defender"
    platform_display_name: str = "Microsoft Defender for Cloud"
    mapping_job_id: Optional[str] = None
    mapping_in_progress: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/save")
async def save_session(req: SessionSaveRequest, user: User = Depends(get_current_user)):
    """Persist critical session state to Cosmos DB, scoped to the current user."""
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")

    # Ensure the container exists
    await cosmos_client.ensure_container(
        CONTAINER_NAME,
        partition_key_paths=["/session_id"],
        default_ttl=SESSION_TTL_SECONDS,
    )

    # Reject overwriting a session that belongs to a different user.
    existing = await cosmos_client.get_document(
        CONTAINER_NAME, req.session_id, partition_key=req.session_id
    )
    if existing is not None:
        owner = existing.get("userId")
        if owner and owner != user.email:
            raise HTTPException(status_code=404, detail="Session not found")

    doc = {
        "id": req.session_id,
        "session_id": req.session_id,
        "userId": user.email,
        "controls": req.controls,
        "mappings": req.mappings,
        "framework_name": req.framework_name,
        "policy_decisions": req.policy_decisions,
        "generated_policy": req.generated_policy,
        "selected_platform": req.selected_platform,
        "platform_display_name": req.platform_display_name,
        "mapping_job_id": req.mapping_job_id,
        "mapping_in_progress": req.mapping_in_progress,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }

    await cosmos_client.upsert_document(CONTAINER_NAME, doc)

    await audit_service.write_audit(
        user,
        action="session.saved",
        resource_type="session",
        resource_id=req.session_id,
        metadata={"controls": len(req.controls), "mappings": len(req.mappings)},
    )

    logger.info(
        "session_saved",
        extra={
            "session_id": req.session_id,
            "userId": user.email,
            "controls": len(req.controls),
            "mappings": len(req.mappings),
        },
    )

    return {
        "status": "saved",
        "session_id": req.session_id,
        "controls": len(req.controls),
        "mappings": len(req.mappings),
    }


def _session_response(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "session_id": doc.get("session_id"),
        "userId": doc.get("userId"),
        "controls": doc.get("controls", []),
        "mappings": doc.get("mappings", []),
        "framework_name": doc.get("framework_name", ""),
        "policy_decisions": doc.get("policy_decisions", {}),
        "generated_policy": doc.get("generated_policy"),
        "selected_platform": doc.get("selected_platform", "azure_defender"),
        "platform_display_name": doc.get(
            "platform_display_name", "Microsoft Defender for Cloud"
        ),
        "mapping_job_id": doc.get("mapping_job_id"),
        "mapping_in_progress": doc.get("mapping_in_progress", False),
        "saved_at": doc.get("saved_at"),
    }


@router.get("/latest")
async def load_latest_session(user: User = Depends(get_current_user)):
    """Restore the current user's most recently saved workflow session."""
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")

    await cosmos_client.ensure_container(
        CONTAINER_NAME,
        partition_key_paths=["/session_id"],
        default_ttl=SESSION_TTL_SECONDS,
    )
    documents = await cosmos_client.query_documents(
        CONTAINER_NAME,
        query=(
            "SELECT TOP 1 * FROM c WHERE c.userId = @userId "
            "ORDER BY c.saved_at DESC"
        ),
        parameters=[{"name": "@userId", "value": user.email}],
    )
    if not documents:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_response(documents[0])


@router.get("/{session_id}")
async def load_session(session_id: str, user: User = Depends(get_current_user)):
    """Restore a previously saved session, scoped to the current user."""
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")

    # Ensure the container exists
    await cosmos_client.ensure_container(
        CONTAINER_NAME,
        partition_key_paths=["/session_id"],
        default_ttl=SESSION_TTL_SECONDS,
    )

    doc = await cosmos_client.get_document(CONTAINER_NAME, session_id, partition_key=session_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Enforce per-user isolation. Legacy docs without a userId remain accessible
    # for back-compat; once re-saved they are stamped with the owner.
    owner = doc.get("userId")
    if owner and owner != user.email:
        raise HTTPException(status_code=404, detail="Session not found")

    return _session_response(doc)
