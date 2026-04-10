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

    for task in active:
        job_id = task["job_id"]
        task_type = task["type"]

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
            update_task(job_id, status="failed", error=str(exc))

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
    job_status = status.get("status", "")
    progress = status.get("progress", 0)
    stage = status.get("stage", "")

    if job_status == "completed":
        update_task(
            job_id,
            status="completed",
            progress=100,
            stage="completed",
            result=status,
        )
    elif job_status == "failed":
        update_task(
            job_id,
            status="failed",
            error=status.get("error", "Unknown error"),
        )
    else:
        update_task(
            job_id,
            status="running",
            progress=progress,
            stage=stage,
            mapped=status.get("controls_mapped", 0),
        )
