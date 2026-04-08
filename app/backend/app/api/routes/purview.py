"""
Microsoft Purview compliance configuration endpoints.
Provides API endpoints for generating and managing Microsoft Purview
configurations including sensitivity labels, DLP policies, retention
labels, and data governance settings.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
import json
import uuid
from datetime import datetime, timezone

from app.models.control import ExternalControl
from app.models.purview import (
    PurviewConfigType,
    PurviewControlMapping,
    PurviewConfigPackage,
    PurviewGenerationRequest,
)
from app.services.purview_service import get_purview_config_service
from app.db import cosmos_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/purview", tags=["microsoft-purview"])


def _cosmos_ready() -> bool:
    """Check if Cosmos DB is initialized."""
    return bool(cosmos_client and cosmos_client.database)


class PurviewMapSingleRequest(BaseModel):
    """Request to map a single control to Purview configurations."""
    control: ExternalControl
    config_types: Optional[List[PurviewConfigType]] = None


class PurviewMapBatchRequest(BaseModel):
    """Request to map multiple controls to Purview configurations."""
    controls: List[ExternalControl]
    config_types: Optional[List[PurviewConfigType]] = None


class PurviewGenerateFullRequest(BaseModel):
    """Request to generate a full Purview configuration package."""
    framework_name: str = Field(..., description="Framework name")
    framework_version: Optional[str] = Field(None, description="Framework version")
    controls: List[ExternalControl] = Field(..., description="Controls to map")
    config_types: List[PurviewConfigType] = Field(
        default_factory=lambda: [
            PurviewConfigType.SENSITIVITY_LABEL,
            PurviewConfigType.DLP_POLICY,
            PurviewConfigType.RETENTION_LABEL,
        ],
        description="Types of Purview configurations to generate"
    )
    enforcement_mode: str = Field(
        default="TestWithNotifications",
        description="Default enforcement mode"
    )


@router.get("/config-types")
async def get_purview_config_types():
    """
    Get all available Microsoft Purview configuration types with descriptions.
    """
    config_types = [
        {
            "id": PurviewConfigType.SENSITIVITY_LABEL.value,
            "name": "Sensitivity Labels",
            "description": "Classify and protect data with labels that enforce encryption, watermarks, and access control",
            "graph_endpoint": "/security/informationProtection/sensitivityLabels",
            "portal": "Microsoft Purview compliance portal > Information Protection",
        },
        {
            "id": PurviewConfigType.DLP_POLICY.value,
            "name": "DLP Policies",
            "description": "Detect and prevent sharing of sensitive information across M365 services and endpoints",
            "graph_endpoint": "/security/dataLossPreventionPolicies",
            "portal": "Microsoft Purview compliance portal > Data Loss Prevention",
        },
        {
            "id": PurviewConfigType.RETENTION_LABEL.value,
            "name": "Retention Labels",
            "description": "Manage data lifecycle with retention periods and disposal actions",
            "graph_endpoint": "/security/labels/retentionLabels",
            "portal": "Microsoft Purview compliance portal > Data Lifecycle Management",
        },
        {
            "id": PurviewConfigType.RETENTION_POLICY.value,
            "name": "Retention Policies",
            "description": "Apply retention settings across entire M365 locations",
            "graph_endpoint": "/security/labels/retentionLabels",
            "portal": "Microsoft Purview compliance portal > Data Lifecycle Management",
        },
        {
            "id": PurviewConfigType.EDISCOVERY.value,
            "name": "eDiscovery",
            "description": "Manage legal holds, searches, and content exports for investigations",
            "graph_endpoint": "/security/cases/ediscoveryCases",
            "portal": "Microsoft Purview compliance portal > eDiscovery",
        },
        {
            "id": PurviewConfigType.INFORMATION_BARRIER.value,
            "name": "Information Barriers",
            "description": "Restrict communication and collaboration between specific groups",
            "graph_endpoint": "/informationProtection/policy/labels",
            "portal": "Microsoft Purview compliance portal > Information Barriers",
        },
        {
            "id": PurviewConfigType.RECORDS_MANAGEMENT.value,
            "name": "Records Management",
            "description": "Manage high-value content with records and regulatory records",
            "graph_endpoint": "/security/labels/retentionLabels",
            "portal": "Microsoft Purview compliance portal > Records Management",
        },
    ]
    return {"config_types": config_types, "count": len(config_types)}


@router.post("/map-single")
async def map_single_control_purview(request: PurviewMapSingleRequest):
    """
    Map a single control to Microsoft Purview configurations.

    Returns recommended Purview configuration types and specific
    configurations for the control.
    """
    logger.info(f"Mapping control {request.control.control_id} to Purview configs")

    try:
        service = get_purview_config_service()
        mapping = service.map_control_to_purview(
            request.control, config_types=request.config_types
        )
        return {"mapping": mapping.model_dump()}
    except Exception as e:
        logger.error(f"Failed to map control to Purview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/map-batch")
async def map_batch_controls_purview(request: PurviewMapBatchRequest):
    """
    Map multiple controls to Microsoft Purview configurations.
    """
    logger.info(f"Batch mapping {len(request.controls)} controls to Purview configs")

    try:
        service = get_purview_config_service()
        mappings = [
            service.map_control_to_purview(c, config_types=request.config_types)
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
        logger.error(f"Failed to batch map controls to Purview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_purview_configs(
    request: PurviewGenerateFullRequest,
    http_request: Request,
):
    """
    Generate a complete Microsoft Purview configuration package from
    compliance controls.

    Returns sensitivity labels, retention labels, DLP policies,
    control mappings, and deployment scripts.
    """
    logger.info(
        f"Generating Purview config package for {request.framework_name} "
        f"({len(request.controls)} controls)"
    )

    try:
        service = get_purview_config_service()

        gen_request = PurviewGenerationRequest(
            framework_name=request.framework_name,
            framework_version=request.framework_version,
            config_types=request.config_types,
            enforcement_mode=request.enforcement_mode,
        )

        package = service.generate_purview_package(request.controls, gen_request)

        result = package.model_dump(mode="json")

        # Persist to Cosmos DB if available
        if _cosmos_ready():
            session_id = http_request.headers.get("X-Session-ID", "anonymous")
            artifact_id = str(uuid.uuid4())
            artifact_doc = {
                "id": artifact_id,
                "session_id": session_id,
                "type": "purview_config_package",
                "framework_name": request.framework_name,
                "sensitivity_label_count": len(package.sensitivity_labels),
                "retention_label_count": len(package.retention_labels),
                "dlp_policy_count": len(package.dlp_policies),
                "mapping_count": len(package.mappings),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                await cosmos_client.upsert_document(
                    cosmos_client.GENERATED_ARTIFACTS, artifact_doc
                )
                result["artifact_id"] = artifact_id
            except Exception as e:
                logger.warning(f"Failed to persist Purview artifact: {e}")

        return result

    except Exception as e:
        logger.error(f"Failed to generate Purview config package: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/json")
async def generate_purview_json(request: PurviewGenerateFullRequest):
    """
    Generate Purview configuration package and return as JSON file download.
    """
    try:
        service = get_purview_config_service()
        gen_request = PurviewGenerationRequest(
            framework_name=request.framework_name,
            framework_version=request.framework_version,
            config_types=request.config_types,
            enforcement_mode=request.enforcement_mode,
        )
        package = service.generate_purview_package(request.controls, gen_request)
        json_content = service.export_as_json(package)

        filename = f"{request.framework_name.replace(' ', '_')}_purview_config.json"
        return Response(
            content=json_content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.error(f"Failed to generate Purview JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sensitivity-labels/templates")
async def get_sensitivity_label_templates():
    """
    Get default sensitivity label templates that can be customized.
    """
    from app.services.purview_service import DEFAULT_SENSITIVITY_LABELS

    return {
        "labels": DEFAULT_SENSITIVITY_LABELS,
        "count": len(DEFAULT_SENSITIVITY_LABELS),
        "description": "Default sensitivity label hierarchy from Public to Highly Confidential",
    }


@router.get("/retention-labels/templates")
async def get_retention_label_templates():
    """
    Get default retention label templates.
    """
    from app.services.purview_service import DEFAULT_RETENTION_LABELS

    return {
        "labels": DEFAULT_RETENTION_LABELS,
        "count": len(DEFAULT_RETENTION_LABELS),
        "description": "Default retention labels ranging from 1 year to 10 years",
    }
