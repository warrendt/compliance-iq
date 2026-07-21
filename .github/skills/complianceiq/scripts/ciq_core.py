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

# Azure Policy hard limits enforced by the ARM ``policySetDefinitions`` REST API
# (api-version 2023-04-01). Exceeding either yields an HTTP 400 at deploy time:
#   - description > 512 chars                  -> "The value ... exceeds ... 512"
#   - a policyDefinition ref with >16 groups   -> InvalidPolicySetDefinitionGroups
# The pipeline's report-grade initiative can exceed both for large frameworks
# (e.g. SAMA: 857-char description, one policy in 19 groups), so we clamp at the
# deploy boundary. Confirmed directly from ARM 400 responses.
ARM_DESCRIPTION_MAX = 512
ARM_GROUPNAMES_MAX = 16


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


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first present key from ``mapping`` (case variants), else default."""
    for k in keys:
        if k in mapping and mapping[k] is not None:
            return mapping[k]
    return default


def normalize_initiative_for_deploy(initiative: Mapping[str, Any]) -> dict:
    """Return a REST-deployable ``policySetDefinitions`` body from a pipeline
    initiative artifact.

    The pipeline's ``files.initiative`` is shaped for PowerShell
    (``New-AzPolicySetDefinition``): ``PolicyDefinitionId``,
    ``PolicyDefinitionReferenceId``, ``GroupNames`` (PascalCase). The ARM REST
    API — used by ``/deploy/validate`` and ``/deploy/initiative`` — requires
    camelCase (``policyDefinitionId`` ...), so ARM silently drops the PascalCase
    keys and validation fails with "missing policyDefinitionId".

    This converts to camelCase and stamps ``metadata.ASC = "true"`` (the legacy
    flag that surfaces a custom initiative under Defender for Cloud > Regulatory
    compliance, matching the backend ``to_azure_json()``). It is idempotent: a
    body already in camelCase passes through unchanged apart from the ASC stamp.
    """
    props = initiative.get("properties") if isinstance(initiative.get("properties"), Mapping) else initiative

    defs = []
    for pd in props.get("policyDefinitions") or []:
        if not isinstance(pd, Mapping):
            continue
        group_names = _first(pd, "groupNames", "GroupNames", default=[]) or []
        # ARM rejects a reference listing >16 groups; keep the first 16.
        if len(group_names) > ARM_GROUPNAMES_MAX:
            group_names = list(group_names)[:ARM_GROUPNAMES_MAX]
        defs.append({
            "policyDefinitionId": _first(pd, "policyDefinitionId", "PolicyDefinitionId"),
            "policyDefinitionReferenceId": _first(pd, "policyDefinitionReferenceId", "PolicyDefinitionReferenceId"),
            "parameters": _first(pd, "parameters", "Parameters", default={}) or {},
            "groupNames": group_names,
        })

    groups = []
    for g in props.get("policyDefinitionGroups") or []:
        if not isinstance(g, Mapping):
            continue
        group = {"name": _first(g, "name", "Name")}
        display = _first(g, "displayName", "DisplayName")
        desc = _first(g, "description", "Description")
        if display is not None:
            group["displayName"] = display
        if desc is not None:
            group["description"] = desc
        groups.append(group)

    metadata = dict(props.get("metadata") or {})
    metadata.setdefault("category", "Regulatory Compliance")
    metadata["ASC"] = "true"

    description = props.get("description", "") or ""
    if len(description) > ARM_DESCRIPTION_MAX:
        description = description[:ARM_DESCRIPTION_MAX]

    return {
        "properties": {
            "displayName": props.get("displayName"),
            "description": description,
            "policyType": "Custom",
            "metadata": metadata,
            "parameters": props.get("parameters") or {},
            "policyDefinitions": defs,
            "policyDefinitionGroups": groups,
        }
    }


def arm_safety_warnings(initiative: Mapping[str, Any]) -> list:
    """Return human-readable warnings for any ARM limits that
    :func:`normalize_initiative_for_deploy` will silently clamp.

    Lets the CLI tell the user *before* deploy that content was trimmed to fit
    Azure Policy limits (e.g. a description shortened, or group associations
    dropped from an over-referenced policy), rather than hiding the loss.
    """
    props = initiative.get("properties") if isinstance(initiative.get("properties"), Mapping) else initiative
    warnings = []

    description = props.get("description") or props.get("Description") or ""
    if len(description) > ARM_DESCRIPTION_MAX:
        warnings.append(
            f"Initiative description is {len(description)} chars; truncated to "
            f"the ARM limit of {ARM_DESCRIPTION_MAX}."
        )

    for pd in props.get("policyDefinitions") or props.get("PolicyDefinitions") or []:
        if not isinstance(pd, Mapping):
            continue
        ref = _first(pd, "policyDefinitionReferenceId", "PolicyDefinitionReferenceId", default="?")
        gn = _first(pd, "groupNames", "GroupNames", default=[]) or []
        if len(gn) > ARM_GROUPNAMES_MAX:
            warnings.append(
                f"Policy '{ref}' is grouped under {len(gn)} controls; ARM allows "
                f"{ARM_GROUPNAMES_MAX}, so {len(gn) - ARM_GROUPNAMES_MAX} group "
                f"association(s) will be dropped for this policy."
            )

    return warnings


def extract_initiative(artifacts: Mapping[str, Any]) -> Optional[dict]:
    """Return a REST-deployable Azure initiative from a ``/pipeline/artifacts``
    payload (normalized to camelCase + ASC-stamped)."""
    files = artifacts.get("files") if isinstance(artifacts, Mapping) else None
    if isinstance(files, Mapping):
        initiative = files.get("initiative")
        if isinstance(initiative, dict):
            return normalize_initiative_for_deploy(initiative)
    return None


# --------------------------------------------------------------------------- #
# Parameterized built-ins (required, no-default parameters)
#
# A built-in with a required (no ``defaultValue``) parameter cannot be referenced
# in a custom policy set without a concrete value: ARM rejects the whole set
# definition with ``MissingPolicyParameter``. The application handles this in
# ``policy_service.generate_initiative`` — it *includes* the built-in when the
# operator supplies every required value, otherwise excludes it. The skill mirrors
# that: it surfaces each such policy + its required parameter schema so the user
# can decide, per policy, to supply a value or exclude it. Nothing is dropped
# silently.
# --------------------------------------------------------------------------- #

def _guid_of(policy_id: Optional[str]) -> Optional[str]:
    """Return the definition GUID (last path segment) of a policyDefinitionId."""
    if not policy_id:
        return None
    return str(policy_id).rstrip("/").rsplit("/", 1)[-1] or None


def required_params_from_definition(definition: Mapping[str, Any]) -> dict:
    """Return ``{paramName: schema}`` for parameters of an ``az policy definition
    show`` object that have **no** ``defaultValue`` (i.e. required).

    ``schema`` keeps the fields useful for prompting the user: ``type``,
    ``description``, ``allowedValues``, ``strongType``.
    """
    params = definition.get("parameters") if isinstance(definition, Mapping) else None
    if not isinstance(params, Mapping):
        return {}
    required: dict = {}
    for name, spec in params.items():
        if not isinstance(spec, Mapping) or "defaultValue" in spec:
            continue
        meta = spec.get("metadata") if isinstance(spec.get("metadata"), Mapping) else {}
        required[name] = {
            "type": spec.get("type"),
            "description": meta.get("description"),
            "allowedValues": spec.get("allowedValues"),
            "strongType": meta.get("strongType"),
        }
    return required


def parameterized_references(
    initiative: Mapping[str, Any],
    required_by_guid: Mapping[str, Mapping[str, Any]],
) -> list:
    """List references in ``initiative`` whose built-in needs required params.

    ``required_by_guid`` maps a definition GUID to its required-parameter schema
    (see :func:`required_params_from_definition`). Returns one entry per affected
    reference: ``{referenceId, policyId, guid, required}``.
    """
    props = initiative.get("properties") if isinstance(initiative.get("properties"), Mapping) else initiative
    out = []
    for pd in props.get("policyDefinitions") or []:
        if not isinstance(pd, Mapping):
            continue
        pid = _first(pd, "policyDefinitionId", "PolicyDefinitionId")
        guid = _guid_of(pid)
        required = required_by_guid.get(guid) if guid else None
        if required:
            out.append({
                "referenceId": _first(pd, "policyDefinitionReferenceId", "PolicyDefinitionReferenceId"),
                "policyId": pid,
                "guid": guid,
                "required": dict(required),
            })
    return out


def _coerce_param_value(value: Any, schema: Mapping[str, Any]) -> Any:
    """Coerce a user-supplied string into the parameter's declared type.

    Only the common cases are handled: ``Array`` splits a comma-separated string
    into a list; ``Integer``/``Boolean`` are parsed; everything else passes
    through. A value that is already a list/dict is returned unchanged.
    """
    if isinstance(value, (list, dict)):
        return value
    ptype = str((schema or {}).get("type") or "").lower()
    if ptype == "array":
        return [v.strip() for v in str(value).split(",") if v.strip()]
    if ptype == "integer":
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if ptype == "boolean":
        return str(value).strip().lower() in {"true", "1", "yes"}
    return value


def apply_parameter_resolutions(
    initiative: Mapping[str, Any],
    *,
    required_by_guid: Mapping[str, Mapping[str, Any]],
    values: Optional[Mapping[str, Mapping[str, Any]]] = None,
    exclude: Optional[Iterable[str]] = None,
) -> tuple:
    """Resolve required-parameter built-ins per the user's choices.

    - ``values``: ``{guid: {paramName: value}}`` — bake these in as literal
      reference parameters (``{"value": ...}``), coerced to the declared type.
    - ``exclude``: GUIDs whose references should be dropped entirely.

    Returns ``(new_initiative, unresolved)`` where ``unresolved`` lists any
    reference still missing a required value and not excluded — the caller must
    refuse to deploy while ``unresolved`` is non-empty (never silently drop).
    """
    values = values or {}
    exclude = set(exclude or ())
    props = initiative.get("properties") if isinstance(initiative.get("properties"), Mapping) else initiative
    src_defs = props.get("policyDefinitions") or []

    new_defs = []
    unresolved = []
    for pd in src_defs:
        if not isinstance(pd, Mapping):
            new_defs.append(pd)
            continue
        pid = _first(pd, "policyDefinitionId", "PolicyDefinitionId")
        guid = _guid_of(pid)
        required = required_by_guid.get(guid) if guid else None

        if guid in exclude:
            continue  # user chose to drop this policy

        if not required:
            new_defs.append(dict(pd))
            continue

        supplied = values.get(guid) or {}
        missing = [p for p in required if p not in supplied]
        if missing:
            unresolved.append({
                "referenceId": _first(pd, "policyDefinitionReferenceId", "PolicyDefinitionReferenceId"),
                "guid": guid,
                "missing": missing,
                "required": dict(required),
            })
            continue  # leave out until resolved; reported to caller

        ref = dict(pd)
        params = dict(ref.get("parameters") or {})
        for pname, schema in required.items():
            params[pname] = {"value": _coerce_param_value(supplied[pname], schema)}
        ref["parameters"] = params
        new_defs.append(ref)

    new_props = dict(props)
    new_props["policyDefinitions"] = new_defs
    return {"properties": new_props}, unresolved


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
