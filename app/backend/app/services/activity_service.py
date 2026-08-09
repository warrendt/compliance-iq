"""
Activity recording service — the single entry point for persisting everything a
user does across the workspace pipeline (documents, controls, AI mappings,
edits, policy exports/versions).

Each ``record_*`` helper performs up to three best-effort writes:

1. a rich document in the dedicated per-type Cosmos container (powers the
   Workspace tabs: Documents, Controls, Mappings, Exports),
2. an ``audit-logs`` entry (powers the unified ``/user/history`` activity feed),
3. a ``user-profiles`` counter bump (powers the Workspace activity summary).

The caller never supplies identity — ``userId`` is always the server-resolved
principal. All writes are best-effort: a failure here is logged but never raised,
so activity logging can never break the user's primary action.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from app.auth.azure_ad_auth import User
from app.db.cosmos_client import cosmos_client
from app.services import audit_service

logger = logging.getLogger(__name__)

# Upload categories — keep the two human-meaningful streams distinct so the
# Workspace can show "Documents" (PDFs/files) separately from "Controls" (the
# control sets a user loads and stores).
CATEGORY_DOCUMENT = "document"
CATEGORY_CONTROLS = "controls"

_UPLOAD_TTL_SECONDS = 2592000  # 30 days (matches the /user/uploads reader)
_MAPPING_TTL_SECONDS = 2592000  # 30 days
_ARTIFACT_TTL_SECONDS = 7776000  # 90 days

# Guard against Cosmos's 2MB item limit. Downloadable artifact content is
# measured in UTF-8 bytes; oversized payloads are dropped wholesale (never
# truncated mid-token, which would yield a corrupt download) and flagged so the
# workspace can explain why the artifact isn't downloadable.
_MAX_CONTENT_BYTES = 1_500_000

# Discriminator for the user-scoped export record (distinguishes it from the
# session-keyed `_persist_artifact` doc that shares the GENERATED_ARTIFACTS
# container but carries no userId).
_USER_EXPORT_DOC_KIND = "user_export_record"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _resolve_identity(user: Union[User, str]) -> tuple[str, str]:
    """Return ``(userId, displayName)`` from a principal or raw email string."""
    if isinstance(user, str):
        return user, user
    return (getattr(user, "email", "") or "", getattr(user, "name", "") or "")


def _ready() -> bool:
    return bool(cosmos_client and cosmos_client.database)


# ---------------------------------------------------------------------------
# Profile counters
# ---------------------------------------------------------------------------

async def _bump_profile(user: Union[User, str], field: str, inc: int = 1) -> None:
    """Increment a profile counter (uploadCount/mappingCount/exportCount).

    Creates the profile document on first activity so counters are never lost.
    """
    if not _ready() or inc <= 0:
        return

    user_id, display_name = _resolve_identity(user)
    if not user_id:
        return

    try:
        await cosmos_client.ensure_container(
            cosmos_client.USER_PROFILES,
            partition_key_paths=["/userId"],
        )
        doc = await cosmos_client.get_document(
            cosmos_client.USER_PROFILES, user_id, user_id
        )
        if doc is None:
            doc = {
                "id": user_id,
                "userId": user_id,
                "displayName": display_name,
                "email": user_id,
                "preferredPlatform": "azure_defender",
                "uploadCount": 0,
                "mappingCount": 0,
                "exportCount": 0,
            }
        doc[field] = int(doc.get(field, 0) or 0) + inc
        doc["lastActive"] = _now_iso()
        await cosmos_client.upsert_document(cosmos_client.USER_PROFILES, doc)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("profile counter bump failed (%s): %s", field, exc)


async def _next_version(user_id: str, file_name: str, category: str) -> int:
    """Return the next version number for a (user, fileName, category) tuple.

    Document version history (stream 6) is derived from prior uploads sharing the
    same file name and category.
    """
    if not _ready():
        return 1
    try:
        items = await cosmos_client.query_documents(
            cosmos_client.USER_UPLOADS,
            query=(
                "SELECT VALUE c.version FROM c WHERE c.userId = @userId "
                "AND c.fileName = @fileName AND c.category = @category"
            ),
            parameters=[
                {"name": "@userId", "value": user_id},
                {"name": "@fileName", "value": file_name},
                {"name": "@category", "value": category},
            ],
            partition_key=user_id,
        )
        versions = [int(v) for v in items if isinstance(v, (int, float))]
        return (max(versions) + 1) if versions else 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("version lookup failed for %s: %s", file_name, exc)
        return 1


# ---------------------------------------------------------------------------
# Uploads: documents (#3) + controls (#5) + versions (#6)
# ---------------------------------------------------------------------------

async def record_upload(
    user: Union[User, str],
    *,
    file_name: str,
    file_type: str,
    category: str = CATEGORY_DOCUMENT,
    file_size: int = 0,
    row_count: int = 0,
    column_names: Optional[List[str]] = None,
    controls: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record an uploaded document or control set, with version tracking.

    For control sets (``category='controls'``) the parsed ``controls`` payload is
    stored so the user's control library is retained per tenant (stream #5).
    """
    user_id, _ = _resolve_identity(user)
    column_names = column_names or []
    metadata = dict(metadata or {})

    version = await _next_version(user_id, file_name, category) if user_id else 1

    fingerprint = f"{file_name}:{file_size}:{row_count}:{version}"
    file_hash = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    doc: Dict[str, Any] = {
        "id": str(uuid4()),
        "userId": user_id,
        "fileName": file_name,
        "fileType": file_type,
        "fileSize": int(file_size or 0),
        "fileHash": file_hash,
        "category": category,
        "version": version,
        "rowCount": int(row_count or 0),
        "columnNames": column_names,
        "timestamp": _now_iso(),
    }
    if controls is not None:
        # Guard against oversized Cosmos items: cap stored controls.
        doc["controls"] = controls[:2000]
        doc["controlCount"] = len(controls)

    if _ready():
        try:
            await cosmos_client.ensure_container(
                cosmos_client.USER_UPLOADS,
                partition_key_paths=["/userId"],
                default_ttl=_UPLOAD_TTL_SECONDS,
            )
            await cosmos_client.upsert_document(
                cosmos_client.USER_UPLOADS, doc, partition_key=user_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("upload record failed for %s: %s", file_name, exc)

    label = "Loaded controls" if category == CATEGORY_CONTROLS else "Uploaded document"
    summary = f"{label} '{file_name}' (v{version})"
    if row_count:
        summary += f" — {row_count} rows"
    metadata.update({
        "summary": summary,
        "fileName": file_name,
        "category": category,
        "version": version,
        "rowCount": int(row_count or 0),
    })
    await audit_service.write_audit(
        user,
        action=f"upload.{category}",
        resource_type=audit_service.RESOURCE_UPLOAD,
        resource_id=doc.get("id"),
        metadata=metadata,
    )
    await _bump_profile(user, "uploadCount", 1)
    return doc


# ---------------------------------------------------------------------------
# AI mappings (#1/#2 activity, mapping stream)
# ---------------------------------------------------------------------------

async def record_mappings(
    user: Union[User, str],
    *,
    framework: str,
    mappings: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """Persist a batch of AI mapping results for the user.

    Each mapping becomes one ``mapping-results`` document; a single audit entry
    summarises the run and ``mappingCount`` is bumped by the number of controls.
    Returns the number of mapping documents written.

    The audit entry distinguishes *mapped* from *persisted*. It previously did
    not: ``count = written or len(mappings)`` meant a run whose every write
    failed reported the full control count anyway, so the compliance record
    claimed "Mapped 200 controls" for a run that stored nothing, and the user's
    lifetime ``mappingCount`` was inflated by the same amount. A failed write is
    not a smaller success, and the audit log is the last place that should
    round it up.
    """
    user_id, _ = _resolve_identity(user)
    metadata = dict(metadata or {})
    written = 0
    date = _today()
    persistence_attempted = bool(_ready() and mappings)

    if _ready() and mappings:
        try:
            await cosmos_client.ensure_container(
                cosmos_client.MAPPING_RESULTS,
                partition_key_paths=["/userId", "/date"],
                default_ttl=_MAPPING_TTL_SECONDS,
            )
            for m in mappings:
                doc = {
                    "id": str(uuid4()),
                    "userId": user_id,
                    "date": date,
                    "controlId": str(m.get("controlId") or m.get("control_id") or ""),
                    "controlName": str(m.get("controlName") or m.get("control_name") or ""),
                    "framework": framework,
                    "domain": m.get("domain"),
                    "mcsbMappings": m.get("mcsbMappings") or m.get("mcsb_mappings") or [],
                    "confidence": float(
                        m.get("confidence")
                        if m.get("confidence") is not None
                        else m.get("confidence_score") or 0.0
                    ),
                    "reasoning": str(m.get("reasoning") or ""),
                    "policyRecommendations": (
                        m.get("policyRecommendations")
                        or m.get("policy_recommendations")
                        or []
                    ),
                    "timestamp": _now_iso(),
                }
                await cosmos_client.upsert_document(cosmos_client.MAPPING_RESULTS, doc)
                written += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("mapping records failed for %s: %s", framework, exc)

    count = len(mappings)
    avg_conf = 0.0
    confs = [
        float(m.get("confidence") if m.get("confidence") is not None
               else m.get("confidence_score") or 0.0)
        for m in mappings
    ]
    if confs:
        avg_conf = round(sum(confs) / len(confs), 3)

    summary = f"Mapped {count} controls from '{framework}' (avg confidence {avg_conf})"
    if persistence_attempted and written < count:
        # Say it in the summary, not only in a field. The summary is what a
        # reviewer reads; a discrepancy buried in metadata is a silent one.
        summary += (
            f" — WARNING: only {written} of {count} were stored, "
            "so this run's detail is incomplete"
        )

    metadata.update({
        "summary": summary,
        "framework": framework,
        "controlCount": count,
        "persistedCount": written,
        "persistenceAttempted": persistence_attempted,
        "avgConfidence": avg_conf,
    })
    await audit_service.write_audit(
        user,
        action="mapping.created",
        resource_type=audit_service.RESOURCE_MAPPING,
        metadata=metadata,
    )
    # Bump the lifetime stat by what is actually retrievable. When persistence
    # was attempted these are equal unless writes failed, so this only differs
    # in the failure case — where a counter that outruns the stored records
    # would leave the history page claiming work it cannot show.
    await _bump_profile(
        user, "mappingCount", written if persistence_attempted else count
    )
    return written


# ---------------------------------------------------------------------------
# Policy exports / builds (#4)
# ---------------------------------------------------------------------------

async def record_export(
    user: Union[User, str],
    *,
    framework: str,
    artifact_type: str = "initiative",
    control_count: int = 0,
    file_name: str = "",
    file_size: int = 0,
    session_id: Optional[str] = None,
    content: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record a generated/exported policy artifact (stream #4)."""
    user_id, _ = _resolve_identity(user)
    metadata = dict(metadata or {})
    partition = session_id or user_id

    # Cap downloadable content by UTF-8 byte size. If it would exceed Cosmos's
    # item limit we drop it entirely (rather than truncate into invalid data)
    # and record why, so the workspace shows an honest "too large" state.
    content = content or ""
    content_skipped_reason = ""
    if len(content.encode("utf-8")) > _MAX_CONTENT_BYTES:
        content = ""
        content_skipped_reason = "too_large"
    content_available = bool(content)

    doc: Dict[str, Any] = {
        "id": str(uuid4()),
        "userId": user_id,
        "session_id": partition,
        "docKind": _USER_EXPORT_DOC_KIND,
        "artifactType": artifact_type,
        "framework": framework,
        "controlCount": int(control_count or 0),
        "content": content,
        "contentAvailable": content_available,
        "fileName": file_name,
        "fileSize": int(file_size or 0),
        "timestamp": _now_iso(),
    }
    if content_skipped_reason:
        doc["contentSkippedReason"] = content_skipped_reason

    if _ready():
        try:
            await cosmos_client.ensure_container(
                cosmos_client.GENERATED_ARTIFACTS,
                partition_key_paths=["/session_id"],
                default_ttl=_ARTIFACT_TTL_SECONDS,
            )
            await cosmos_client.upsert_document(
                cosmos_client.GENERATED_ARTIFACTS, doc, partition_key=partition
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("export record failed for %s: %s", framework, exc)

    metadata.update({
        "summary": f"Exported {artifact_type} for '{framework}' ({control_count} controls)",
        "framework": framework,
        "artifactType": artifact_type,
        "controlCount": int(control_count or 0),
        "fileName": file_name,
    })
    await audit_service.write_audit(
        user,
        action="export.generated",
        resource_type=audit_service.RESOURCE_EXPORT,
        resource_id=doc.get("id"),
        metadata=metadata,
    )
    await _bump_profile(user, "exportCount", 1)
    return doc


# ---------------------------------------------------------------------------
# Edits / changes (#2) — audit-only, surfaces in the unified feed
# ---------------------------------------------------------------------------

async def record_activity(
    user: Union[User, str],
    *,
    action: str,
    resource_type: str,
    summary: str,
    resource_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Record a generic activity (e.g. an edit) into the unified history feed."""
    metadata = dict(metadata or {})
    metadata.setdefault("summary", summary)
    await audit_service.write_audit(
        user,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=metadata,
    )
