"""Tests for user-facing AI mapping progress formatting."""

from components.mapping_progress import build_mapping_activity, find_active_mapping_job


def test_activity_marks_current_mapping_stage_as_active():
    activity = build_mapping_activity(45, 3, 8, "mapping_controls")

    assert activity == [
        {"label": "Mapping job received and queued", "state": "complete"},
        {
            "label": "Preparing Microsoft Cloud Security Benchmark context",
            "state": "complete",
        },
        {"label": "Mapping controls (3/8 controls mapped)", "state": "active"},
        {"label": "Preparing mappings for review", "state": "pending"},
    ]


def test_activity_bounds_mapping_progress_and_counts():
    activity = build_mapping_activity(999, -1, -4, "")

    assert all(item["state"] == "complete" for item in activity)
    assert activity[2]["label"] == "Mapping controls (0/0 controls mapped)"


def test_active_mapping_job_uses_most_recent_active_task():
    tasks = [
        {"job_id": "completed", "status": "completed", "started_at": "2026-07-13T10:00:00Z"},
        {"job_id": "older", "status": "running", "started_at": "2026-07-13T10:01:00Z"},
        {"job_id": "newer", "status": "pending", "started_at": "2026-07-13T10:02:00Z"},
    ]

    assert find_active_mapping_job(tasks) == "newer"


def test_active_mapping_job_returns_none_without_active_task():
    assert find_active_mapping_job([{"job_id": "done", "status": "completed"}]) is None
