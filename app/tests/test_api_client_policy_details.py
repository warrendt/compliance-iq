"""Tests for ApiClient.get_policy_details request chunking.

The backend caps ``/api/v1/policy/details`` at 100 GUIDs per request. When an
initiative has more than 100 policies, the client must split the lookup into
batches and merge the results — otherwise the request 422s and the UI falls
back to showing bare GUIDs instead of policy names.
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


class _FakeClient:
    """Records POST payloads and echoes each GUID back as a detail dict."""

    def __init__(self, recorder):
        self._recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, url, json=None, timeout=None):
        ids = json["policy_ids"]
        self._recorder.append(list(ids))
        policies = {pid: {"policy_id": pid, "display_name": pid} for pid in ids}
        return _FakeResponse({"requested": len(ids), "found": len(ids), "policies": policies})


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setitem(sys.modules, "streamlit", _FakeStreamlit())
    sys.modules.pop("utils.api_client", None)
    from utils.api_client import APIClient  # noqa: WPS433

    recorder: list[list[str]] = []
    client = APIClient(base_url="http://backend.test")
    monkeypatch.setattr(client, "_get_client", lambda: _FakeClient(recorder))
    return client, recorder


def test_more_than_100_ids_are_chunked_and_merged(api_client):
    client, recorder = api_client
    ids = [f"{i:08d}-0000-0000-0000-000000000000" for i in range(250)]

    result = client.get_policy_details(ids)

    # 250 ids -> three batches of 100, 100, 50.
    assert [len(batch) for batch in recorder] == [100, 100, 50]
    assert result["requested"] == 250
    assert result["found"] == 250
    assert len(result["policies"]) == 250
    # Every requested GUID is present in the merged result.
    assert set(result["policies"]) == set(ids)


def test_exactly_100_ids_is_a_single_request(api_client):
    client, recorder = api_client
    ids = [f"{i:08d}-0000-0000-0000-000000000000" for i in range(100)]

    result = client.get_policy_details(ids)

    assert len(recorder) == 1
    assert result["found"] == 100


def test_empty_list_makes_no_request(api_client):
    client, recorder = api_client

    result = client.get_policy_details([])

    assert recorder == []
    assert result == {"requested": 0, "found": 0, "policies": {}}
