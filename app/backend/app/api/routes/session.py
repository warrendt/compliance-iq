"""
Session persistence endpoints — save and restore critical frontend session
state so that controls, mappings, and policy decisions survive page
navigation and browser refreshes.

State is persisted to Cosmos DB in the ``user-sessions`` container.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.cosmos_client import cosmos_client

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


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/save")
async def save_session(req: SessionSaveRequest):
    """Persist critical session state to Cosmos DB."""
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")

    # Ensure the container exists
    await cosmos_client.ensure_container(
        CONTAINER_NAME,
        partition_key_paths=["/session_id"],
        default_ttl=SESSION_TTL_SECONDS,
    )

    doc = {
        "id": req.session_id,
        "session_id": req.session_id,
        "controls": req.controls,
        "mappings": req.mappings,
        "framework_name": req.framework_name,
        "policy_decisions": req.policy_decisions,
        "generated_policy": req.generated_policy,
        "selected_platform": req.selected_platform,
        "platform_display_name": req.platform_display_name,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }

    await cosmos_client.upsert_document(CONTAINER_NAME, doc)

    logger.info(
        "session_saved",
        extra={
            "session_id": req.session_id,
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


@router.get("/{session_id}")
async def load_session(session_id: str):
    """Restore a previously saved session from Cosmos DB."""
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

    return {
        "session_id": doc.get("session_id"),
        "controls": doc.get("controls", []),
        "mappings": doc.get("mappings", []),
        "framework_name": doc.get("framework_name", ""),
        "policy_decisions": doc.get("policy_decisions", {}),
        "generated_policy": doc.get("generated_policy"),
        "selected_platform": doc.get("selected_platform", "azure_defender"),
        "platform_display_name": doc.get("platform_display_name", "Microsoft Defender for Cloud"),
        "saved_at": doc.get("saved_at"),
    }
