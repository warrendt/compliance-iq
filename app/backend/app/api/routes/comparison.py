"""
API routes for internal-vs-external control comparison (diff).

Flow:
  POST /comparison/run        upload internal PDF + pick external framework →
                              creates a per-user job in the ``comparisons``
                              container and runs it in the background.
  GET  /comparison/frameworks list selectable external frameworks (dropdown).
  GET  /comparison/status/{id} poll job status + bucket counts.
  GET  /comparison            list the current user's comparisons.
  GET  /comparison/{id}       full comparison result.

All reads/writes are scoped to the authenticated user (``userId == user.email``);
cross-user access returns 404.
"""

import asyncio
import json
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth.azure_ad_auth import User, get_current_user
from app.db.cosmos_client import cosmos_client
from app.models.db_models import ComparisonDocument
from app.services import audit_service, comparison_service, version_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comparison", tags=["Comparison"])

_COMPARISON_TTL_SECONDS = 7776000  # 90 days
_MAX_PDF_BYTES = 50 * 1024 * 1024
# Keep the persisted version payload comfortably under the Cosmos 2MB item limit.
_MAX_PAYLOAD_BYTES = 1_700_000


# ── Response models ───────────────────────────────────────────────────────────

class FrameworkInfo(BaseModel):
    key: str
    display_name: str
    control_count: int


class ComparisonStatus(BaseModel):
    comparison_id: str
    status: str
    stage: str = ""
    externalFramework: str = ""
    internalFileName: str = ""
    counts: Dict[str, int] = {}
    error: Optional[str] = None


class BuildStatus(BaseModel):
    comparison_id: str
    buildStatus: str = "none"
    buildVersionId: Optional[str] = None
    buildVersionNumber: Optional[int] = None
    buildError: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_db() -> None:
    if not cosmos_client.database:
        raise HTTPException(status_code=503, detail="Database not available")


async def _ensure() -> None:
    await cosmos_client.ensure_container(
        cosmos_client.COMPARISONS,
        partition_key_paths=["/userId"],
        default_ttl=_COMPARISON_TTL_SECONDS,
    )


def _scrub(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in doc.items() if not k.startswith("_")}


async def _update_job(comparison_id: str, user_id: str, **fields: Any) -> None:
    """Patch a comparison doc (best-effort) and bump updatedAt."""
    doc = await cosmos_client.get_document(
        cosmos_client.COMPARISONS, comparison_id, partition_key=user_id
    )
    if not doc:
        logger.warning("comparison_update_missing", extra={"id": comparison_id})
        return
    doc.update(fields)
    doc["updatedAt"] = _now()
    # Strip Cosmos system fields (_etag/_rid/_self/_ts) before writing back.
    clean = {k: v for k, v in doc.items() if not k.startswith("_")}
    await cosmos_client.upsert_document(cosmos_client.COMPARISONS, clean)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/frameworks", response_model=List[FrameworkInfo])
async def list_frameworks():
    """List external frameworks available for comparison (bundled catalogues)."""
    return [FrameworkInfo(**fw) for fw in comparison_service.list_external_frameworks()]


@router.post("/run", response_model=ComparisonStatus)
async def run_comparison(
    background_tasks: BackgroundTasks,
    external_framework: str = Form(..., description="External framework key (see /frameworks)"),
    pdf_file: UploadFile = File(..., description="Internal control PDF document"),
    user: User = Depends(get_current_user),
):
    """Start an internal-vs-external comparison job for the current user."""
    _require_db()

    # Validate the chosen framework up front so the user gets immediate feedback.
    try:
        display_name, _ = comparison_service.load_external_controls(external_framework)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF document")
    content = await pdf_file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="PDF file is empty")
    if len(content) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="PDF file exceeds 50MB limit")

    await _ensure()

    doc = ComparisonDocument(
        userId=user.email,
        status="pending",
        internalFileName=pdf_file.filename,
        externalFramework=external_framework,
    ).model_dump(mode="json")
    doc["externalFrameworkName"] = display_name
    doc["stage"] = "queued"
    doc["startedAt"] = _now()
    doc["updatedAt"] = _now()
    await cosmos_client.insert_document(cosmos_client.COMPARISONS, doc)

    await audit_service.write_audit(
        user,
        action="comparison.run",
        resource_type=audit_service.RESOURCE_COMPARISON,
        resource_id=doc["id"],
        metadata={"framework": external_framework, "file": pdf_file.filename},
    )

    background_tasks.add_task(
        _run_comparison_job,
        doc["id"], user.email, content, pdf_file.filename, external_framework,
    )
    logger.info("comparison_created", extra={"id": doc["id"], "userId": user.email})

    return ComparisonStatus(
        comparison_id=doc["id"],
        status="pending",
        stage="queued",
        externalFramework=external_framework,
        internalFileName=pdf_file.filename,
    )


@router.get("/status/{comparison_id}", response_model=ComparisonStatus)
async def get_comparison_status(comparison_id: str, user: User = Depends(get_current_user)):
    """Poll the status (and bucket counts once complete) of a comparison job."""
    _require_db()
    doc = await cosmos_client.get_document(
        cosmos_client.COMPARISONS, comparison_id, partition_key=user.email
    )
    if not doc or (doc.get("userId") and doc["userId"] != user.email):
        raise HTTPException(status_code=404, detail="Comparison not found")
    return ComparisonStatus(
        comparison_id=doc["id"],
        status=doc.get("status", "unknown"),
        stage=doc.get("stage", ""),
        externalFramework=doc.get("externalFramework", ""),
        internalFileName=doc.get("internalFileName", ""),
        counts=doc.get("counts", {}) or {},
        error=doc.get("errorMessage"),
    )


@router.get("")
async def list_comparisons(user: User = Depends(get_current_user)):
    """List all comparisons for the current user (newest first)."""
    _require_db()
    await _ensure()
    rows = await cosmos_client.query_documents(
        cosmos_client.COMPARISONS,
        query=(
            "SELECT c.id, c.status, c.stage, c.externalFramework, c.externalFrameworkName, "
            "c.internalFileName, c.counts, c.timestamp, c.startedAt, c.completedAt "
            "FROM c WHERE c.userId = @userId ORDER BY c.timestamp DESC"
        ),
        parameters=[{"name": "@userId", "value": user.email}],
        partition_key=user.email,
    )
    return {"comparisons": rows}


@router.get("/{comparison_id}")
async def get_comparison(comparison_id: str, user: User = Depends(get_current_user)):
    """Return the full comparison result document."""
    _require_db()
    doc = await cosmos_client.get_document(
        cosmos_client.COMPARISONS, comparison_id, partition_key=user.email
    )
    if not doc or (doc.get("userId") and doc["userId"] != user.email):
        raise HTTPException(status_code=404, detail="Comparison not found")
    return _scrub(doc)


# ── Initiative build (full union) ─────────────────────────────────────────────

async def _load_owned_comparison(comparison_id: str, user_email: str) -> Dict[str, Any]:
    doc = await cosmos_client.get_document(
        cosmos_client.COMPARISONS, comparison_id, partition_key=user_email
    )
    if not doc or (doc.get("userId") and doc["userId"] != user_email):
        raise HTTPException(status_code=404, detail="Comparison not found")
    return doc


@router.post("/{comparison_id}/build-initiative", response_model=BuildStatus)
async def build_initiative(
    comparison_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Build an Azure Policy initiative from the full union of this comparison.

    Idempotent: a build already running returns 409; an already-completed build
    returns its existing version instead of rebuilding.
    """
    _require_db()
    doc = await _load_owned_comparison(comparison_id, user.email)

    if doc.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Comparison is not completed yet")
    if not ((doc.get("result") or {}).get("internal_controls")):
        raise HTTPException(
            status_code=400,
            detail="This comparison predates union-build support. Please re-run it.",
        )

    build_status = doc.get("buildStatus")
    if build_status == "building":
        raise HTTPException(status_code=409, detail="An initiative build is already in progress")
    if build_status == "completed" and doc.get("buildVersionId"):
        return BuildStatus(
            comparison_id=comparison_id,
            buildStatus="completed",
            buildVersionId=doc.get("buildVersionId"),
            buildVersionNumber=doc.get("buildVersionNumber"),
        )

    await _update_job(
        comparison_id, user.email,
        buildStatus="building", buildError=None,
        buildVersionId=None, buildVersionNumber=None,
    )
    await audit_service.write_audit(
        user,
        action="comparison.build_initiative",
        resource_type=audit_service.RESOURCE_COMPARISON,
        resource_id=comparison_id,
    )
    background_tasks.add_task(_run_build_job, comparison_id, user.email)
    return BuildStatus(comparison_id=comparison_id, buildStatus="building")


@router.get("/{comparison_id}/build-status", response_model=BuildStatus)
async def get_build_status(comparison_id: str, user: User = Depends(get_current_user)):
    """Poll the status of an initiative build for a comparison."""
    _require_db()
    doc = await _load_owned_comparison(comparison_id, user.email)
    return BuildStatus(
        comparison_id=comparison_id,
        buildStatus=doc.get("buildStatus", "none"),
        buildVersionId=doc.get("buildVersionId"),
        buildVersionNumber=doc.get("buildVersionNumber"),
        buildError=doc.get("buildError"),
    )


# ── Background job ─────────────────────────────────────────────────────────────

async def _run_comparison_job(
    comparison_id: str,
    user_id: str,
    content: bytes,
    filename: str,
    framework_key: str,
) -> None:
    """Extract internal controls, load external catalogue, run the LLM diff."""
    tmp_dir = tempfile.mkdtemp(prefix="compliance_iq_compare_")
    try:
        from app.pipeline import (
            PipelineConfig,
            extract_text_from_pdf,
            get_pdf_metadata,
            extract_controls_from_text,
        )

        config = PipelineConfig.from_env()
        errors = config.validate()
        if errors:
            raise RuntimeError(f"Config errors: {'; '.join(errors)}")

        await _update_job(comparison_id, user_id, status="running", stage="extracting_text")

        # Use only the basename to avoid path traversal via a crafted filename.
        pdf_path = Path(tmp_dir) / (Path(filename).name or "internal.pdf")
        pdf_path.write_bytes(content)
        metadata = await asyncio.to_thread(get_pdf_metadata, str(pdf_path))
        text = await asyncio.to_thread(extract_text_from_pdf, str(pdf_path), config.max_pdf_pages)

        await _update_job(comparison_id, user_id, stage="extracting_controls")
        extraction = await asyncio.to_thread(extract_controls_from_text, text, config, metadata)
        internal = [
            {
                "id": c.control_id,
                "title": c.control_title,
                "description": c.control_description,
                "domain": c.domain,
            }
            for c in extraction.controls
        ]
        if not internal:
            raise RuntimeError("No controls were extracted from the internal document")

        display_name, external_controls = comparison_service.load_external_controls(framework_key)

        await _update_job(
            comparison_id, user_id,
            stage="comparing", frameworkName=extraction.framework_name,
        )
        result = await comparison_service.compare_controls(internal, external_controls, config)

        await _update_job(
            comparison_id, user_id,
            status="completed",
            stage="completed",
            counts=result["counts"],
            result={
                "matches": result["matches"],
                "summary": result["summary"],
                "internal_framework": extraction.framework_name,
                "external_framework": display_name,
                "internal_count": len(internal),
                "external_count": len(external_controls),
                "internal_controls": internal,
            },
            errorMessage=None,
            completedAt=_now(),
        )
        await audit_service.write_audit(
            user_id,
            action="comparison.completed",
            resource_type=audit_service.RESOURCE_COMPARISON,
            resource_id=comparison_id,
            metadata=result["counts"],
        )
        logger.info("comparison_completed", extra={"id": comparison_id, "counts": result["counts"]})
    except Exception as exc:  # noqa: BLE001 — persist failure, never crash the worker
        logger.exception("comparison_job_failed", extra={"id": comparison_id})
        await _update_job(
            comparison_id, user_id,
            status="failed", stage="failed",
            errorMessage=str(exc)[:500], completedAt=_now(),
        )
        await audit_service.write_audit(
            user_id,
            action="comparison.failed",
            resource_type=audit_service.RESOURCE_COMPARISON,
            resource_id=comparison_id,
            metadata={"error": str(exc)[:200]},
            success=False,
            error_message=str(exc)[:500],
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

async def _run_build_job(comparison_id: str, user_id: str) -> None:
    """Build initiative artifacts from the comparison's full union and persist a version."""
    tmp_dir = tempfile.mkdtemp(prefix="compliance_iq_build_")
    try:
        from app.pipeline import (
            PipelineConfig,
            map_controls_to_azure_policies,
            validate_mappings,
            build_initiative_artifacts,
        )

        doc = await cosmos_client.get_document(
            cosmos_client.COMPARISONS, comparison_id, partition_key=user_id
        )
        if not doc:
            logger.warning("build_job_comparison_missing", extra={"id": comparison_id})
            return

        config = PipelineConfig.from_env()
        errors = config.validate()
        if errors:
            raise RuntimeError(f"Config errors: {'; '.join(errors)}")

        extraction = comparison_service.build_union_extraction(doc)
        if not extraction.controls:
            raise RuntimeError("Union contained no controls to build an initiative from")

        mappings = await asyncio.to_thread(map_controls_to_azure_policies, extraction, config)
        validation = await asyncio.to_thread(validate_mappings, extraction, mappings)
        created = await asyncio.to_thread(
            build_initiative_artifacts, extraction, mappings, validation, tmp_dir
        )

        files: List[Dict[str, str]] = []
        omitted: List[str] = []
        running = 0
        for path_str in created:
            p = Path(path_str)
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001 — skip anything unreadable
                continue
            # Guard the Cosmos 2MB item limit: keep files until the budget is spent.
            if running + len(text.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
                omitted.append(p.name)
                continue
            running += len(text.encode("utf-8"))
            files.append({"name": p.name, "content": text})

        counts = (doc.get("result") or {}).get("counts", {}) or {}
        artifact_payload = {
            "framework_name": extraction.framework_name,
            "source_comparison_id": comparison_id,
            "summary": extraction.summary,
            "counts": counts,
            "control_count": len(extraction.controls),
            "automatable_count": sum(1 for m in mappings if getattr(m, "is_automatable", False)),
            "files": files,
            "omitted_files": omitted,
        }

        version = await version_service.create_version(
            user_id=user_id,
            artifact_payload=artifact_payload,
            source_comparison_id=comparison_id,
            metadata={
                "source": "comparison_union",
                "internalFileName": doc.get("internalFileName"),
                "externalFramework": doc.get("externalFramework"),
            },
        )

        await _update_job(
            comparison_id, user_id,
            buildStatus="completed",
            buildVersionId=version.get("id"),
            buildVersionNumber=version.get("version_number"),
            buildError=None,
        )
        await audit_service.write_audit(
            user_id,
            action="comparison.build_completed",
            resource_type=audit_service.RESOURCE_COMPARISON,
            resource_id=comparison_id,
            metadata={"versionId": version.get("id"), "versionNumber": version.get("version_number")},
        )
        logger.info(
            "comparison_build_completed",
            extra={"id": comparison_id, "versionId": version.get("id")},
        )
    except Exception as exc:  # noqa: BLE001 — persist failure, never crash the worker
        logger.exception("comparison_build_failed", extra={"id": comparison_id})
        await _update_job(
            comparison_id, user_id,
            buildStatus="failed", buildError=str(exc)[:500],
        )
        await audit_service.write_audit(
            user_id,
            action="comparison.build_failed",
            resource_type=audit_service.RESOURCE_COMPARISON,
            resource_id=comparison_id,
            metadata={"error": str(exc)[:200]},
            success=False,
            error_message=str(exc)[:500],
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
