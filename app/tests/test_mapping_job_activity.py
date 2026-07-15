"""Tests for durable, job-scoped mapping execution traces."""

from app.models.mapping import MappingJob, record_mapping_activity


def test_mapping_activity_is_bounded_and_contains_safe_event_fields():
    job = MappingJob(
        job_id="job-1",
        framework_name="Framework",
        status="pending",
        total_controls=2,
    )

    for index in range(55):
        record_mapping_activity(job, f"Mapped {index}/55 controls")

    assert len(job.activity) == 50
    assert job.activity[0]["message"] == "Mapped 5/55 controls"
    assert job.activity[-1]["message"] == "Mapped 54/55 controls"
    assert set(job.activity[-1]) == {"ts", "level", "message"}
