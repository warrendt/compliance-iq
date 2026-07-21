"""Tests for the frontend workspace activity-recording writers.

These ``record_*`` methods were dropped in a mix-merge and restored: the
per-user workspace (My Workspace tab) stays empty unless the pipeline pages
POST each step (upload/mappings/export/activity) to ``/api/v1/user/*``.

The writers are best-effort: they must POST the documented payload shape and
must never raise into the UI (return ``None`` on any transport failure).
"""
import sys
import types

import pytest


class _FakeSessionState(dict):
    pass


class _FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = _FakeSessionState()

    def cache_resource(self, func=None, **_):
        return func if func is not None else (lambda f: f)

    def cache_data(self, func=None, **_):
        return func if func is not None else (lambda f: f)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _RecordingClient:
    """Captures (url, json) for each POST and echoes an id back."""

    def __init__(self, recorder):
        self._recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, url, json=None, timeout=None):
        self._recorder.append((url, json))
        return _FakeResponse({"id": "rec-1", **(json or {})})


class _FailingClient:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, *_, **__):
        raise RuntimeError("backend unreachable")


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setitem(sys.modules, "streamlit", _FakeStreamlit())
    sys.modules.pop("utils.api_client", None)
    from utils.api_client import APIClient  # noqa: WPS433

    recorder: list[tuple] = []
    client = APIClient(base_url="http://backend.test")
    monkeypatch.setattr(client, "_get_client", lambda: _RecordingClient(recorder))
    return client, recorder


def test_record_upload_posts_expected_payload(api_client):
    client, recorder = api_client
    out = client.record_upload(
        file_name="ccc.csv",
        category="controls",
        row_count=120,
        column_names=["control_id", "description"],
        controls=[{"control_id": "1-1"}],
        metadata={"framework": "NCA CCC"},
    )
    assert out is not None
    url, payload = recorder[-1]
    assert url == "http://backend.test/api/v1/user/uploads"
    assert payload["fileName"] == "ccc.csv"
    assert payload["category"] == "controls"
    assert payload["rowCount"] == 120
    assert payload["columnNames"] == ["control_id", "description"]
    assert payload["controls"] == [{"control_id": "1-1"}]
    assert payload["metadata"] == {"framework": "NCA CCC"}


def test_record_mappings_posts_to_mappings_route(api_client):
    client, recorder = api_client
    out = client.record_mappings(
        framework="NCA CCC",
        mappings=[{"control_id": "1-1", "confidence_score": 0.9}],
        metadata={"jobId": "job-1"},
    )
    assert out is not None
    url, payload = recorder[-1]
    assert url == "http://backend.test/api/v1/user/mappings"
    assert payload["framework"] == "NCA CCC"
    assert payload["mappings"][0]["control_id"] == "1-1"
    assert payload["metadata"] == {"jobId": "job-1"}


def test_record_export_posts_camelcase_fields(api_client):
    client, recorder = api_client
    out = client.record_export(
        framework="NCA CCC",
        artifact_type="mcsb_initiative",
        control_count=76,
        file_name="ccc_initiative.json",
        session_id="sess-1",
        metadata={"enforceMode": False},
    )
    assert out is not None
    url, payload = recorder[-1]
    assert url == "http://backend.test/api/v1/user/exports"
    assert payload["artifactType"] == "mcsb_initiative"
    assert payload["controlCount"] == 76
    assert payload["fileName"] == "ccc_initiative.json"
    assert payload["sessionId"] == "sess-1"
    assert payload["metadata"] == {"enforceMode": False}


def test_record_activity_posts_to_activity_route(api_client):
    client, recorder = api_client
    out = client.record_activity(action="edit", summary="Edited a mapping")
    assert out is not None
    url, payload = recorder[-1]
    assert url == "http://backend.test/api/v1/user/activity"
    assert payload["action"] == "edit"
    assert payload["summary"] == "Edited a mapping"
    assert payload["resourceType"] == "edit"


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.record_upload(file_name="x.csv"),
        lambda c: c.record_mappings(framework="F", mappings=[]),
        lambda c: c.record_export(framework="F"),
        lambda c: c.record_activity(action="a", summary="s"),
    ],
)
def test_record_writers_are_best_effort(monkeypatch, call):
    monkeypatch.setitem(sys.modules, "streamlit", _FakeStreamlit())
    sys.modules.pop("utils.api_client", None)
    from utils.api_client import APIClient  # noqa: WPS433

    client = APIClient(base_url="http://backend.test")
    monkeypatch.setattr(client, "_get_client", lambda: _FailingClient())
    # A transport failure must be swallowed (returns None), never raised.
    assert call(client) is None
