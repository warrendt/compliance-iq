"""Presentation helpers for the PDF extraction progress experience."""

from __future__ import annotations

from typing import Literal, TypedDict


ActivityState = Literal["complete", "active", "pending"]
_MAX_JOB_ACTIVITY_EVENTS = 6


class PdfExtractionActivity(TypedDict):
    """A user-safe progress event derived from a backend job status."""

    label: str
    state: ActivityState


def select_job_log_events(logs: list[dict], job_id: str) -> list[dict]:
    """Return bounded log entries associated with the active job."""
    matching_events = [
        entry
        for entry in logs
        if job_id and job_id in str(entry.get("message", ""))
    ]
    return matching_events[-_MAX_JOB_ACTIVITY_EVENTS:]


def build_pdf_extraction_activity(
    progress: int,
    stage: str,
) -> list[PdfExtractionActivity]:
    """Create a concise activity feed without exposing raw backend logs."""
    safe_progress = max(0, min(progress, 100))
    current_stage = stage or "Waiting for an extraction worker"

    def state_for(start: int, end: int) -> ActivityState:
        if safe_progress >= end:
            return "complete"
        if safe_progress >= start:
            return "active"
        return "pending"

    return [
        {"label": "PDF received and queued", "state": state_for(0, 5)},
        {"label": "Reading document text", "state": state_for(5, 20)},
        {"label": current_stage, "state": state_for(20, 95)},
        {"label": "Preparing extracted controls for review", "state": state_for(95, 100)},
    ]
