"""
Deploy & Explorer endpoints — proxy ARM calls using the caller's Entra token.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Optional
import logging

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

@router.get("/scopes")
async def list_scopes(user: User = Depends(get_current_user)):
    """Return subscriptions and management groups visible to the caller."""
    svc = _svc(user)
    subs = await svc.list_subscriptions()
    mgs = await svc.list_management_groups()

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
    return {"scopes": sub_items + mg_items}


# ------------------------------------------------------------------
# Validate (dry-run)
# ------------------------------------------------------------------

class ValidateRequest(BaseModel):
    scope: str = Field(..., description="ARM scope path")
    initiative_name: str = Field(..., min_length=1, max_length=128)
    initiative_body: dict[str, Any]


@router.post("/validate")
async def validate_initiative(
    req: ValidateRequest, user: User = Depends(get_current_user)
):
    """Dry-run: create/update the initiative definition and return ARM result."""
    svc = _svc(user)
    try:
        result = await svc.validate_initiative(
            scope=req.scope,
            initiative_name=req.initiative_name,
            body=req.initiative_body,
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
