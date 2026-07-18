"""
Route-level tests: the policy generation endpoints record the generated
initiative server-side (so it is saved reliably, independent of the frontend).

Server-side recording is done by ``version_service.create_version`` (an
immutable, versioned download bundle) plus best-effort persistence to Cosmos DB.
The earlier ``activity_service.record_export`` path was removed when versioning
replaced it, so these tests target the current mechanism.

Run from app/ with:
  AZURE_OPENAI_ENDPOINT=https://dummy.openai.azure.com/ ENABLE_AUTH=false \
  PYTHONPATH=backend python -m pytest tests/test_policy_activity_recording.py -q -p no:cacheprovider
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import policy as policy_routes

_VERSION = {"id": "version-1", "version_number": 1, "semantic_version": "1.0.0"}


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
    svc.generate_security_standard.return_value = {
        "standard_name": "00000000-0000-0000-0000-000000000000",
        "arm_template": "{}",
        "powershell": "Invoke-AzRestMethod",
    }
    return svc


class TestMcsbRecording:
    def test_generate_records_version_server_side(self):
        create_version = AsyncMock(return_value=_VERSION)
        cosmos = MagicMock(database=None)  # not ready -> skip artifact persist
        with patch.object(policy_routes, "get_policy_service", return_value=_fake_policy_service()), \
             patch.object(policy_routes, "cosmos_client", cosmos), \
             patch.object(policy_routes.version_service, "create_version", create_version):
            app = FastAPI()
            app.include_router(policy_routes.router, prefix="/api/v1")
            client = TestClient(app)
            resp = client.post(
                "/api/v1/policy/generate",
                json=_mcsb_payload(),
                headers={"X-Session-ID": "sess-1"},
            )
        assert resp.status_code == 200, resp.text
        create_version.assert_awaited_once()
        kwargs = create_version.await_args.kwargs
        assert kwargs["metadata"]["source"] == "mcsb_initiative"
        assert kwargs["metadata"]["framework_name"] == "Test Framework"
        assert kwargs["metadata"]["mappings_count"] == 1
        # Downloadable multi-format envelope is stored as the artifact payload.
        names = [f["name"] for f in kwargs["artifact_payload"]["files"]]
        assert any(n.endswith("_initiative.json") for n in names)
        assert any(n.endswith(".bicep") for n in names)
        # The response echoes the created version.
        assert resp.json()["version_id"] == "version-1"

    def test_persist_failure_does_not_break_generation(self):
        # Cosmos persistence is best-effort: an upsert failure must not fail the
        # request (the version is already created).
        create_version = AsyncMock(return_value=_VERSION)
        cosmos = MagicMock()
        cosmos.database = object()  # ready -> persistence is attempted
        cosmos.upsert_document = AsyncMock(side_effect=RuntimeError("cosmos down"))
        cosmos.GENERATED_ARTIFACTS = "generated_artifacts"
        with patch.object(policy_routes, "get_policy_service", return_value=_fake_policy_service()), \
             patch.object(policy_routes, "cosmos_client", cosmos), \
             patch.object(policy_routes.version_service, "create_version", create_version):
            app = FastAPI()
            app.include_router(policy_routes.router, prefix="/api/v1")
            client = TestClient(app)
            resp = client.post("/api/v1/policy/generate", json=_mcsb_payload())
        assert resp.status_code == 200, resp.text
        create_version.assert_awaited_once()


class TestSlzRecording:
    def _slz_payload(self) -> dict:
        return {
            "framework_name": "Test Framework",
            "allowed_locations": ["swedencentral"],
            "mappings": [
                _valid_mapping({"sovereignty": {"sovereignty_level": "L2"}})
            ],
        }

    def test_generate_slz_records_version_server_side(self):
        create_version = AsyncMock(return_value=_VERSION)
        cosmos = MagicMock(database=None)
        svc = MagicMock()
        svc.generate_slz_initiatives.return_value = {
            "archetype_artifacts": {
                "archetype-a": {"initiative_json": {"properties": {}}}
            }
        }
        with patch.object(policy_routes, "get_policy_service", return_value=svc), \
             patch.object(policy_routes, "cosmos_client", cosmos), \
             patch.object(policy_routes.version_service, "create_version", create_version):
            app = FastAPI()
            app.include_router(policy_routes.router, prefix="/api/v1")
            client = TestClient(app)
            resp = client.post(
                "/api/v1/policy/generate/slz",
                json=self._slz_payload(),
                headers={"X-Session-ID": "sess-2"},
            )
        assert resp.status_code == 200, resp.text
        create_version.assert_awaited_once()
        kwargs = create_version.await_args.kwargs
        assert kwargs["metadata"]["source"] == "slz_initiative"
        assert kwargs["metadata"]["mappings_count"] == 1
