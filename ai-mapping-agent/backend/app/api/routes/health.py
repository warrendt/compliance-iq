"""
Health check endpoints.
"""

from fastapi import APIRouter
from pydantic import BaseModel
import logging

from app import __version__
from app.auth import test_azure_openai_connection
from app.services import get_mcsb_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    azure_openai_connected: bool
    mcsb_controls_loaded: bool
    mcsb_control_count: int


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns application status and service connectivity.
    """
    logger.info("Health check requested")

    # Test Azure OpenAI connection
    try:
        azure_openai_connected = test_azure_openai_connection()
    except Exception as e:
        logger.error(f"Azure OpenAI health check failed: {e}")
        azure_openai_connected = False

    # Check MCSB service
    try:
        mcsb_service = get_mcsb_service()
        controls = mcsb_service.get_all_controls()
        mcsb_controls_loaded = True
        mcsb_control_count = len(controls)
    except Exception as e:
        logger.error(f"MCSB service health check failed: {e}")
        mcsb_controls_loaded = False
        mcsb_control_count = 0

    return HealthResponse(
        status="healthy" if (azure_openai_connected and mcsb_controls_loaded) else "degraded",
        version=__version__,
        azure_openai_connected=azure_openai_connected,
        mcsb_controls_loaded=mcsb_controls_loaded,
        mcsb_control_count=mcsb_control_count
    )


@router.get("/ping")
async def ping():
    """Simple ping endpoint."""
    return {"message": "pong"}
