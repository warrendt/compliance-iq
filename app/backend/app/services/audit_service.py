"""
Audit logging service.

Writes audit-trail entries to the ``audit-logs`` Cosmos container (partitioned
by ``/userId``) so the ``/user/history`` endpoint has data to return. Auditing is
best-effort: a failure here must never break the calling request, so all errors
are swallowed and logged.
"""

import logging
from typing import Any, Dict, Optional, Union

from app.auth.azure_ad_auth import User
from app.db.cosmos_client import cosmos_client
from app.models.db_models import AuditLogDocument

logger = logging.getLogger(__name__)

# 90 days — matches the TTL the /user/history reader ensures on audit-logs.
_AUDIT_TTL_SECONDS = 7776000

# Canonical resourceType values surfaced by /user/history filters.
RESOURCE_UPLOAD = "upload"
RESOURCE_MAPPING = "mapping"
RESOURCE_EXPORT = "export"
RESOURCE_COMPARISON = "comparison"
RESOURCE_POLICY_VERSION = "policy_version"


def _resolve_user_id(user: Union[User, str]) -> str:
    """Accept either a ``User`` principal or a raw userId string."""
    if isinstance(user, str):
        return user
    return getattr(user, "email", "") or ""


async def write_audit(
    user: Union[User, str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Write a single audit-log entry. Returns the stored doc, or None on no-op.

    Best-effort: never raises. If the database is unavailable or the write
    fails, the error is logged and ``None`` is returned.
    """
    user_id = _resolve_user_id(user)
    if not cosmos_client.database:
        logger.debug("audit_skipped_db_unavailable", extra={"action": action})
        return None

    try:
        await cosmos_client.ensure_container(
            cosmos_client.AUDIT_LOGS,
            partition_key_paths=["/userId"],
            default_ttl=_AUDIT_TTL_SECONDS,
        )

        doc = AuditLogDocument(
            userId=user_id,
            action=action,
            resourceType=resource_type,
            resourceId=resource_id,
            metadata=metadata or {},
            success=success,
            errorMessage=error_message,
        )
        body = doc.model_dump(mode="json")

        result = await cosmos_client.insert_document(cosmos_client.AUDIT_LOGS, body)
        logger.info(
            "audit_written",
            extra={"userId": user_id, "action": action, "resourceType": resource_type},
        )
        return result
    except Exception as exc:  # noqa: BLE001 — auditing must not break the caller
        logger.warning(
            "audit_write_failed",
            extra={"userId": user_id, "action": action, "error": str(exc)},
        )
        return None
