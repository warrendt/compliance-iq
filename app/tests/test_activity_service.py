"""
Unit tests for activity_service — the workspace activity recorder (mocked Cosmos).

Run from app/ with:
  AZURE_OPENAI_ENDPOINT=https://dummy.openai.azure.com/ ENABLE_AUTH=false \
  PYTHONPATH=backend python -m pytest tests/test_activity_service.py -q -p no:cacheprovider
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.auth.azure_ad_auth import User
from app.services import activity_service


def _mock_cosmos(get_document_return=None, query_return=None):
    """Build a mock cosmos_client with the container constants the service uses."""
    mock = MagicMock()
    mock.database = MagicMock()
    mock.USER_UPLOADS = "user-uploads"
    mock.MAPPING_RESULTS = "mapping-results"
    mock.GENERATED_ARTIFACTS = "generated-artifacts"
    mock.USER_PROFILES = "user-profiles"
    mock.ensure_container = AsyncMock()
    mock.upsert_document = AsyncMock(side_effect=lambda *a, **k: (a[1] if len(a) > 1 else k.get("document")))
    mock.get_document = AsyncMock(return_value=get_document_return)
    mock.query_documents = AsyncMock(return_value=query_return or [])
    return mock


_USER = User(oid="oid-1", email="dev@example.com", name="Dev User")


class TestRecordUpload:
    @pytest.mark.asyncio
    async def test_writes_upload_with_version_and_controls(self):
        cosmos = _mock_cosmos(query_return=[1, 2])  # prior versions → next = 3
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()) as audit:
            doc = await activity_service.record_upload(
                _USER,
                file_name="sama.csv",
                file_type="text/csv",
                category=activity_service.CATEGORY_CONTROLS,
                row_count=3,
                column_names=["id", "name"],
                controls=[{"control_id": "c1"}, {"control_id": "c2"}],
            )

        assert doc["userId"] == "dev@example.com"
        assert doc["category"] == "controls"
        assert doc["version"] == 3
        assert doc["controlCount"] == 2
        assert doc["controls"] == [{"control_id": "c1"}, {"control_id": "c2"}]
        # dedicated container write + audit + profile bump
        cosmos.upsert_document.assert_awaited()
        audit.assert_awaited_once()
        _, akw = audit.call_args
        assert akw["resource_type"] == activity_service.audit_service.RESOURCE_UPLOAD
        assert "summary" in akw["metadata"]

    @pytest.mark.asyncio
    async def test_default_version_is_one(self):
        cosmos = _mock_cosmos(query_return=[])
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()):
            doc = await activity_service.record_upload(
                _USER, file_name="new.pdf", file_type="application/pdf",
                category=activity_service.CATEGORY_DOCUMENT,
            )
        assert doc["version"] == 1
        assert doc["category"] == "document"

    @pytest.mark.asyncio
    async def test_controls_are_capped(self):
        cosmos = _mock_cosmos(query_return=[])
        big = [{"control_id": f"c{i}"} for i in range(5000)]
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()):
            doc = await activity_service.record_upload(
                _USER, file_name="big.csv", file_type="text/csv",
                category=activity_service.CATEGORY_CONTROLS, controls=big,
            )
        assert len(doc["controls"]) == 2000
        assert doc["controlCount"] == 5000

    @pytest.mark.asyncio
    async def test_does_not_raise_on_db_failure(self):
        cosmos = _mock_cosmos(query_return=[])
        cosmos.upsert_document = AsyncMock(side_effect=Exception("boom"))
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()):
            doc = await activity_service.record_upload(
                _USER, file_name="x.csv", file_type="text/csv",
            )
        assert doc["fileName"] == "x.csv"  # returns the doc even though write failed


class TestRecordMappings:
    @pytest.mark.asyncio
    async def test_writes_one_doc_per_mapping_and_bumps_count(self):
        cosmos = _mock_cosmos()
        mappings = [
            {"control_id": "c1", "control_name": "Access", "confidence_score": 0.9},
            {"control_id": "c2", "control_name": "Crypto", "confidence_score": 0.7},
        ]
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()) as audit:
            written = await activity_service.record_mappings(
                _USER, framework="SAMA", mappings=mappings,
            )
        assert written == 2
        # one upsert per mapping into mapping-results + a profile bump
        mapping_writes = [
            c for c in cosmos.upsert_document.await_args_list
            if c.args and c.args[0] == "mapping-results"
        ]
        assert len(mapping_writes) == 2
        body = mapping_writes[0].args[1]
        assert body["userId"] == "dev@example.com"
        assert body["framework"] == "SAMA"
        assert "date" in body  # composite PK field
        _, akw = audit.call_args
        assert akw["metadata"]["controlCount"] == 2
        assert akw["metadata"]["avgConfidence"] == pytest.approx(0.8, abs=0.001)

    @pytest.mark.asyncio
    async def test_empty_mappings_still_audits(self):
        cosmos = _mock_cosmos()
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()) as audit:
            written = await activity_service.record_mappings(
                _USER, framework="SAMA", mappings=[],
            )
        assert written == 0
        audit.assert_awaited_once()


class TestRecordExport:
    @pytest.mark.asyncio
    async def test_writes_artifact_and_defaults_partition_to_user(self):
        cosmos = _mock_cosmos()
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()) as audit:
            doc = await activity_service.record_export(
                _USER, framework="SAMA", artifact_type="initiative",
                control_count=12, file_name="sama.json",
            )
        assert doc["session_id"] == "dev@example.com"  # fallback partition
        assert doc["controlCount"] == 12
        write = [
            c for c in cosmos.upsert_document.await_args_list
            if c.args and c.args[0] == "generated-artifacts"
        ]
        assert write
        _, akw = audit.call_args
        assert akw["resource_type"] == activity_service.audit_service.RESOURCE_EXPORT

    @pytest.mark.asyncio
    async def test_uses_supplied_session_id(self):
        cosmos = _mock_cosmos()
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()):
            doc = await activity_service.record_export(
                _USER, framework="SAMA", session_id="sess-9",
            )
        assert doc["session_id"] == "sess-9"


class TestRecordActivity:
    @pytest.mark.asyncio
    async def test_audit_only(self):
        cosmos = _mock_cosmos()
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()) as audit:
            await activity_service.record_activity(
                _USER, action="mapping.edited", resource_type="edit",
                summary="Edited mappings",
            )
        audit.assert_awaited_once()
        _, akw = audit.call_args
        assert akw["action"] == "mapping.edited"
        assert akw["metadata"]["summary"] == "Edited mappings"


class TestProfileBump:
    @pytest.mark.asyncio
    async def test_creates_profile_when_missing(self):
        cosmos = _mock_cosmos(get_document_return=None)
        with patch.object(activity_service, "cosmos_client", cosmos):
            await activity_service._bump_profile(_USER, "uploadCount", 1)
        write = [
            c for c in cosmos.upsert_document.await_args_list
            if c.args and c.args[0] == "user-profiles"
        ]
        assert write
        body = write[0].args[1]
        assert body["uploadCount"] == 1
        assert body["userId"] == "dev@example.com"

    @pytest.mark.asyncio
    async def test_increments_existing_profile(self):
        existing = {"id": "dev@example.com", "userId": "dev@example.com", "mappingCount": 5}
        cosmos = _mock_cosmos(get_document_return=existing)
        with patch.object(activity_service, "cosmos_client", cosmos):
            await activity_service._bump_profile(_USER, "mappingCount", 3)
        write = [
            c for c in cosmos.upsert_document.await_args_list
            if c.args and c.args[0] == "user-profiles"
        ]
        assert write[0].args[1]["mappingCount"] == 8
