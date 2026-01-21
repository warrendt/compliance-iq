"""
Control mapping endpoints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import logging
import uuid

from app.models import (
    ExternalControl,
    ControlMapping,
    MappingBatch,
    MappingRequest,
    MappingJob
)
from app.services import get_ai_mapping_service, get_mcsb_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mapping", tags=["mapping"])

# In-memory job storage (for MVP - use Redis/database in production)
mapping_jobs: dict[str, MappingJob] = {}


class MapSingleRequest(BaseModel):
    """Request to map a single control."""
    control: ExternalControl


class MapSingleResponse(BaseModel):
    """Response for single control mapping."""
    mapping: ControlMapping


@router.post("/map-single", response_model=MapSingleResponse)
async def map_single_control(request: MapSingleRequest):
    """
    Map a single external control to MCSB.

    This endpoint maps one control at a time and returns the result immediately.

    Example:
        ```python
        import requests

        response = requests.post(
            "http://localhost:8000/api/v1/mapping/map-single",
            json={
                "control": {
                    "control_id": "SAMA-AC-01",
                    "control_name": "Strong Authentication",
                    "description": "Enforce MFA for all users",
                    "domain": "Identity & Access Control"
                }
            }
        )
        print(response.json())
        ```
    """
    logger.info(f"Mapping single control: {request.control.control_id}")

    try:
        ai_service = get_ai_mapping_service()
        mapping = ai_service.map_control(request.control)

        return MapSingleResponse(mapping=mapping)

    except Exception as e:
        logger.error(f"Failed to map control: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=MappingJob)
async def analyze_controls(
    request: MappingRequest,
    background_tasks: BackgroundTasks
):
    """
    Start batch control mapping job.

    Returns job ID immediately and processes mappings in background.

    Example:
        ```python
        # Start job
        response = requests.post(
            "http://localhost:8000/api/v1/mapping/analyze",
            json={
                "framework_name": "SAMA Cybersecurity",
                "controls": [...]
            }
        )
        job_id = response.json()["job_id"]

        # Check status
        status = requests.get(f"http://localhost:8000/api/v1/mapping/status/{job_id}")
        ```
    """
    logger.info(f"Starting mapping job for {request.framework_name}")

    # Create job
    job_id = str(uuid.uuid4())
    job = MappingJob(
        job_id=job_id,
        framework_name=request.framework_name,
        status="pending",
        total_controls=len(request.controls),
        mapped_controls=0
    )

    mapping_jobs[job_id] = job

    # Start background task
    background_tasks.add_task(
        process_mapping_job,
        job_id,
        request.controls
    )

    logger.info(f"Created mapping job {job_id} with {len(request.controls)} controls")
    return job


@router.get("/status/{job_id}", response_model=MappingJob)
async def get_mapping_status(job_id: str):
    """
    Get status of a mapping job.

    Args:
        job_id: Job identifier

    Returns:
        MappingJob with current status and results
    """
    if job_id not in mapping_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return mapping_jobs[job_id]


@router.get("/mcsb/controls")
async def get_mcsb_controls(domain: Optional[str] = None):
    """
    Get MCSB controls, optionally filtered by domain.

    Args:
        domain: Optional domain filter

    Returns:
        List of MCSB controls
    """
    try:
        mcsb_service = get_mcsb_service()

        if domain:
            controls = mcsb_service.get_controls_by_domain(domain)
        else:
            controls = mcsb_service.get_all_controls()

        return {
            "controls": controls,
            "count": len(controls)
        }

    except Exception as e:
        logger.error(f"Failed to get MCSB controls: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mcsb/domains")
async def get_mcsb_domains():
    """Get all MCSB security domains."""
    try:
        mcsb_service = get_mcsb_service()
        domains = mcsb_service.get_all_domains()

        return {
            "domains": domains,
            "count": len(domains)
        }

    except Exception as e:
        logger.error(f"Failed to get MCSB domains: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_mapping_job(job_id: str, controls: List[ExternalControl]):
    """
    Background task to process mapping job.

    Args:
        job_id: Job identifier
        controls: List of controls to map
    """
    job = mapping_jobs[job_id]
    job.status = "in_progress"

    try:
        ai_service = get_ai_mapping_service()

        def progress_callback(current: int, total: int):
            """Update job progress."""
            job.mapped_controls = current
            job.progress = int((current / total) * 100)
            logger.debug(f"Job {job_id}: {current}/{total} ({job.progress}%)")

        # Map controls
        batch_result = ai_service.map_controls_batch(controls, progress_callback)

        # Update job
        job.status = "completed"
        job.progress = 100
        job.result = batch_result
        from datetime import datetime
        job.completed_at = datetime.utcnow()

        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        job.status = "failed"
        job.error_message = str(e)
