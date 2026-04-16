"""
Microsoft 365 compliance policy endpoints.
Provides API endpoints for generating and managing Microsoft 365 compliance
policies including DLP, Conditional Access, Device Compliance, and
Information Protection policies.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
import json
import uuid
from datetime import datetime, timezone

from app.models.control import ExternalControl
from app.auth.azure_ad_auth import User, get_current_user
from app.models.m365_policy import (
    M365PolicyType,
    M365ServiceScope,
    M365ControlMapping,
    M365PolicyPackage,
    M365GenerationRequest,
)
from app.services.m365_policy_service import get_m365_policy_service
from app.services.graph_client import get_graph_client
from app.db import cosmos_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/m365", tags=["microsoft-365"])


def _cosmos_ready() -> bool:
    """Check if Cosmos DB is initialized."""
    return bool(cosmos_client and cosmos_client.database)


class M365MapSingleRequest(BaseModel):
    """Request to map a single control to Microsoft 365 policies."""
    control: ExternalControl
    policy_types: Optional[List[M365PolicyType]] = None


class M365MapBatchRequest(BaseModel):
    """Request to map multiple controls to Microsoft 365 policies."""
    controls: List[ExternalControl]
    policy_types: Optional[List[M365PolicyType]] = None


class M365GenerateRequest(BaseModel):
    """Request to generate a full M365 policy package."""
    framework_name: str = Field(..., description="Framework name")
    framework_version: Optional[str] = Field(None, description="Framework version")
    controls: List[ExternalControl] = Field(..., description="Controls to map")
    policy_types: List[M365PolicyType] = Field(
        default_factory=lambda: [M365PolicyType.DLP, M365PolicyType.CONDITIONAL_ACCESS],
        description="Types of M365 policies to generate"
    )
    service_scopes: List[M365ServiceScope] = Field(
        default_factory=lambda: [M365ServiceScope.ALL],
        description="Target M365 services"
    )
    enforcement_mode: str = Field(
        default="TestWithNotifications",
        description="Default enforcement mode"
    )


@router.get("/policy-types")
async def get_m365_policy_types():
    """
    Get all available Microsoft 365 policy types with descriptions.
    """
    policy_types = [
        {
            "id": M365PolicyType.DLP.value,
            "name": "Data Loss Prevention",
            "description": "Prevent sharing of sensitive information across M365 services",
            "services": ["Exchange", "SharePoint", "OneDrive", "Teams", "Endpoints"],
            "graph_endpoint": "/security/dataLossPreventionPolicies",
        },
        {
            "id": M365PolicyType.CONDITIONAL_ACCESS.value,
            "name": "Conditional Access",
            "description": "Control access based on conditions (MFA, device, location, risk)",
            "services": ["Entra ID", "All Cloud Apps"],
            "graph_endpoint": "/identity/conditionalAccess/policies",
        },
        {
            "id": M365PolicyType.DEVICE_COMPLIANCE.value,
            "name": "Device Compliance",
            "description": "Enforce device compliance requirements via Intune",
            "services": ["Windows", "iOS", "Android", "macOS"],
            "graph_endpoint": "/deviceManagement/deviceCompliancePolicies",
        },
        {
            "id": M365PolicyType.INFORMATION_PROTECTION.value,
            "name": "Information Protection",
            "description": "Information barriers and sharing restrictions",
            "services": ["Exchange", "SharePoint", "Teams"],
            "graph_endpoint": "/informationProtection/policy/labels",
        },
        {
            "id": M365PolicyType.COMMUNICATION_COMPLIANCE.value,
            "name": "Communication Compliance",
            "description": "Monitor and enforce communication policies",
            "services": ["Exchange", "Teams"],
            "graph_endpoint": "/security/cases/ediscoveryCases",
        },
        {
            "id": M365PolicyType.INSIDER_RISK.value,
            "name": "Insider Risk Management",
            "description": "Detect and respond to insider risk activities",
            "services": ["All M365 Services"],
            "graph_endpoint": "/security/cases/ediscoveryCases",
        },
    ]
    return {"policy_types": policy_types, "count": len(policy_types)}


@router.post("/map-single")
async def map_single_control_m365(request: M365MapSingleRequest):
    """
    Map a single control to Microsoft 365 policies.

    Returns recommended M365 policy types and specific policies for the control.
    """
    logger.info(f"Mapping control {request.control.control_id} to M365 policies")

    try:
        service = get_m365_policy_service()
        mapping = service.map_control_to_m365(
            request.control, policy_types=request.policy_types
        )
        return {"mapping": mapping.model_dump()}
    except Exception as e:
        logger.error(f"Failed to map control to M365: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/map-batch")
async def map_batch_controls_m365(request: M365MapBatchRequest):
    """
    Map multiple controls to Microsoft 365 policies.

    Returns recommended M365 policy types and specific policies for each control.
    """
    logger.info(f"Batch mapping {len(request.controls)} controls to M365 policies")

    try:
        service = get_m365_policy_service()
        mappings = [
            service.map_control_to_m365(c, policy_types=request.policy_types)
            for c in request.controls
        ]

        avg_confidence = (
            sum(m.confidence_score for m in mappings) / len(mappings)
            if mappings else 0.0
        )

        return {
            "mappings": [m.model_dump() for m in mappings],
            "total": len(request.controls),
            "mapped": len(mappings),
            "avg_confidence": round(avg_confidence, 2),
        }
    except Exception as e:
        logger.error(f"Failed to batch map controls to M365: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_m365_policies(
    request: M365GenerateRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a complete Microsoft 365 policy package from compliance controls.

    Returns M365 policies, control mappings, and deployment scripts.
    """
    logger.info(
        f"Generating M365 policy package for {request.framework_name} "
        f"({len(request.controls)} controls)"
    )

    try:
        service = get_m365_policy_service()

        gen_request = M365GenerationRequest(
            framework_name=request.framework_name,
            framework_version=request.framework_version,
            policy_types=request.policy_types,
            service_scopes=request.service_scopes,
            enforcement_mode=request.enforcement_mode,
        )

        package = service.generate_m365_package(request.controls, gen_request)

        result = package.model_dump(mode="json")

        # Persist to Cosmos DB if available
        if _cosmos_ready():
            raw_session_id = http_request.headers.get("X-Session-ID", "default")
            session_id = f"{current_user.user_id}:{raw_session_id}"
            artifact_id = str(uuid.uuid4())
            artifact_doc = {
                "id": artifact_id,
                "session_id": session_id,
                "tenant_id": current_user.tenant_id,
                "user_id": current_user.user_id,
                "user_email": current_user.email,
                "type": "m365_policy_package",
                "framework_name": request.framework_name,
                "policy_count": len(package.policies),
                "mapping_count": len(package.mappings),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                await cosmos_client.upsert_document(
                    cosmos_client.GENERATED_ARTIFACTS, artifact_doc
                )
                result["artifact_id"] = artifact_id
                await cosmos_client.append_history_event(
                    user_id=current_user.user_id,
                    tenant_id=current_user.tenant_id,
                    event_type="export.created",
                    resource_type="m365_artifact",
                    resource_id=artifact_id,
                    session_id=session_id,
                    details={
                        "framework_name": request.framework_name,
                        "policy_count": len(package.policies),
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to persist M365 artifact: {e}")

        return result

    except Exception as e:
        logger.error(f"Failed to generate M365 policy package: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/json")
async def generate_m365_json(request: M365GenerateRequest):
    """
    Generate M365 policy package and return as JSON file download.
    """
    try:
        service = get_m365_policy_service()
        gen_request = M365GenerationRequest(
            framework_name=request.framework_name,
            framework_version=request.framework_version,
            policy_types=request.policy_types,
            service_scopes=request.service_scopes,
            enforcement_mode=request.enforcement_mode,
        )
        package = service.generate_m365_package(request.controls, gen_request)
        json_content = service.export_as_json(package)

        filename = f"{request.framework_name.replace(' ', '_')}_m365_policies.json"
        return Response(
            content=json_content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.error(f"Failed to generate M365 JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph-endpoints")
async def get_graph_endpoints():
    """
    Get available Microsoft Graph API endpoints for M365 compliance.
    """
    graph_client = get_graph_client()
    endpoints = graph_client.get_available_endpoints()
    permissions = graph_client.get_all_required_permissions()

    return {
        "endpoints": endpoints,
        "required_permissions": permissions,
        "api_base": "https://graph.microsoft.com",
    }
