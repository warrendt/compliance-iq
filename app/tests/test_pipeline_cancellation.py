"""A long stage the user cannot abort is a bug, not an inconvenience.

Mapping is now per-control against the whole catalog rather than a handful of
batched calls, so the mapping stage is roughly an order of magnitude longer than
it was. Before this change ``_run_pipeline_job`` had no cancellation check at
all - ``ensure_not_cancelled`` existed only in the extraction job - so a user
who pressed cancel watched the job keep running and keep spending tokens.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pytest  # noqa: E402

from app.api.routes import pipeline as pipeline_routes  # noqa: E402


@pytest.fixture
def job(monkeypatch, tmp_path):
    """A minimal in-flight job with the slow stages stubbed out."""
    job_id = "job-1"
    record = {
        "job_id": job_id,
        "status": "pending",
        "pdf_filename": "framework.pdf",
        "pdf_content": b"%PDF-1.4 stub",
        "min_confidence": 0.5,
        "allowed_locations": ["southafricanorth"],
    }
    monkeypatch.setitem(pipeline_routes._jobs, job_id, record)
    monkeypatch.setattr(pipeline_routes, "_cosmos_upsert_job", lambda *a, **k: None)
    return record


def _stub_pipeline(monkeypatch, *, on_map=None, controls=("C-1", "C-2")):
    """Replace the pipeline package the job imports from."""
    import types

    from app.pipeline.models import (
        ControlExtractionResult,
        ControlPolicyMapping,
        ExtractedControl,
    )

    extraction = ControlExtractionResult(
        framework_name="Test Framework",
        controls=[
            ExtractedControl(
                control_id=c,
                control_title=f"Control {c}",
                control_description="A requirement.",
                domain="Data Protection",
                control_type="Technical",
            )
            for c in controls
        ],
        summary="A test framework.",
    )

    def _map(extraction_arg, config, progress_callback=None):
        total = len(extraction_arg.controls)
        results = []
        for index, control in enumerate(extraction_arg.controls, start=1):
            if on_map:
                on_map(index, total)
            if progress_callback:
                progress_callback(index, total)
            results.append(
                ControlPolicyMapping(
                    control_id=control.control_id,
                    control_title=control.control_title,
                    domain=control.domain,
                    confidence_score=0.9,
                    mapping_rationale="Relevant",
                    is_automatable=False,
                )
            )
        return results

    class _Config:
        batch_size = 5
        max_pdf_pages = 100

        @staticmethod
        def from_env():
            return _Config()

        def validate(self):
            return []

    stub = types.SimpleNamespace(
        PipelineConfig=_Config,
        extract_text_from_pdf=lambda *a, **k: "text",
        get_pdf_metadata=lambda *a, **k: {"pages": 1},
        extract_controls_from_text=lambda *a, **k: extraction,
        map_controls_to_azure_policies=_map,
        validate_mappings=lambda *a, **k: types.SimpleNamespace(is_valid=True),
        build_initiative_artifacts=lambda **k: [],
    )
    monkeypatch.setitem(sys.modules, "app.pipeline", stub)


def test_cancelling_during_mapping_stops_the_run(monkeypatch, job):
    """The per-control progress hook is the only place inside a long mapping
    stage where cancellation can be honoured."""
    mapped = []

    def on_map(index, total):
        mapped.append(index)
        if index == 1:
            job["cancel_requested"] = True

    _stub_pipeline(monkeypatch, on_map=on_map, controls=("C-1", "C-2", "C-3"))

    pipeline_routes._run_pipeline_job("job-1")

    assert job["status"] == "cancelled"
    # It stopped on the control the cancellation arrived during, rather than
    # finishing all three.
    assert mapped == [1]


def test_a_cancelled_job_is_not_reported_as_failed(monkeypatch, job):
    """Reporting a deliberate cancellation as a failure sends the user looking
    for a defect they caused."""
    job["cancel_requested"] = True
    _stub_pipeline(monkeypatch)

    pipeline_routes._run_pipeline_job("job-1")

    assert job["status"] == "cancelled"
    assert "error" not in job
    assert job["stage"] == "Cancelled"


def test_a_cancelled_job_drops_the_raw_document(monkeypatch, job):
    """The success path already excludes the PDF from the persisted copy; a
    terminal job should not push the customer's document into storage either."""
    job["cancel_requested"] = True
    _stub_pipeline(monkeypatch)

    pipeline_routes._run_pipeline_job("job-1")

    assert "pdf_content" not in job


def test_a_failed_job_drops_the_raw_document(monkeypatch, job):
    _stub_pipeline(monkeypatch)
    stub = sys.modules["app.pipeline"]

    def _boom(*a, **k):
        raise RuntimeError("Azure OpenAI is unreachable")

    monkeypatch.setattr(stub, "extract_controls_from_text", _boom)

    pipeline_routes._run_pipeline_job("job-1")

    assert job["status"] == "failed"
    assert "unreachable" in job["error"]
    assert "pdf_content" not in job


def test_an_uncancelled_job_runs_to_completion(monkeypatch, job):
    _stub_pipeline(monkeypatch)

    pipeline_routes._run_pipeline_job("job-1")

    assert job["status"] == "completed"
    assert job["progress"] == 100
