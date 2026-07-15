"""Tests for user-facing PDF extraction progress formatting."""

from components.pdf_progress import (
    build_pdf_extraction_activity,
    select_job_log_events,
)
from components.pdf_upload_state import is_replacement_upload


def test_activity_marks_current_extraction_stage_as_active():
    activity = build_pdf_extraction_activity(
        45,
        "AI extracting controls (3/8 sections)",
    )

    assert activity == [
        {"label": "PDF received and queued", "state": "complete"},
        {"label": "Reading document text", "state": "complete"},
        {"label": "AI extracting controls (3/8 sections)", "state": "active"},
        {"label": "Preparing extracted controls for review", "state": "pending"},
    ]


def test_activity_bounds_progress_and_uses_safe_queue_message():
    activity = build_pdf_extraction_activity(999, "")

    assert all(item["state"] == "complete" for item in activity)
    assert activity[2]["label"] == "Waiting for an extraction worker"


def test_replacement_upload_detects_new_bytes_or_filename():
    assert is_replacement_upload(b"previous", "previous.pdf", b"new", "new.pdf")
    assert is_replacement_upload(b"same", "previous.pdf", b"same", "new.pdf")
    assert not is_replacement_upload(b"same", "framework.pdf", b"same", "framework.pdf")


def test_live_backend_activity_only_includes_current_job_and_is_bounded():
    logs = [
        {"message": "Pipeline job another-job completed"},
        {"message": "PDF extraction job current-job queued"},
        {"message": "PDF extraction job current-job processing"},
        {"message": "PDF extraction job current-job completed"},
    ]

    assert select_job_log_events(logs, "current-job") == logs[1:]
