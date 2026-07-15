"""Presentation helpers for the AI mapping progress experience."""

from __future__ import annotations

from typing import Literal, TypedDict


ActivityState = Literal["complete", "active", "pending"]


class MappingActivity(TypedDict):
    """A user-safe progress event derived from an AI mapping job status."""

    label: str
    state: ActivityState


def find_active_mapping_job(tasks: list[dict]) -> str | None:
    """Return the newest active mapping job ID from the session task registry."""
    active_tasks = [
        task
        for task in tasks
        if task.get("status") in {"pending", "running"}
    ]
    if not active_tasks:
        return None
    newest_task = max(active_tasks, key=lambda task: task.get("started_at", ""))
    return newest_task.get("job_id")


def build_mapping_activity(
    progress: int,
    mapped_controls: int,
    total_controls: int,
    status: str,
) -> list[MappingActivity]:
    """Create a concise activity feed without exposing control content."""
    safe_progress = max(0, min(progress, 100))
    safe_mapped = max(0, mapped_controls)
    safe_total = max(0, total_controls)
    current_status = status.replace("_", " ").strip().capitalize() or "Mapping controls"

    def state_for(start: int, end: int) -> ActivityState:
        if safe_progress >= end:
            return "complete"
        if safe_progress >= start:
            return "active"
        return "pending"

    return [
        {"label": "Mapping job received and queued", "state": state_for(0, 5)},
        {"label": "Preparing Microsoft Cloud Security Benchmark context", "state": state_for(5, 15)},
        {
            "label": f"{current_status} ({safe_mapped}/{safe_total} controls mapped)",
            "state": state_for(15, 95),
        },
        {"label": "Preparing mappings for review", "state": state_for(95, 100)},
    ]
