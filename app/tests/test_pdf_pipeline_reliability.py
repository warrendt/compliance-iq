"""Regression tests for resilient PDF upload and asynchronous extraction."""

from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, UploadFile

from app.api.routes import pipeline


def test_frontend_proxy_accepts_documented_pdf_limit():
    """The Nginx proxy must not reject valid PDFs before the backend sees them."""
    nginx_config = (
        __file__.replace("tests/test_pdf_pipeline_reliability.py", "frontend/nginx.conf")
    )
    with open(nginx_config, encoding="utf-8") as config:
        assert "client_max_body_size 50m;" in config.read()


def test_frontend_proxy_routes_deep_linked_streamlit_websockets():
    """Progress updates need deep-linked Streamlit WebSockets to reach the app."""
    nginx_config = (
        __file__.replace("tests/test_pdf_pipeline_reliability.py", "frontend/nginx.conf")
    )
    with open(nginx_config, encoding="utf-8") as config:
        contents = config.read()

    assert "location ~ ^/.+/_stcore/(health|host-config)$" in contents
    assert "return 404;" in contents
    assert "location ~ ^/.+/_stcore/(.*)$" in contents
    assert "proxy_pass http://streamlit_upstream/_stcore/$1$is_args$args;" in contents
    assert "location ~ ^/.+/(static/.*)$" in contents
    assert "proxy_pass http://streamlit_upstream/$1$is_args$args;" in contents


def test_cosmos_job_document_excludes_pdf_content_and_has_id(monkeypatch):
    """Cosmos persistence must use a valid, bounded job-status document."""
    captured = []

    class Container:
        def upsert_item(self, document):
            captured.append(document)

    monkeypatch.setattr(pipeline, "_cosmos_container", Container())
    job = {
        "job_id": "job-1",
        "status": "pending",
        "pdf_content": b"binary-pdf",
    }

    pipeline._cosmos_upsert_job(job)

    assert captured == [{"job_id": "job-1", "status": "pending", "id": "job-1"}]


def test_pipeline_cosmos_initialization_supports_serverless_accounts(monkeypatch):
    """Pipeline-job persistence must not configure throughput on serverless Cosmos."""

    class Container:
        pass

    class Database:
        def __init__(self):
            self.container_kwargs = None

        def create_container_if_not_exists(self, **kwargs):
            self.container_kwargs = kwargs
            return Container()

    class Client:
        def __init__(self, *_args, **_kwargs):
            self.database = Database()

        def create_database_if_not_exists(self, **_kwargs):
            return self.database

    monkeypatch.setenv("COSMOS_DB_ENDPOINT", "https://example.documents.azure.com:443/")
    monkeypatch.setattr(pipeline, "CosmosClient", Client)
    monkeypatch.setattr(pipeline, "DefaultAzureCredential", lambda **_kwargs: object())
    monkeypatch.setattr(pipeline, "_cosmos_client", None)
    monkeypatch.setattr(pipeline, "_cosmos_container", None)

    pipeline._init_cosmos()

    assert pipeline._cosmos_container is not None
    assert "offer_throughput" not in pipeline._cosmos_client.database.container_kwargs
    assert pipeline._cosmos_client.database.container_kwargs["id"] == "pipeline-jobs"


@pytest.mark.asyncio
async def test_recovered_active_job_is_marked_failed_instead_of_stuck(monkeypatch):
    """A restart cannot leave an orphaned job permanently in a running state."""
    recovered_job = {
        "id": "job-2",
        "job_id": "job-2",
        "status": "extracting_controls",
        "progress": 40,
        "stage": "AI extracting controls",
    }
    persisted = []
    pipeline._jobs.clear()
    monkeypatch.setattr(pipeline, "_cosmos_get_job", lambda _: recovered_job)
    monkeypatch.setattr(pipeline, "_cosmos_upsert_job", lambda job: persisted.append(job.copy()))

    status = await pipeline.get_pipeline_status("job-2")

    assert status.status == "failed"
    assert status.stage == "Interrupted"
    assert "restarted" in status.error
    assert persisted[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_extract_submission_returns_before_background_work(monkeypatch):
    """Submitting a PDF only queues work; it never waits for Azure OpenAI."""
    job = {
        "id": "job-3",
        "job_id": "job-3",
        "status": "pending",
        "progress": 0,
        "stage": "Queued",
        "target_platform": "extract",
    }
    queued_worker = AsyncMock()
    monkeypatch.setattr(pipeline, "_create_job", lambda **_: ("job-3", job))
    monkeypatch.setattr(pipeline, "_run_pdf_extraction_job", queued_worker)

    background_tasks = BackgroundTasks()
    response = await pipeline.start_pdf_extraction(
        background_tasks,
        UploadFile(BytesIO(b"%PDF-1.7"), filename="framework.pdf"),
    )

    assert response.job_id == "job-3"
    assert response.status == "pending"
    assert len(background_tasks.tasks) == 1
    queued_worker.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancelling_pdf_job_persists_a_terminal_cancelled_status(monkeypatch):
    """Clearing a PDF workflow must stop its backend job from continuing."""
    job = {
        "id": "job-cancel",
        "job_id": "job-cancel",
        "status": "extracting_controls",
        "progress": 35,
        "stage": "AI extracting controls",
    }
    persisted = []
    pipeline._jobs.clear()
    pipeline._jobs["job-cancel"] = job
    monkeypatch.setattr(pipeline, "_cosmos_upsert_job", lambda value: persisted.append(value.copy()))

    response = await pipeline.cancel_pipeline_job("job-cancel")

    assert response.status == "cancelled"
    assert pipeline._jobs["job-cancel"]["cancel_requested"] is True
    assert persisted[-1]["status"] == "cancelled"
