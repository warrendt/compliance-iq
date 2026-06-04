"""
API routes for per-user policy initiative version history.

Versions are immutable. A revert never mutates the target — it creates a new
version that copies the target's artifact bundle (see ``version_service``).

All reads/writes are scoped to the authenticated user (``userId == user.email``);
cross-user access returns 404.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth.azure_ad_auth import User, get_current_user
from app.db.cosmos_client import cosmos_client
from app.services import audit_service, version_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/versions", tags=["Versions"])


def _require_db() -> None:
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")


@router.get("")
async def list_versions(user: User = Depends(get_current_user)):
    """List the current user's policy versions (newest first, metadata only)."""
    _require_db()
    rows = await version_service.list_version_summaries(user.email)
    return {"versions": rows}


@router.get("/{version_id}")
async def get_version(version_id: str, user: User = Depends(get_current_user)):
    """Return a single version document (including its artifact bundle)."""
    _require_db()
    doc = await version_service.get_version(user.email, version_id)
    if not doc or (doc.get("userId") and doc["userId"] != user.email):
        raise HTTPException(status_code=404, detail="Version not found")
    return {k: v for k, v in doc.items() if not k.startswith("_")}


@router.get("/{version_id}/download")
async def download_version(version_id: str, user: User = Depends(get_current_user)):
    """Return just the artifact payload (files) for a version, for download."""
    _require_db()
    doc = await version_service.get_version(user.email, version_id)
    if not doc or (doc.get("userId") and doc["userId"] != user.email):
        raise HTTPException(status_code=404, detail="Version not found")
    await audit_service.write_audit(
        user,
        action="version.download",
        resource_type=audit_service.RESOURCE_POLICY_VERSION,
        resource_id=version_id,
    )
    return doc.get("artifact_payload", {}) or {}


@router.post("/{version_id}/revert")
async def revert_version(version_id: str, user: User = Depends(get_current_user)):
    """Revert by creating a new version that copies the target's bundle."""
    _require_db()
    new_version = await version_service.revert_to_version(user.email, version_id)
    await audit_service.write_audit(
        user,
        action="version.revert",
        resource_type=audit_service.RESOURCE_POLICY_VERSION,
        resource_id=version_id,
        metadata={
            "new_version_id": new_version.get("id"),
            "new_version_number": new_version.get("version_number"),
        },
    )
    return {k: v for k, v in new_version.items() if not k.startswith("_")}
