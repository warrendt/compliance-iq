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
    pdf_extraction: Optional[Dict[str, Any]] = None
    pdf_extraction_file_name: Optional[str] = None
    pdf_extraction_job_id: Optional[str] = None
    pdf_extraction_job_status: Optional[str] = None
    pdf_extraction_job_progress: Optional[int] = None
    pdf_extraction_job_stage: Optional[str] = None
    clear_pdf_extraction: bool = False


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

    existing = await cosmos_client.get_document(CONTAINER_NAME, req.session_id, partition_key=req.session_id) or {}

    if req.clear_pdf_extraction:
        pdf_extraction = None
        pdf_extraction_file_name = None
        pdf_extraction_saved_at = None
        pdf_extraction_job_id = None
        pdf_extraction_job_status = None
        pdf_extraction_job_progress = 0
        pdf_extraction_job_stage = None
    else:
        pdf_extraction = req.pdf_extraction if req.pdf_extraction is not None else existing.get("pdf_extraction")
        pdf_extraction_file_name = (
            req.pdf_extraction_file_name
            if req.pdf_extraction_file_name is not None
            else existing.get("pdf_extraction_file_name")
        )
        pdf_extraction_saved_at = (
            datetime.now(timezone.utc).isoformat()
            if req.pdf_extraction is not None
            else existing.get("pdf_extraction_saved_at")
        )
        pdf_extraction_job_id = (
            req.pdf_extraction_job_id
            if req.pdf_extraction_job_id is not None
            else existing.get("pdf_extraction_job_id")
        )
        pdf_extraction_job_status = (
            req.pdf_extraction_job_status
            if req.pdf_extraction_job_status is not None
            else existing.get("pdf_extraction_job_status")
        )
        pdf_extraction_job_progress = (
            req.pdf_extraction_job_progress
            if req.pdf_extraction_job_progress is not None
            else existing.get("pdf_extraction_job_progress")
        )
        pdf_extraction_job_stage = (
            req.pdf_extraction_job_stage
            if req.pdf_extraction_job_stage is not None
            else existing.get("pdf_extraction_job_stage")
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
        "pdf_extraction": pdf_extraction,
        "pdf_extraction_file_name": pdf_extraction_file_name,
        "pdf_extraction_saved_at": pdf_extraction_saved_at,
        "pdf_extraction_job_id": pdf_extraction_job_id,
        "pdf_extraction_job_status": pdf_extraction_job_status,
        "pdf_extraction_job_progress": pdf_extraction_job_progress,
        "pdf_extraction_job_stage": pdf_extraction_job_stage,
        "pdf_extraction_job_updated_at": datetime.now(timezone.utc).isoformat(),
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
        "pdf_extraction": doc.get("pdf_extraction"),
        "pdf_extraction_file_name": doc.get("pdf_extraction_file_name"),
        "pdf_extraction_saved_at": doc.get("pdf_extraction_saved_at"),
        "pdf_extraction_job_id": doc.get("pdf_extraction_job_id"),
        "pdf_extraction_job_status": doc.get("pdf_extraction_job_status"),
        "pdf_extraction_job_progress": doc.get("pdf_extraction_job_progress"),
        "pdf_extraction_job_stage": doc.get("pdf_extraction_job_stage"),
        "pdf_extraction_job_updated_at": doc.get("pdf_extraction_job_updated_at"),
        "saved_at": doc.get("saved_at"),
    }
