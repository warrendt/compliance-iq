"""
Health check endpoints.
"""

from fastapi import APIRouter
from pydantic import BaseModel
import logging

from app import __version__
from app.auth import test_azure_openai_connection
from app.services import get_sovereignty_service, get_policy_catalog_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    azure_openai_connected: bool
    slz_policies_loaded: bool = False
    slz_policy_count: int = 0
    policy_catalog_count: int = 0
    policy_catalog_source: str = "unloaded"


@router.get("", response_model=HealthResponse)
@router.get("/", response_model=HealthResponse)
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

    # Check SLZ sovereignty service
    try:
        slz_service = get_sovereignty_service()
        slz_summary = slz_service.get_summary()
        slz_policies_loaded = slz_summary["total_policies"] > 0
        slz_policy_count = slz_summary["total_policies"]
    except Exception as e:
        logger.error(f"SLZ service health check failed: {e}")
        slz_policies_loaded = False
        slz_policy_count = 0

    # Check Azure Policy catalog (retrieval corpus)
    try:
        catalog = get_policy_catalog_service()
        policy_catalog_count = catalog.count
        policy_catalog_source = catalog.source
    except Exception as e:
        logger.error(f"Policy catalog health check failed: {e}")
        policy_catalog_count = 0
        policy_catalog_source = "error"

    return HealthResponse(
        status="healthy" if azure_openai_connected else "degraded",
        version=__version__,
        azure_openai_connected=azure_openai_connected,
        slz_policies_loaded=slz_policies_loaded,
        slz_policy_count=slz_policy_count,
        policy_catalog_count=policy_catalog_count,
        policy_catalog_source=policy_catalog_source,
    )


@router.get("/ping")
async def ping():
    """Simple ping endpoint."""
    return {"message": "pong"}


@router.get("/logs")
async def get_application_logs(
    since: int = 0,
    level: str = "DEBUG",
    limit: int = 200,
):
    """Return recent application log entries from the in-memory buffer.

    Args:
        since: Return entries with sequence number > since (for incremental polling).
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        limit: Maximum number of entries to return (default 200).

    Returns:
        Dict with ``logs`` list, ``next_cursor``, and ``total_buffered``.
    """
    from app.logging_config import get_log_entries

    return get_log_entries(since=since, level=level, limit=limit)
