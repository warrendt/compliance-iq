"""
Control mapping endpoints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
import uuid
import asyncio
from datetime import datetime

from app.models import (
    ExternalControl,
    ControlMapping,
    MappingBatch,
    MappingRequest,
    MappingJob
)
from app.services import get_ai_mapping_service, get_mcsb_service
from app.db import cosmos_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mapping", tags=["mapping"])

# In-memory job storage (for MVP - use Redis/database in production)
mapping_jobs: dict[str, MappingJob] = {}


def _cosmos_ready() -> bool:
    """Check if Cosmos DB is initialized."""
    return bool(cosmos_client and cosmos_client.database)


async def _persist_job(job: MappingJob) -> None:
    """Persist the job to Cosmos DB if available."""
    if not _cosmos_ready():
        return

    doc = job.model_dump(mode="json")
    doc["id"] = job.job_id
    doc["job_id"] = job.job_id

    try:
        await cosmos_client.upsert_document(
            cosmos_client.MAPPING_JOBS,
            doc,
            partition_key=job.job_id
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Cosmos persist failed for job {job.job_id}: {exc}")


async def _load_job(job_id: str) -> Optional[MappingJob]:
    """Load a job from memory or Cosmos DB."""
    if job_id in mapping_jobs:
        return mapping_jobs[job_id]

    if not _cosmos_ready():
        return None

    try:
        doc = await cosmos_client.get_document(
            cosmos_client.MAPPING_JOBS,
            document_id=job_id,
            partition_key=job_id
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Cosmos load failed for job {job_id}: {exc}")
        return None

    if not doc:
        return None

    job = MappingJob(**doc)
    mapping_jobs[job_id] = job
    return job


class MapSingleRequest(BaseModel):
    """Request to map a single control."""
    control: ExternalControl


class MapSingleResponse(BaseModel):
    """Response for single control mapping."""
    mapping: ControlMapping


class MapBatchRequest(BaseModel):
    """Request to map multiple controls concurrently."""
    controls: List[ExternalControl]
    concurrency: int = Field(default=5, ge=1, le=10, description="Max concurrent AI calls")


class MapBatchResponse(BaseModel):
    """Response for concurrent batch mapping."""
    mappings: List[ControlMapping]
    total: int
    mapped: int
    failed: int
    avg_confidence: float


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
        mapping = await ai_service.map_control(request.control)

        return MapSingleResponse(mapping=mapping)

    except Exception as e:
        logger.error(f"Failed to map control: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/map-batch", response_model=MapBatchResponse)
async def map_batch_controls(request: MapBatchRequest):
    """
    Map multiple controls concurrently.

    Processes controls in parallel (default 5 at a time) for faster throughput.
    Returns all results once complete.
    """
    logger.info(f"Batch mapping {len(request.controls)} controls (concurrency={request.concurrency})")

    ai_service = get_ai_mapping_service()
    semaphore = asyncio.Semaphore(request.concurrency)
    mappings: List[ControlMapping] = []
    failed = 0

    async def map_one(control: ExternalControl) -> Optional[ControlMapping]:
        nonlocal failed
        async with semaphore:
            try:
                return await ai_service.map_control(control)
            except Exception as e:
                logger.error(f"Failed to map {control.control_id}: {e}")
                failed += 1
                return ai_service._create_fallback_mapping(control, str(e))

    tasks = [map_one(c) for c in request.controls]
    results = await asyncio.gather(*tasks)
    mappings = [m for m in results if m is not None]

    avg_conf = (
        sum(m.confidence_score for m in mappings) / len(mappings)
        if mappings else 0.0
    )

    logger.info(f"Batch complete: {len(mappings)} mapped, {failed} failed, avg confidence {avg_conf:.2f}")

    return MapBatchResponse(
        mappings=mappings,
        total=len(request.controls),
        mapped=len(mappings) - failed,
        failed=failed,
        avg_confidence=avg_conf,
    )


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

    # Persist immediately so other replicas can serve status
    await _persist_job(job)

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
    job = await _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


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
    job = await _load_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found in cache or Cosmos")
        return

    job.status = "in_progress"

    try:
        ai_service = get_ai_mapping_service()

        async def progress_callback(current: int, total: int):
            """Update job progress."""
            job.mapped_controls = current
            job.progress = int((current / total) * 100)
            await _persist_job(job)
            logger.debug(f"Job {job_id}: {current}/{total} ({job.progress}%)")

        # Map controls
        batch_result = await ai_service.map_controls_batch(controls, progress_callback)

        # Update job
        job.status = "completed"
        job.progress = 100
        job.result = batch_result
        job.completed_at = datetime.utcnow()

        await _persist_job(job)

        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        job.status = "failed"
        job.error_message = str(e)
        await _persist_job(job)
