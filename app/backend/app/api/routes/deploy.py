"""
Deploy & Explorer endpoints — proxy ARM calls using the caller's Entra token.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Awaitable, Optional
import logging

import httpx

from app.auth.azure_ad_auth import User, get_current_user
from app.services.policy_deploy_service import PolicyDeployService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/deploy", tags=["deploy"])


def _svc(user: User) -> PolicyDeployService:
    """Build a PolicyDeployService using the caller's delegated token."""
    if not user.access_token:
        raise HTTPException(
            status_code=401,
            detail="No access token available — sign in with Entra ID to deploy policies.",
        )
    return PolicyDeployService(user.access_token)


# ------------------------------------------------------------------
# Scopes
# ------------------------------------------------------------------

async def _safe_arm_fetch(
    coro: Awaitable[list[dict[str, Any]]], label: str
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Await an ARM list call, converting failures into a warning string.

    Returns ``(items, warning)``. On success ``warning`` is ``None``; on
    failure ``items`` is empty and ``warning`` describes the ARM error. This
    lets one scope source fail (e.g. management groups, which most users cannot
    read) without discarding results from the other.
    """
    try:
        return await coro, None
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = (exc.response.text or "").strip()[:300]
        logger.warning("scope_fetch_failed label=%s status=%s", label, status)
        if status in (401, 403):
            reason = (
                "access denied — your signed-in identity lacks read permission "
                "at this level (this is expected for most users at the "
                "management-group level)"
            )
        else:
            reason = f"ARM HTTP {status}: {body}" if body else f"ARM HTTP {status}"
        return [], f"{label}: {reason}"
    except Exception as exc:  # noqa: BLE001 — surface any failure as a warning
        logger.warning("scope_fetch_error label=%s", label, exc_info=exc)
        return [], f"{label}: {exc}"


@router.get("/scopes")
async def list_scopes(user: User = Depends(get_current_user)):
    """Return subscriptions and management groups visible to the caller.

    Subscriptions and management groups are fetched independently so a failure
    in one (commonly a 403 on management groups) does not blank out the other.
    """
    svc = _svc(user)

    subs, subs_warn = await _safe_arm_fetch(svc.list_subscriptions(), "Subscriptions")
    mgs, mgs_warn = await _safe_arm_fetch(
        svc.list_management_groups(), "Management groups"
    )

    sub_items = [
        {"id": s["subscriptionId"], "display": s.get("displayName", s["subscriptionId"]), "type": "subscription",
         "scope": f"/subscriptions/{s['subscriptionId']}"}
        for s in subs
    ]
    mg_items = [
        {"id": m["name"], "display": m.get("properties", {}).get("displayName", m["name"]), "type": "management_group",
         "scope": f"/providers/Microsoft.Management/managementGroups/{m['name']}"}
        for m in mgs
    ]

    warnings = [w for w in (subs_warn, mgs_warn) if w]

    # Only fail the whole request when BOTH sources errored — otherwise return
    # whatever we could resolve plus the warnings.
    if subs_warn and mgs_warn:
        raise HTTPException(status_code=502, detail=" | ".join(warnings))

    return {"scopes": sub_items + mg_items, "warnings": warnings}


# ------------------------------------------------------------------
# Validate (non-destructive dry run)
# ------------------------------------------------------------------

class ValidateRequest(BaseModel):
    scope: str = Field(..., description="ARM scope path")
    initiative_name: str = Field(..., min_length=1, max_length=128)
    initiative_body: dict[str, Any]
    check_references: bool = Field(
        True,
        description="Verify each referenced policy definition exists (read-only).",
    )


@router.post("/validate")
async def validate_initiative(
    req: ValidateRequest, user: User = Depends(get_current_user)
):
    """Non-destructive validation of an initiative definition.

    Runs structural checks and read-only reference resolution. Nothing is
    written to the tenant — unlike deploy, this never creates or updates
    the policy set definition.
    """
    svc = _svc(user)
    try:
        result = await svc.validate_initiative(
            scope=req.scope,
            initiative_name=req.initiative_name,
            body=req.initiative_body,
            check_references=req.check_references,
        )
        return result
    except Exception as exc:
        logger.warning("validate_failed", exc_info=exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ------------------------------------------------------------------
# Deploy (definition + optional assignment)
# ------------------------------------------------------------------

class DeployRequest(BaseModel):
    scope: str = Field(..., description="ARM scope path")
    initiative_name: str = Field(..., min_length=1, max_length=128)
    initiative_body: dict[str, Any]
    assign: bool = Field(False, description="Also create a policy assignment")
    assignment_display_name: Optional[str] = None
    assignment_description: Optional[str] = ""
    enforce_mode: bool = Field(
        False,
        description="When False (default), the assignment is created with "
        "DoNotEnforce (audit-only): compliance is assessed but effects are "
        "never applied or remediated.",
    )
    location: str = Field(
        "eastus",
        description="Region for the assignment's system-assigned identity "
        "(mandatory when the initiative contains DeployIfNotExists/Modify "
        "policies, even under DoNotEnforce).",
    )


@router.post("/initiative")
async def deploy_initiative(
    req: DeployRequest, user: User = Depends(get_current_user)
):
    """Deploy a policy set definition (and optionally assign it)."""
    svc = _svc(user)
    try:
        definition = await svc.deploy_initiative(
            scope=req.scope,
            initiative_name=req.initiative_name,
            body=req.initiative_body,
        )
    except Exception as exc:
        logger.error("deploy_definition_failed", exc_info=exc)
        raise HTTPException(status_code=502, detail=str(exc))

    assignment = None
    if req.assign:
        try:
            definition_id = definition.get("id", "")
            assignment = await svc.create_assignment(
                scope=req.scope,
                assignment_name=f"{req.initiative_name}-assignment",
                policy_set_definition_id=definition_id,
                display_name=req.assignment_display_name or req.initiative_name,
                description=req.assignment_description or "",
                enforce_mode=req.enforce_mode,
                location=req.location,
            )
        except Exception as exc:
            logger.error("deploy_assignment_failed", exc_info=exc)
            raise HTTPException(
                status_code=502,
                detail=f"Initiative created but assignment failed: {exc}",
            )

    return {
        "status": "deployed",
        "definition": definition,
        "assignment": assignment,
    }


# ------------------------------------------------------------------
# Explorer — list existing policies
# ------------------------------------------------------------------

@router.get("/definitions")
async def list_definitions(
    scope: str = Query(..., description="ARM scope"),
    custom_only: bool = Query(True),
    user: User = Depends(get_current_user),
):
    """List policy definitions at the given scope."""
    svc = _svc(user)
    try:
        return {"definitions": await svc.list_policy_definitions(scope, custom_only=custom_only)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/initiatives")
async def list_initiatives(
    scope: str = Query(..., description="ARM scope"),
    custom_only: bool = Query(True),
    user: User = Depends(get_current_user),
):
    """List policy set (initiative) definitions at the given scope."""
    svc = _svc(user)
    try:
        return {"initiatives": await svc.list_policy_set_definitions(scope, custom_only=custom_only)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/assignments")
async def list_assignments(
    scope: str = Query(..., description="ARM scope"),
    user: User = Depends(get_current_user),
):
    """List policy assignments at the given scope."""
    svc = _svc(user)
    try:
        return {"assignments": await svc.list_policy_assignments(scope)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
