"""
Route-level tests: the policy generation endpoints record the generated
initiative to the user's workspace server-side (so it is saved reliably,
independent of the frontend).

Run from app/ with:
  AZURE_OPENAI_ENDPOINT=https://dummy.openai.azure.com/ ENABLE_AUTH=false \
  PYTHONPATH=backend python -m pytest tests/test_policy_activity_recording.py -q -p no:cacheprovider
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import policy as policy_routes


def _valid_mapping(extra: dict | None = None) -> dict:
    m = {
        "external_control_id": "EXT-1",
        "external_control_name": "Encrypt data at rest",
        "mcsb_control_id": "DP-4",
        "mcsb_control_name": "Enable data at rest encryption by default",
        "mcsb_domain": "Data Protection",
        "confidence_score": 0.9,
        "reasoning": "Direct match on encryption-at-rest intent.",
        "azure_policy_ids": ["4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b"],
        "mapping_type": "exact",
    }
    if extra:
        m.update(extra)
    return m


def _mcsb_payload() -> dict:
    return {
        "framework_name": "Test Framework",
        "mappings": [_valid_mapping()],
        "min_confidence_threshold": 0.0,
        "enforce_mode": False,
    }


def _fake_policy_service() -> MagicMock:
    svc = MagicMock()
    response = MagicMock()
    response.included_policies = 1
    response.excluded_policies = 0
    response.model_dump.return_value = {"included_policies": 1, "excluded_policies": 0}
    response.initiative.to_azure_json.return_value = {"properties": {}}
    svc.generate_initiative.return_value = response
    svc.export_as_bicep.return_value = "// bicep"
    svc.generate_deployment_script.return_value = {"powershell": "ps", "cli": "cli"}
    return svc


class TestMcsbRecording:
    def test_generate_records_export_server_side(self):
        record = AsyncMock()
        cosmos = MagicMock(database=None)  # not ready → skip artifact persist
        with patch.object(policy_routes, "get_policy_service", return_value=_fake_policy_service()), \
             patch.object(policy_routes, "cosmos_client", cosmos), \
             patch.object(policy_routes.activity_service, "record_export", record):
            app = FastAPI()
            app.include_router(policy_routes.router, prefix="/api/v1")
            client = TestClient(app)
            resp = client.post(
                "/api/v1/policy/generate",
                json=_mcsb_payload(),
                headers={"X-Session-ID": "sess-1"},
            )
        assert resp.status_code == 200, resp.text
        record.assert_awaited_once()
        kwargs = record.await_args.kwargs
        assert kwargs["artifact_type"] == "mcsb_initiative"
        assert kwargs["framework"] == "Test Framework"
        assert kwargs["control_count"] == 1
        assert kwargs["session_id"] == "sess-1"
        # Downloadable multi-format envelope is stored as content.
        import json as _json
        envelope = _json.loads(kwargs["content"])
        names = [f["name"] for f in envelope["files"]]
        assert any(n.endswith("_initiative.json") for n in names)
        assert any(n.endswith(".bicep") for n in names)

    def test_record_failure_does_not_break_generation(self):
        record = AsyncMock(side_effect=RuntimeError("cosmos down"))
        cosmos = MagicMock(database=None)
        with patch.object(policy_routes, "get_policy_service", return_value=_fake_policy_service()), \
             patch.object(policy_routes, "cosmos_client", cosmos), \
             patch.object(policy_routes.activity_service, "record_export", record):
            app = FastAPI()
            app.include_router(policy_routes.router, prefix="/api/v1")
            client = TestClient(app)
            resp = client.post("/api/v1/policy/generate", json=_mcsb_payload())
        # Recording is best-effort: generation still succeeds.
        assert resp.status_code == 200, resp.text


class TestSlzRecording:
    def _slz_payload(self) -> dict:
        return {
            "framework_name": "Test Framework",
            "allowed_locations": ["swedencentral"],
            "mappings": [
                _valid_mapping({"sovereignty": {"sovereignty_level": "L2"}})
            ],
        }

    def test_generate_slz_records_export_server_side(self):
        record = AsyncMock()
        cosmos = MagicMock(database=None)
        svc = MagicMock()
        svc.generate_slz_initiatives.return_value = {"archetype-a": {"json": {}}}
        with patch.object(policy_routes, "get_policy_service", return_value=svc), \
             patch.object(policy_routes, "cosmos_client", cosmos), \
             patch.object(policy_routes.activity_service, "record_export", record):
            app = FastAPI()
            app.include_router(policy_routes.router, prefix="/api/v1")
            client = TestClient(app)
            resp = client.post(
                "/api/v1/policy/generate/slz",
                json=self._slz_payload(),
                headers={"X-Session-ID": "sess-2"},
            )
        assert resp.status_code == 200, resp.text
        record.assert_awaited_once()
        kwargs = record.await_args.kwargs
        assert kwargs["artifact_type"] == "slz_initiative"
        assert kwargs["control_count"] == 1
        assert kwargs["session_id"] == "sess-2"
