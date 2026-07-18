"""Tests that ApiClient.generate_policy_initiative forwards operator-supplied
parameter values so the backend can include parameterized built-ins.

The opt-in feature only works if the frontend actually sends
``policy_parameter_values`` in the ``/policy/generate`` payload — and omits the
key entirely when nothing is supplied (so behaviour is unchanged by default).
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
    def raise_for_status(self):
        return None

    def json(self):
        return {"ok": True}


class _FakeClient:
    """Records the JSON payload of the generate request."""

    def __init__(self, recorder):
        self._recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, url, json=None, headers=None):
        self._recorder.append(json)
        return _FakeResponse()


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setitem(sys.modules, "streamlit", _FakeStreamlit())
    sys.modules.pop("utils.api_client", None)
    from utils.api_client import APIClient  # noqa: WPS433

    recorder: list[dict] = []
    client = APIClient(base_url="http://backend.test")
    monkeypatch.setattr(client, "_get_client", lambda: _FakeClient(recorder))
    return client, recorder


def test_parameter_values_are_forwarded(api_client):
    client, recorder = api_client
    values = {"f32ca068-2ada-4705-b5b5-84ce89422846": {"vaultName": "rsv-prod"}}

    client.generate_policy_initiative(
        mappings=[],
        framework_name="Framework",
        policy_parameter_values=values,
    )

    assert recorder[0]["policy_parameter_values"] == values


def test_key_omitted_when_no_values(api_client):
    client, recorder = api_client

    client.generate_policy_initiative(mappings=[], framework_name="Framework")

    assert "policy_parameter_values" not in recorder[0]


def test_empty_dict_is_omitted(api_client):
    client, recorder = api_client

    client.generate_policy_initiative(
        mappings=[], framework_name="Framework", policy_parameter_values={}
    )

    assert "policy_parameter_values" not in recorder[0]
