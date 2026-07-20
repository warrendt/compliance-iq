"""Pure, side-effect-free helpers for the ComplianceIQ skill client.

Everything network-, subprocess-, or filesystem-touching lives in ``ciq.py``.
This module holds only deterministic functions so the request/response shaping
and control-flow decisions can be unit tested without hitting Azure.
"""

from __future__ import annotations

import secrets
from typing import Any, Iterable, Mapping, Optional

# Endpoints are all mounted under this prefix (backend ``settings.api_v1_prefix``).
API_PREFIX = "/api/v1"

# Statuses the pipeline job can end on. Mirrors ``PipelineJobStatus.status``.
_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
_SUCCESS_STATUSES = frozenset({"completed"})

# ARM audience of a token from ``az account get-access-token`` (v1). The backend
# must be configured to accept this (AZURE_AD_ACCEPTED_AUDIENCES) for deploy.
ARM_RESOURCE = "https://management.azure.com"


def api_url(base_url: str, path: str) -> str:
    """Join the frontend base URL with an API ``path`` under ``/api/v1``.

    ``path`` may be given with or without the ``/api/v1`` prefix and with or
    without a leading slash.
    """
    base = base_url.rstrip("/")
    p = "/" + path.strip("/")
    if not p.startswith(API_PREFIX + "/") and p != API_PREFIX:
        p = API_PREFIX + p
    return base + p


def is_terminal_status(status: Optional[str]) -> bool:
    """True when the pipeline job has reached a final state."""
    return (status or "").lower() in _TERMINAL_STATUSES


def is_success_status(status: Optional[str]) -> bool:
    """True when the pipeline job completed successfully."""
    return (status or "").lower() in _SUCCESS_STATUSES


def default_initiative_name(framework_name: Optional[str]) -> str:
    """Derive the initiative name the backend uses from a framework name.

    Matches ``framework_name.replace(" ", "_").lower()`` used server-side, and
    falls back to a safe default when the framework name is missing.
    """
    name = (framework_name or "compliance_framework").strip()
    return name.replace(" ", "_").lower() or "compliance_framework"


def extract_initiative(artifacts: Mapping[str, Any]) -> Optional[dict]:
    """Return the Azure initiative JSON from a ``/pipeline/artifacts`` payload."""
    files = artifacts.get("files") if isinstance(artifacts, Mapping) else None
    if isinstance(files, Mapping):
        initiative = files.get("initiative")
        if isinstance(initiative, dict):
            return initiative
    return None


def summarize_status(status: Mapping[str, Any]) -> str:
    """One-line human summary of a pipeline status payload."""
    return (
        f"{status.get('status', 'unknown')} "
        f"({status.get('progress', 0)}%) "
        f"stage={status.get('stage', '')!r} "
        f"controls={status.get('controls_extracted', 0)}/"
        f"mapped={status.get('controls_mapped', 0)}"
        + (f" error={status.get('error')!r}" if status.get("error") else "")
    ).strip()


def parse_scopes(scopes_payload: Mapping[str, Any]) -> list[dict]:
    """Return the list of scope dicts from a ``/deploy/scopes`` payload."""
    scopes = scopes_payload.get("scopes") if isinstance(scopes_payload, Mapping) else None
    return list(scopes) if isinstance(scopes, list) else []


def build_validate_body(
    scope: str,
    initiative_name: str,
    initiative_body: dict,
    check_references: bool = True,
) -> dict:
    """Build the JSON body for ``POST /deploy/validate``."""
    return {
        "scope": scope,
        "initiative_name": initiative_name,
        "initiative_body": initiative_body,
        "check_references": check_references,
    }


def build_deploy_body(
    scope: str,
    initiative_name: str,
    initiative_body: dict,
    *,
    assign: bool = False,
    enforce_mode: bool = False,
    location: str = "eastus",
    assignment_display_name: Optional[str] = None,
    assignment_description: str = "",
) -> dict:
    """Build the JSON body for ``POST /deploy/initiative``.

    ``enforce_mode`` defaults to ``False`` (DoNotEnforce / audit-only) — the
    same safe default the application uses. ``location`` is required whenever
    the initiative contains DeployIfNotExists/Modify policies (an identity is
    created even under DoNotEnforce).
    """
    return {
        "scope": scope,
        "initiative_name": initiative_name,
        "initiative_body": initiative_body,
        "assign": assign,
        "enforce_mode": enforce_mode,
        "location": location,
        "assignment_display_name": assignment_display_name or initiative_name,
        "assignment_description": assignment_description,
    }


def build_run_fields(
    min_confidence: float = 0.5,
    allowed_locations: Optional[str] = None,
) -> dict[str, str]:
    """Build the multipart form fields for ``POST /pipeline/run``."""
    fields = {"min_confidence": str(min_confidence)}
    if allowed_locations:
        fields["allowed_locations"] = allowed_locations
    return fields


def new_boundary() -> str:
    """Return a fresh multipart boundary token."""
    return "----complianceiq" + secrets.token_hex(16)


def encode_multipart(
    fields: Mapping[str, str],
    file_field: str,
    filename: str,
    file_bytes: bytes,
    boundary: Optional[str] = None,
    content_type: str = "application/pdf",
) -> tuple[bytes, str]:
    """Encode ``multipart/form-data`` with one file part and text ``fields``.

    Returns ``(body, content_type_header)``. Pure and deterministic when a
    ``boundary`` is supplied, which the tests rely on.
    """
    b = boundary or new_boundary()
    crlf = b"\r\n"
    out: list[bytes] = []

    for name, value in fields.items():
        out.append(b"--" + b.encode())
        out.append(
            f'Content-Disposition: form-data; name="{name}"'.encode()
        )
        out.append(b"")
        out.append(str(value).encode())

    out.append(b"--" + b.encode())
    out.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{filename}"'
        ).encode()
    )
    out.append(f"Content-Type: {content_type}".encode())
    out.append(b"")

    body = crlf.join(out) + crlf + file_bytes + crlf + b"--" + b.encode() + b"--" + crlf
    return body, f"multipart/form-data; boundary={b}"


def auth_headers(token: Optional[str]) -> dict[str, str]:
    """Return Authorization headers for the given bearer token (or empty)."""
    return {"Authorization": f"Bearer {token}"} if token else {}


def is_valid_scope(scope: str) -> bool:
    """Cheap sanity check that ``scope`` is an ARM scope path we can deploy to."""
    return isinstance(scope, str) and (
        scope.startswith("/subscriptions/")
        or scope.startswith("/providers/Microsoft.Management/managementGroups/")
    )


def choose_scope(scopes: Iterable[Mapping[str, Any]], wanted: str) -> Optional[dict]:
    """Find a scope whose id, display name, or scope path matches ``wanted``."""
    w = (wanted or "").strip().lower()
    if not w:
        return None
    for s in scopes:
        candidates = {
            str(s.get("id", "")).lower(),
            str(s.get("display", "")).lower(),
            str(s.get("scope", "")).lower(),
        }
        if w in candidates or any(w in c for c in candidates if c):
            return dict(s)
    return None
