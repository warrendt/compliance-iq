"""
Azure Policy generation endpoints.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
import json

from app.models import PolicyGenerationRequest, PolicyGenerationResponse, ControlMapping
from app.services import get_policy_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/policy", tags=["policy"])


@router.post("/generate")
async def generate_policy_initiative(request: PolicyGenerationRequest):
    """
    Generate Azure Policy initiative from control mappings.

    Returns an enriched response including the initiative JSON in Azure
    format, a Bicep template, and PowerShell / CLI deployment scripts.
    """
    logger.info(f"Generating policy initiative for {request.framework_name}")

    try:
        policy_service = get_policy_service()
        response = policy_service.generate_initiative(request)

        logger.info(
            f"Generated initiative with {response.included_policies} policies"
        )

        # Build enriched response with all artifacts the frontend needs
        initiative_name = request.framework_name.replace(" ", "_").lower()
        initiative_json = response.initiative.to_azure_json()
        bicep_template = policy_service.export_as_bicep(
            response.initiative, initiative_name
        )
        scripts = policy_service.generate_deployment_script(
            response.initiative, initiative_name
        )

        result = response.model_dump()
        result["initiative_id"] = f"{initiative_name}-compliance"
        result["initiative_json"] = initiative_json
        result["bicep_template"] = bicep_template
        result["powershell_script"] = scripts["powershell"]
        result["cli_script"] = scripts.get("cli", "")
        return result

    except Exception as e:
        logger.error(f"Failed to generate policy initiative: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/json")
async def generate_policy_json(request: PolicyGenerationRequest):
    """
    Generate Azure Policy initiative and return as JSON file.

    Returns:
        JSON file download with initiative definition
    """
    logger.info(f"Generating policy JSON for {request.framework_name}")

    try:
        policy_service = get_policy_service()
        response = policy_service.generate_initiative(request)

        # Export as JSON
        json_content = policy_service.export_as_json(response.initiative, pretty=True)

        # Create filename
        filename = f"{request.framework_name.replace(' ', '_')}_initiative.json"

        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        logger.error(f"Failed to generate policy JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/bicep")
async def generate_policy_bicep(request: PolicyGenerationRequest):
    """
    Generate Azure Policy initiative as Bicep template.

    Returns:
        Bicep template file download
    """
    logger.info(f"Generating Bicep template for {request.framework_name}")

    try:
        policy_service = get_policy_service()
        response = policy_service.generate_initiative(request)

        # Export as Bicep
        initiative_name = request.framework_name.lower().replace(' ', '_')
        bicep_content = policy_service.export_as_bicep(
            response.initiative,
            initiative_name
        )

        # Create filename
        filename = f"{initiative_name}_initiative.bicep"

        return Response(
            content=bicep_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        logger.error(f"Failed to generate Bicep template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/scripts")
async def generate_deployment_scripts(request: PolicyGenerationRequest):
    """
    Generate deployment scripts (Azure CLI and PowerShell).

    Returns:
        Dictionary with CLI and PowerShell scripts
    """
    logger.info(f"Generating deployment scripts for {request.framework_name}")

    try:
        policy_service = get_policy_service()
        response = policy_service.generate_initiative(request)

        # Generate scripts
        initiative_name = request.framework_name.lower().replace(' ', '_')
        scripts = policy_service.generate_deployment_script(
            response.initiative,
            initiative_name
        )

        return {
            "initiative_name": initiative_name,
            "cli_script": scripts["cli"],
            "powershell_script": scripts["powershell"]
        }

    except Exception as e:
        logger.error(f"Failed to generate deployment scripts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- SLZ Initiative Generation ---

class SLZGenerationRequest(BaseModel):
    """Request to generate SLZ-specific policy initiatives per archetype."""
    framework_name: str = Field(..., description="Compliance framework name")
    mappings: List[ControlMapping] = Field(..., description="Control mappings with sovereignty data")
    allowed_locations: Optional[List[str]] = Field(
        default=None,
        description="Allowed Azure regions for data residency (e.g. ['uaenorth','uaecentral'])"
    )


@router.post("/generate/slz")
async def generate_slz_initiatives(request: SLZGenerationRequest):
    """
    Generate Sovereign Landing Zone policy initiatives per archetype.

    Produces per-archetype artifacts (JSON initiative, Bicep template,
    deployment scripts) based on sovereignty mappings in each control.

    Returns:
        Dictionary keyed by archetype with JSON, Bicep, CLI, and PS artifacts
    """
    logger.info(
        f"Generating SLZ initiatives for {request.framework_name} "
        f"({len(request.mappings)} mappings)"
    )

    try:
        policy_service = get_policy_service()

        # Filter to mappings that have sovereignty data
        sov_mappings = [m for m in request.mappings if m.sovereignty is not None]
        if not sov_mappings:
            raise HTTPException(
                status_code=400,
                detail="No mappings contain sovereignty data. Run AI mapping first."
            )

        result = policy_service.generate_slz_initiatives(
            mappings=sov_mappings,
            framework_name=request.framework_name,
            allowed_locations=request.allowed_locations,
        )

        return {
            "framework_name": request.framework_name,
            "total_mappings": len(request.mappings),
            "sovereignty_mappings": len(sov_mappings),
            "archetypes": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate SLZ initiatives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Policy Details (cached lookup) ---

class PolicyDetailsRequest(BaseModel):
    """Request to look up Azure Policy details by GUID."""
    policy_ids: List[str] = Field(
        ...,
        description="List of Azure Policy definition GUIDs",
        min_length=1,
        max_length=100,
    )


@router.post("/details")
async def get_policy_details(request: PolicyDetailsRequest):
    """
    Batch-lookup Azure Policy details by GUID.

    Returns cached results from Cosmos DB with Microsoft Learn fallback.
    """
    from app.services.policy_cache_service import get_policy_cache_service

    logger.info(f"Looking up {len(request.policy_ids)} policy details")

    try:
        cache_service = get_policy_cache_service()
        details = await cache_service.get_policy_details(request.policy_ids)

        return {
            "requested": len(request.policy_ids),
            "found": len(details),
            "policies": details,
        }

    except Exception as e:
        logger.error(f"Failed to look up policy details: {e}")
        raise HTTPException(status_code=500, detail=str(e))
