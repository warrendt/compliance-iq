"""
Platform selection endpoints.
Allows users to discover available compliance platforms and select
their target platform at the start of the compliance mapping workflow.
"""

from fastapi import APIRouter, HTTPException
import logging

from app.models.platform import (
    CompliancePlatform,
    PlatformSelectionRequest,
    PlatformSelectionResponse,
)
from app.services.platform_service import get_platform_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/list")
async def list_platforms():
    """
    List all available compliance platforms.

    Returns platform information including capabilities, API endpoints,
    and documentation links for Azure Defender, Microsoft 365, and
    Microsoft Purview.
    """
    try:
        service = get_platform_service()
        platforms = service.get_all_platforms()
        return {
            "platforms": [p.model_dump() for p in platforms],
            "count": len(platforms),
        }
    except Exception as e:
        logger.error(f"Failed to list platforms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{platform_id}")
async def get_platform_details(platform_id: str):
    """
    Get detailed information about a specific compliance platform.

    Args:
        platform_id: Platform identifier (azure_defender, microsoft_365, microsoft_purview)
    """
    try:
        platform = CompliancePlatform(platform_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform: {platform_id}. "
                   f"Valid options: {[p.value for p in CompliancePlatform]}"
        )

    try:
        service = get_platform_service()
        info = service.get_platform_info(platform)
        return info.model_dump()
    except Exception as e:
        logger.error(f"Failed to get platform details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/select", response_model=PlatformSelectionResponse)
async def select_platform(request: PlatformSelectionRequest):
    """
    Select a compliance platform for the mapping workflow.

    This is the first step in the compliance mapping process. Users
    choose their target platform and optionally select specific
    capabilities to focus on.

    Example:
        ```json
        {
            "platform": "microsoft_365",
            "capabilities": ["dlp", "conditional_access"]
        }
        ```
    """
    try:
        service = get_platform_service()
        response = service.select_platform(request)
        return response
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform: {request.platform}"
        )
    except Exception as e:
        logger.error(f"Failed to select platform: {e}")
        raise HTTPException(status_code=500, detail=str(e))
