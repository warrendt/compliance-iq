"""
Centralized task/job management for long-running backend operations.

Every long-running operation (PDF extraction, AI mapping, pipeline run)
registers a task here.  The task registry lives in
``st.session_state["task_registry"]`` and survives page navigation.

Task status is polled from the backend on demand; the task status bar
component calls ``poll_active_tasks()`` to refresh all active entries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import streamlit as st

# ── Types ─────────────────────────────────────────────────────────────────

TaskType = Literal[
    "ai_mapping",
    "pdf_extraction",
    "pipeline_run",
    "policy_generation",
]

TaskStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
]


# ── Registry helpers ──────────────────────────────────────────────────────

def _registry() -> Dict[str, Dict[str, Any]]:
    """Return the session-scoped task registry, creating it if absent."""
    if "task_registry" not in st.session_state:
        st.session_state["task_registry"] = {}
    return st.session_state["task_registry"]


def register_task(
    job_id: str,
    task_type: TaskType,
    *,
    description: str = "",
    page_origin: str = "",
    total: int = 0,
    poll_backend: bool = True,
) -> Dict[str, Any]:
    """Register a new background task.

    Args:
        job_id: Backend-assigned job identifier.
        task_type: Category of the task.
        description: Short human-readable label.
        page_origin: Page that launched the task.
        total: Total work items (e.g. number of controls).

    Returns:
        The newly-created task entry dict.
    """
    entry: Dict[str, Any] = {
        "job_id": job_id,
        "type": task_type,
        "poll_backend": poll_backend,
        "status": "running",
        "progress": 0,
        "stage": "",
        "description": description,
        "page_origin": page_origin,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "total": total,
        "mapped": 0,
        "error": None,
        "result": None,
        "transient_failures": 0,
        "last_poll_error": None,
    }
    _registry()[job_id] = entry
    return entry


def update_task(
    job_id: str,
    *,
    status: Optional[TaskStatus] = None,
    progress: Optional[int] = None,
    stage: Optional[str] = None,
    mapped: Optional[int] = None,
    error: Optional[str] = None,
    result: Optional[Any] = None,
) -> None:
    """Update an existing task entry in-place."""
    reg = _registry()
    task = reg.get(job_id)
    if task is None:
        return
    if status is not None:
        task["status"] = status
    if progress is not None:
        task["progress"] = progress
    if stage is not None:
        task["stage"] = stage
    if mapped is not None:
        task["mapped"] = mapped
    if error is not None:
        task["error"] = error
    if result is not None:
        task["result"] = result
    if status in ("completed", "failed", "cancelled") and task["completed_at"] is None:
        task["completed_at"] = datetime.now(timezone.utc).isoformat()


def remove_task(job_id: str) -> None:
    """Remove a task from the registry."""
    _registry().pop(job_id, None)


def get_task(job_id: str) -> Optional[Dict[str, Any]]:
    """Return a task entry or ``None``."""
    return _registry().get(job_id)


def get_active_tasks() -> List[Dict[str, Any]]:
    """Return all tasks with status ``pending`` or ``running``."""
    return [t for t in _registry().values() if t["status"] in ("pending", "running")]


def get_tasks_by_type(task_type: TaskType) -> List[Dict[str, Any]]:
    """Return all tasks (any status) of a given type."""
    return [t for t in _registry().values() if t["type"] == task_type]


def get_all_tasks() -> List[Dict[str, Any]]:
    """Return every task in the registry, newest first."""
    tasks = list(_registry().values())
    tasks.sort(key=lambda t: t.get("started_at", ""), reverse=True)
    return tasks


def has_active_task_of_type(task_type: TaskType) -> bool:
    """Check if there is already an active (pending/running) task of this type."""
    return any(
        t["status"] in ("pending", "running")
        for t in _registry().values()
        if t["type"] == task_type
    )


# ── Polling helpers ──────────────────────────────────────────────────────

def poll_active_tasks(api_client: Any) -> int:
    """Poll the backend for status updates on all active tasks.

    Args:
        api_client: An ``APIClient`` instance used to query job status.

    Returns:
        Number of tasks that are still active after polling.
    """
    active = get_active_tasks()
    still_active = 0

    max_transient_failures = int(st.session_state.get("task_max_transient_failures", 20))
    max_not_found_failures = int(st.session_state.get("task_max_not_found_failures", 6))

    for task in active:
        job_id = task["job_id"]
        task_type = task["type"]
        should_poll_backend = task.get("poll_backend", True)

        if not should_poll_backend:
            # Frontend-managed tasks are updated by the page itself.
            t = get_task(job_id)
            if t and t["status"] in ("pending", "running"):
                still_active += 1
            continue

        try:
            if task_type == "ai_mapping":
                status = api_client.get_job_status(job_id)
                _apply_mapping_status(job_id, status)
            elif task_type in ("pipeline_run", "pdf_extraction"):
                status = api_client.get_pipeline_status(job_id)
                _apply_pipeline_status(job_id, status)
            else:
                # Unknown type — skip
                pass
        except Exception as exc:
            task_now = get_task(job_id) or {}
            transient_failures = int(task_now.get("transient_failures", 0))
            err_text = str(exc).lower()
            is_transient = any(
                token in err_text
                for token in (
                    "timed out",
                    "timeout",
                    "temporarily unavailable",
                    "connection reset",
                    "connection aborted",
                    "502",
                    "503",
                    "504",
                    "404",
                )
            )
            is_not_found = any(
                token in err_text
                for token in (
                    "404",
                    "not found",
                    "job",
                )
            ) and ("not found" in err_text or "404" in err_text)

            # Only fail immediately on clear non-transient client/auth errors.
            is_hard_error = any(
                token in err_text
                for token in (
                    "401",
                    "403",
                    "422",
                    "forbidden",
                    "unauthorized",
                    "validation error",
                )
            )

            if is_hard_error and not is_transient:
                update_task(job_id, status="failed", error=str(exc))
            else:
                next_failures = transient_failures + 1
                task_now["transient_failures"] = next_failures
                task_now["last_poll_error"] = str(exc)

                # Repeated not-found typically means orphaned task/job mismatch.
                if is_not_found and next_failures >= max_not_found_failures:
                    update_task(
                        job_id,
                        status="failed",
                        stage="orphaned",
                        error=(
                            "Task could not be recovered from backend status after multiple attempts. "
                            "Please restart the operation."
                        ),
                    )
                # Generic transient polling failures should eventually fail to avoid infinite hang.
                elif next_failures >= max_transient_failures:
                    update_task(
                        job_id,
                        status="failed",
                        stage="polling_timeout",
                        error=(
                            "Task status polling failed repeatedly and was stopped to avoid a hung state. "
                            "Please retry."
                        ),
                    )
                else:
                    update_task(
                        job_id,
                        status="running",
                        stage="waiting for status (retrying)",
                        error=None,
                    )

        # Re-check after update
        t = get_task(job_id)
        if t and t["status"] in ("pending", "running"):
            still_active += 1

    return still_active


def _apply_mapping_status(job_id: str, status: Dict[str, Any]) -> None:
    """Apply backend mapping job status to the task registry."""
    job_status = status.get("status", "")
    progress = status.get("progress", 0)
    mapped = status.get("mapped_controls", 0)

    if job_status == "completed":
        update_task(
            job_id,
            status="completed",
            progress=100,
            mapped=mapped,
            result=status.get("result"),
        )
    elif job_status == "failed":
        update_task(
            job_id,
            status="failed",
            error=status.get("error_message", "Unknown error"),
        )
    else:
        update_task(
            job_id,
            status="running",
            progress=progress,
            stage=job_status,
            mapped=mapped,
        )


def _apply_pipeline_status(job_id: str, status: Dict[str, Any]) -> None:
    """Apply backend pipeline job status to the task registry."""
    task = get_task(job_id)
    is_pdf_extraction = bool(task and task.get("type") == "pdf_extraction")

    job_status = status.get("status", "")
    progress = status.get("progress", 0)
    stage = status.get("stage", "")

    if is_pdf_extraction:
        st.session_state["pdf_extract_backend_job_id"] = job_id
        st.session_state["pdf_extract_backend_status"] = job_status
        st.session_state["pdf_extract_backend_progress"] = int(progress or 0)
        st.session_state["pdf_extract_backend_stage"] = stage
        if status.get("pdf_filename"):
            st.session_state["pdf_file_name"] = status.get("pdf_filename")

    if job_status == "completed":
        result_payload: Any = status
        extraction_result = status.get("extraction_result")
        if isinstance(extraction_result, dict):
            result_payload = {
                "source_file": status.get("pdf_filename"),
                "extraction": extraction_result,
            }
        update_task(
            job_id,
            status="completed",
            progress=100,
            stage="completed",
            result=result_payload,
        )
        if is_pdf_extraction:
            st.session_state["pdf_extracting"] = False
            st.session_state["pdf_extract_task_id"] = None
        task_after = get_task(job_id)
        if task_after is not None:
            task_after["transient_failures"] = 0
            task_after["last_poll_error"] = None
    elif job_status == "failed":
        update_task(
            job_id,
            status="failed",
            error=status.get("error", "Unknown error"),
        )
        if is_pdf_extraction:
            st.session_state["pdf_extracting"] = False
            st.session_state["pdf_extract_task_id"] = None
    else:
        update_task(
            job_id,
            status="running",
            progress=progress,
            stage=stage,
            mapped=status.get("controls_mapped", 0),
        )
        task_after = get_task(job_id)
        if task_after is not None:
            task_after["transient_failures"] = 0
            task_after["last_poll_error"] = None
