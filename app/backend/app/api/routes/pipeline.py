"""
API routes for the compliance pipeline — PDF to Defender for Cloud Initiative.
Provides a POST endpoint that accepts a PDF upload and runs the full pipeline.
Also provides an extract-only endpoint that returns controls in CSV-flow format.
"""

import base64
import csv
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

import httpx
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])

# In-memory job store (production would use Cosmos DB)
_jobs: dict[str, dict] = {}

# Optional per-job debug log buffer (in-memory, not persisted)
_job_logs: dict[str, list[dict]] = {}

PIPELINE_DEBUG_LOG = os.getenv("PIPELINE_DEBUG_LOG", "0").lower() in {"1", "true", "yes"}
PIPELINE_LOG_MAX_ENTRIES = int(os.getenv("PIPELINE_LOG_MAX_ENTRIES", "500"))

_cosmos_client = None
_cosmos_container = None


class PipelineJobStatus(BaseModel):
    """Status of a pipeline job."""
    job_id: str
    status: str  # pending, extracting_text, extracting_controls, mapping_policies, validating, generating, completed, failed
    progress: int = 0  # 0-100
    stage: str = ""
    framework_name: Optional[str] = None
    controls_extracted: int = 0
    controls_mapped: int = 0
    error: Optional[str] = None
    output_dir: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class PipelineRequest(BaseModel):
    """Request options for the pipeline."""
    min_confidence: float = Field(0.5, ge=0.0, le=1.0)
    allowed_locations: Optional[list[str]] = None


class PipelineArtifacts(BaseModel):
    """Artifacts returned for review/edit in UI."""
    job_id: str
    framework_name: Optional[str]
    files: dict


class PipelineRepackRequest(BaseModel):
    """Request to repack initiative ZIP with edited mappings CSV."""
    mappings_csv: str


class ExtractedControlCSVFormat(BaseModel):
    """A single extracted control in CSV-flow format (matches ExternalControl)."""
    control_id: str
    control_name: str
    description: str
    domain: Optional[str] = None
    control_type: Optional[str] = None
    requirements: Optional[str] = None


class PipelineExtractResponse(BaseModel):
    """Response from the extract-only endpoint."""
    framework_name: str
    framework_version: Optional[str] = None
    issuing_authority: Optional[str] = None
    country_or_region: Optional[str] = None
    controls: list[ExtractedControlCSVFormat]
    total_controls: int


@router.post("/run", response_model=PipelineJobStatus)
async def run_pipeline_endpoint(
    background_tasks: BackgroundTasks,
    pdf_file: UploadFile = File(..., description="Compliance control PDF document"),
    min_confidence: float = Form(0.5, ge=0.0, le=1.0),
    allowed_locations: Optional[str] = Form(None, description="Comma-separated Azure regions"),
):
    """
    Submit a compliance PDF for automated processing.

    The pipeline will:
    1. Extract text from the PDF
    2. Use AI to extract all compliance controls
    3. Map each control to Azure Policy definitions
    4. Validate the mappings
    5. Generate deployable initiative artifacts

    Returns a job ID that can be polled for status.
    """
    # Validate file
    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "File must be a PDF document")

    content = await pdf_file.read()
    job_id, job = _create_job(
        filename=pdf_file.filename,
        content=content,
        min_confidence=min_confidence,
        allowed_locations=_parse_locations(allowed_locations),
    )

    background_tasks.add_task(_run_pipeline_job, job_id)
    logger.info(f"Pipeline job created: {job_id} for {pdf_file.filename}")
    _log_debug(job_id, f"Job created for {pdf_file.filename}")

    return PipelineJobStatus(**{k: v for k, v in job.items() if k in PipelineJobStatus.model_fields})


@router.post("/extract", response_model=PipelineExtractResponse)
async def extract_controls_from_pdf(
    pdf_file: UploadFile = File(..., description="Compliance control PDF document"),
):
    """
    Extract controls from a compliance PDF (Stages 1-2 only).

    Returns controls in CSV-flow format so the frontend can load them
    directly into the Upload → Map → Review → Export flow.
    No mapping, validation, or initiative generation is performed.
    """
    from app.pipeline import (
        PipelineConfig,
        extract_text_from_pdf,
        get_pdf_metadata,
        extract_controls_from_text,
    )

    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "File must be a PDF document")

    content = await pdf_file.read()
    if len(content) == 0:
        raise HTTPException(400, "PDF file is empty")
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "PDF file exceeds 50MB limit")

    # Save to temp file for pypdf
    tmp_dir = tempfile.mkdtemp(prefix="compliance_iq_extract_")
    pdf_path = Path(tmp_dir) / pdf_file.filename
    try:
        pdf_path.write_bytes(content)

        config = PipelineConfig.from_env()
        errors = config.validate()
        if errors:
            raise HTTPException(500, f"Config errors: {'; '.join(errors)}")

        # Stage 1: Extract text
        pdf_metadata = get_pdf_metadata(str(pdf_path))
        pdf_text = extract_text_from_pdf(str(pdf_path), max_pages=config.max_pdf_pages)

        # Stage 2: AI control extraction
        extraction = extract_controls_from_text(pdf_text, config, pdf_metadata)

        # Convert ExtractedControl → CSV-flow format (ExternalControl-compatible)
        csv_controls = [
            ExtractedControlCSVFormat(
                control_id=c.control_id,
                control_name=c.control_title,
                description=c.control_description,
                domain=c.domain,
                control_type=c.control_type,
                requirements="; ".join(c.sub_controls) if c.sub_controls else None,
            )
            for c in extraction.controls
        ]

        return PipelineExtractResponse(
            framework_name=extraction.framework_name,
            framework_version=extraction.framework_version,
            issuing_authority=extraction.issuing_authority,
            country_or_region=extraction.country_or_region,
            controls=csv_controls,
            total_controls=len(csv_controls),
        )
    finally:
        # Clean up temp files
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.post("/selftest", response_model=PipelineJobStatus)
async def run_pipeline_selftest(
    background_tasks: BackgroundTasks,
    pdf_url: str = Form("https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"),
    min_confidence: float = Form(0.5, ge=0.0, le=1.0),
    allowed_locations: Optional[str] = Form(None, description="Comma-separated Azure regions"),
):
    """Run a self-test job using a small public PDF. Helpful for smoke testing inside the private app."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(pdf_url)
            resp.raise_for_status()
            content = resp.content
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Failed to download test PDF: {exc}") from exc

    job_id, job = _create_job(
        filename="selftest.pdf",
        content=content,
        min_confidence=min_confidence,
        allowed_locations=_parse_locations(allowed_locations),
    )

    background_tasks.add_task(_run_pipeline_job, job_id)
    logger.info(f"Pipeline self-test job created: {job_id} from {pdf_url}")
    _log_debug(job_id, f"Self-test job created from {pdf_url}")

    return PipelineJobStatus(**{k: v for k, v in job.items() if k in PipelineJobStatus.model_fields})


@router.get("/status/{job_id}", response_model=PipelineJobStatus)
async def get_pipeline_status(job_id: str):
    """Get the current status of a pipeline job."""
    if job_id not in _jobs:
        raise HTTPException(404, f"Job {job_id} not found")

    job = _jobs[job_id]
    return PipelineJobStatus(**{k: v for k, v in job.items() if k in PipelineJobStatus.model_fields})


@router.get("/logs/{job_id}")
async def get_pipeline_logs(job_id: str, since: int = 0):
    """Return buffered debug logs for a job. Available only when PIPELINE_DEBUG_LOG is enabled."""
    if not PIPELINE_DEBUG_LOG:
        raise HTTPException(404, "Pipeline logging is disabled")

    if job_id not in _jobs:
        raise HTTPException(404, f"Job {job_id} not found")

    logs = _job_logs.get(job_id, [])
    sliced = logs[since:]
    next_cursor = since + len(sliced)
    job_status = PipelineJobStatus(**{k: v for k, v in _jobs[job_id].items() if k in PipelineJobStatus.model_fields})
    return {"logs": sliced, "next_cursor": next_cursor, "status": job_status}


@router.get("/download/{job_id}")
async def download_pipeline_output(job_id: str):
    """Download the generated initiative artifacts as a ZIP file."""
    if job_id not in _jobs:
        raise HTTPException(404, f"Job {job_id} not found")

    job = _jobs[job_id]

    if job["status"] != "completed":
        raise HTTPException(400, f"Job is not completed (status: {job['status']})")

    _ensure_output_dir(job_id, job)

    output_dir = job.get("output_dir")
    if not output_dir or not Path(output_dir).exists():
        raise HTTPException(500, "Output directory not found")

    # Create ZIP in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        out_path = Path(output_dir)
        for file_path in out_path.iterdir():
            if file_path.is_file():
                zf.write(file_path, file_path.name)

    zip_buffer.seek(0)

    fw_name = job.get("framework_name", "initiative")
    safe_name = fw_name.replace(" ", "_").replace("/", "_")

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_Initiative.zip"'
        },
    )


@router.post("/repack/{job_id}")
async def repack_pipeline_output(job_id: str, payload: PipelineRepackRequest):
    """Repack initiative ZIP with edited mappings CSV (no full re-run)."""
    if job_id not in _jobs:
        raise HTTPException(404, f"Job {job_id} not found")

    job = _jobs[job_id]

    if job.get("status") != "completed":
        raise HTTPException(400, f"Job is not completed (status: {job.get('status')})")

    _ensure_output_dir(job_id, job)

    output_dir = job.get("output_dir")
    if not output_dir or not Path(output_dir).exists():
        raise HTTPException(500, "Output directory not found")

    out = Path(output_dir)
    mappings_file = next((f for f in out.iterdir() if f.name.endswith("_Mappings.csv")), None)
    if not mappings_file:
        raise HTTPException(500, "Mappings CSV not found for this job")

    # Overwrite mappings CSV with edited content
    mappings_file.write_text(payload.mappings_csv, encoding="utf-8")

    # Rebuild ZIP in-memory using current output directory contents
    zip_bytes = _zip_dir(out)

    fw_name = job.get("framework_name", "initiative")
    safe_name = fw_name.replace(" ", "_").replace("/", "_")

    return StreamingResponse(
        BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_Initiative_Edited.zip"'
        },
    )


@router.get("/artifacts/{job_id}", response_model=PipelineArtifacts)
async def get_pipeline_artifacts(job_id: str):
    """Return generated artifacts as JSON-friendly payload for UI preview/edit."""
    if job_id not in _jobs:
        raise HTTPException(404, f"Job {job_id} not found")

    job = _jobs[job_id]

    if job.get("status") != "completed":
        raise HTTPException(400, f"Job is not completed (status: {job.get('status')})")

    _ensure_output_dir(job_id, job)

    output_dir = job.get("output_dir")
    if not output_dir or not Path(output_dir).exists():
        raise HTTPException(500, "Output directory not found")

    out = Path(output_dir)

    def _read_json(name: str):
        p = out / name
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def _read_csv(name: str):
        p = out / name
        if not p.exists():
            return None
        with p.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    files: dict = {
        "initiative": _read_json(next((f.name for f in out.iterdir() if f.name.endswith("_Initiative.json")), None)),
        "groups": _read_json("groups.json"),
        "policies": _read_json("policies.json"),
        "params": _read_json("params.json"),
        "validation_report": _read_json("validation_report.json"),
        "mappings": _read_csv(next((f.name for f in out.iterdir() if f.name.endswith("_Mappings.csv")), None)),
    }

    # Remove None entries to keep payload tidy
    files = {k: v for k, v in files.items() if v is not None}

    return PipelineArtifacts(
        job_id=job_id,
        framework_name=job.get("framework_name"),
        files=files,
    )


@router.get("/jobs", response_model=list[PipelineJobStatus])
async def list_pipeline_jobs():
    """List all pipeline jobs."""
    return [
        PipelineJobStatus(**{k: v for k, v in job.items() if k in PipelineJobStatus.model_fields})
        for job in _jobs.values()
    ]


async def _run_pipeline_job(job_id: str):
    """Execute the pipeline in the background."""
    from app.pipeline import (
        PipelineConfig,
        extract_text_from_pdf,
        get_pdf_metadata,
        extract_controls_from_text,
        map_controls_to_azure_policies,
        validate_mappings,
        build_initiative_artifacts,
    )

    job = _jobs[job_id]

    try:

        # Save PDF to temp file
        tmp_dir = tempfile.mkdtemp(prefix="compliance_iq_")
        pdf_path = Path(tmp_dir) / job["pdf_filename"]
        pdf_path.write_bytes(job["pdf_content"])
        _log_debug(job_id, f"Saved PDF to {pdf_path}")

        # Load config
        config = PipelineConfig.from_env()
        errors = config.validate()
        if errors:
            job["status"] = "failed"
            job["error"] = f"Config errors: {'; '.join(errors)}"
            _log_debug(job_id, job["error"])
            return

        # ── Stage 1: Extract text ─────────────────────────────────────
        job["status"] = "extracting_text"
        job["stage"] = "Extracting text from PDF"
        job["progress"] = 5
        _log_debug(job_id, "Starting text extraction")

        pdf_metadata = get_pdf_metadata(str(pdf_path))
        pdf_text = extract_text_from_pdf(str(pdf_path), max_pages=config.max_pdf_pages)
        _log_debug(job_id, f"Extracted text ({len(pdf_text):,} chars) from {pdf_metadata.get('pages', '?')} pages")

        job["progress"] = 15

        # ── Stage 2: Extract controls ─────────────────────────────────
        job["status"] = "extracting_controls"
        job["stage"] = "AI extracting controls from document"
        job["progress"] = 20
        _log_debug(job_id, "Extracting controls with Azure OpenAI")

        extraction = extract_controls_from_text(pdf_text, config, pdf_metadata)

        job["framework_name"] = extraction.framework_name
        job["controls_extracted"] = len(extraction.controls)
        job["progress"] = 40
        _log_debug(job_id, f"Extracted {len(extraction.controls)} controls (framework: {extraction.framework_name})")

        # ── Stage 3: Map to Azure Policies ────────────────────────────
        job["status"] = "mapping_policies"
        job["stage"] = "Mapping controls to Azure Policies"
        job["progress"] = 45

        _log_debug(job_id, "Mapping controls to Azure Policies")

        def progress_cb(current, total):
            pct = 45 + int((current / total) * 30)
            job["progress"] = pct
            job["controls_mapped"] = current
            _log_debug(job_id, f"Mapped {current}/{total} controls")

        mappings = map_controls_to_azure_policies(extraction, config, progress_callback=progress_cb)
        job["controls_mapped"] = len(mappings)
        job["progress"] = 80
        _log_debug(job_id, f"Completed mapping for {len(mappings)} controls")

        # ── Stage 4: Validate ─────────────────────────────────────────
        job["status"] = "validating"
        job["stage"] = "Validating mappings"
        job["progress"] = 85
        _log_debug(job_id, "Validating mappings")

        validation = validate_mappings(extraction, mappings, job["min_confidence"])
        job["progress"] = 90
        _log_debug(job_id, "Validation complete")

        # ── Stage 5: Generate artifacts ───────────────────────────────
        job["status"] = "generating"
        job["stage"] = "Generating initiative artifacts"

        output_dir = str(Path(tmp_dir) / "output")
        files = build_initiative_artifacts(
            extraction=extraction,
            mappings=mappings,
            validation=validation,
            output_dir=output_dir,
            allowed_locations=job["allowed_locations"],
        )
        _log_debug(job_id, f"Artifacts generated: {len(files)} files")

        job["output_dir"] = output_dir
        job["status"] = "completed"
        job["stage"] = "Complete"
        job["progress"] = 100
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
        _log_debug(job_id, "Pipeline completed")

        # Persist job and artifacts to Cosmos if enabled
        try:
            zip_bytes = _zip_dir(Path(output_dir))
            job_copy = {k: v for k, v in job.items() if k != "pdf_content"}
            job_copy["artifacts_zip_b64"] = base64.b64encode(zip_bytes).decode("utf-8")
            _cosmos_upsert_job(job_copy)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to persist artifacts for job {job_id}: {exc}")
            _log_debug(job_id, f"Failed to persist artifacts: {exc}")

        logger.info(f"Pipeline job {job_id} completed: {len(files)} files generated")

        # Remove the raw PDF content from memory
        del job["pdf_content"]

    except Exception as e:
        logger.error(f"Pipeline job {job_id} failed: {e}", exc_info=True)
        job["status"] = "failed"
        job["error"] = str(e)
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
        _cosmos_upsert_job(job)
        _log_debug(job_id, f"Pipeline failed: {e}")


def _parse_locations(allowed_locations: Optional[str]) -> Optional[list[str]]:
    if not allowed_locations:
        return None
    parsed = [loc.strip() for loc in allowed_locations.split(",") if loc.strip()]
    return parsed or None


def _create_job(
    *, filename: str, content: bytes, min_confidence: float, allowed_locations: Optional[list[str]]
):
    if len(content) == 0:
        raise HTTPException(400, "PDF file is empty")
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(400, "PDF file exceeds 50MB limit")

    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "stage": "Queued",
        "framework_name": None,
        "controls_extracted": 0,
        "controls_mapped": 0,
        "error": None,
        "output_dir": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "pdf_filename": filename,
        "pdf_content": content,
        "min_confidence": min_confidence,
        "allowed_locations": allowed_locations,
    }
    _jobs[job_id] = job

    if PIPELINE_DEBUG_LOG:
        _job_logs[job_id] = []
        _log_debug(job_id, "Job initialized")

    _cosmos_upsert_job(job)
    return job_id, job


def _zip_dir(out: Path) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in out.iterdir():
            if file_path.is_file():
                zf.write(file_path, file_path.name)
    buf.seek(0)
    return buf.getvalue()


def _ensure_output_dir(job_id: str, job: dict):
    output_dir = job.get("output_dir")
    if output_dir and Path(output_dir).exists():
        return

    # Attempt to restore from Cosmos if available
    if not _cosmos_container:
        return

    doc = _cosmos_get_job(job_id)
    if not doc:
        return

    artifacts_b64 = doc.get("artifacts_zip_b64")
    if not artifacts_b64:
        return

    tmp_dir = tempfile.mkdtemp(prefix="compliance_iq_restored_")
    zip_bytes = base64.b64decode(artifacts_b64)
    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
        zf.extractall(tmp_dir)

    job["output_dir"] = tmp_dir
    _jobs[job_id] = job


def _init_cosmos():
    global _cosmos_client, _cosmos_container
    if _cosmos_container is not None:
        return

    endpoint = os.getenv("COSMOS_DB_ENDPOINT")
    database_name = os.getenv("COSMOS_DB_DATABASE_NAME", "compliance-iq-db")
    container_name = os.getenv("COSMOS_DB_CONTAINER_NAME", "pipeline-jobs")

    if not endpoint:
        return

    try:
        cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        _cosmos_client = CosmosClient(endpoint, credential=cred)
        db = _cosmos_client.create_database_if_not_exists(id=database_name)
        _cosmos_container = db.create_container_if_not_exists(
            id=container_name,
            partition_key="/job_id",
            offer_throughput=400,
        )
        logger.info("Cosmos persistence enabled for pipeline jobs")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Cosmos not enabled: {exc}")
        _cosmos_container = None


def _cosmos_upsert_job(job: dict):
    if _cosmos_container is None:
        _init_cosmos()
    if _cosmos_container is None:
        return
    try:
        _cosmos_container.upsert_item(job)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to persist job {job.get('job_id')}: {exc}")


def _cosmos_get_job(job_id: str) -> Optional[dict]:
    if _cosmos_container is None:
        _init_cosmos()
    if _cosmos_container is None:
        return None
    try:
        return _cosmos_container.read_item(item=job_id, partition_key=job_id)
    except Exception:
        return None


def _log_debug(job_id: str, message: str):
    """Append a debug log entry for a job if debug logging is enabled."""
    if not PIPELINE_DEBUG_LOG:
        return
    if job_id not in _job_logs:
        _job_logs[job_id] = []

    entry = {
        "ts": datetime.now(timezone.utc).isoformat() + "Z",
        "message": message,
    }
    buf = _job_logs[job_id]
    buf.append(entry)

    # Trim buffer to max size to avoid unbounded growth
    if len(buf) > PIPELINE_LOG_MAX_ENTRIES:
        _job_logs[job_id] = buf[-PIPELINE_LOG_MAX_ENTRIES:]
