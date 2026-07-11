"""
Tests for downloadable workspace artifacts:

- ``activity_service.record_export`` stores downloadable ``content`` with a
  discriminator and drops oversized payloads (never truncates into invalid data).
- ``GET /user/exports/{id}`` returns content, re-verifies ownership, and 404s
  on another user's artifact / missing doc.
- ``GET /user/uploads/{id}`` returns a stored control set scoped to controls.

Run from app/ with:
  AZURE_OPENAI_ENDPOINT=https://dummy.openai.azure.com/ ENABLE_AUTH=false \
  PYTHONPATH=backend python -m pytest tests/test_artifact_download.py -q -p no:cacheprovider
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, Request

from app.auth.azure_ad_auth import User
from app.services import activity_service

_USER = User(oid="oid-1", email="dev@example.com", name="Dev User")


def _mock_cosmos(get_document_return=None, query_return=None):
    mock = MagicMock()
    mock.database = MagicMock()
    mock.USER_UPLOADS = "user-uploads"
    mock.MAPPING_RESULTS = "mapping-results"
    mock.GENERATED_ARTIFACTS = "generated-artifacts"
    mock.USER_PROFILES = "user-profiles"
    mock.ensure_container = AsyncMock()
    mock.upsert_document = AsyncMock(
        side_effect=lambda *a, **k: (a[1] if len(a) > 1 else k.get("document"))
    )
    mock.get_document = AsyncMock(return_value=get_document_return)
    mock.query_documents = AsyncMock(return_value=query_return or [])
    return mock


# ---------------------------------------------------------------------------
# activity_service.record_export — content storage + cap
# ---------------------------------------------------------------------------

class TestRecordExportContent:
    @pytest.mark.asyncio
    async def test_stores_content_and_discriminator(self):
        cosmos = _mock_cosmos()
        captured = {}

        async def _capture(container, doc, partition_key=None):
            captured["doc"] = doc
            return doc

        cosmos.upsert_document = AsyncMock(side_effect=_capture)
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()):
            doc = await activity_service.record_export(
                _USER,
                framework="Test FW",
                artifact_type="mcsb_initiative",
                control_count=2,
                file_name="test_initiative.json",
                session_id="sess-1",
                content='{"files": [{"name": "a.json", "content": "{}"}]}',
            )

        assert doc["content"].startswith("{")
        assert doc["contentAvailable"] is True
        assert doc["docKind"] == activity_service._USER_EXPORT_DOC_KIND
        assert "contentSkippedReason" not in doc
        assert captured["doc"]["userId"] == "dev@example.com"

    @pytest.mark.asyncio
    async def test_drops_oversized_content_without_truncating(self):
        cosmos = _mock_cosmos()
        # Exceed the byte cap; must be dropped wholesale, not truncated.
        big = "x" * (activity_service._MAX_CONTENT_BYTES + 10)
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()):
            doc = await activity_service.record_export(
                _USER,
                framework="Test FW",
                artifact_type="mcsb_initiative",
                content=big,
            )

        assert doc["content"] == ""
        assert doc["contentAvailable"] is False
        assert doc["contentSkippedReason"] == "too_large"

    @pytest.mark.asyncio
    async def test_empty_content_is_not_available(self):
        cosmos = _mock_cosmos()
        with patch.object(activity_service, "cosmos_client", cosmos), \
             patch.object(activity_service.audit_service, "write_audit", new=AsyncMock()):
            doc = await activity_service.record_export(
                _USER, framework="Test FW", artifact_type="initiative"
            )
        assert doc["content"] == ""
        assert doc["contentAvailable"] is False


# ---------------------------------------------------------------------------
# GET /user/exports/{id}
# ---------------------------------------------------------------------------

class TestGetExportDetail:
    @pytest.mark.asyncio
    async def test_point_read_returns_content(self):
        from app.api.routes.user import get_export_detail

        doc = {
            "id": "exp-1",
            "userId": "dev@example.com",
            "fileName": "test_initiative.json",
            "framework": "Test FW",
            "artifactType": "mcsb_initiative",
            "content": '{"files": []}',
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        cosmos = _mock_cosmos(get_document_return=doc)
        req = MagicMock(spec=Request)
        with patch("app.api.routes.user.cosmos_client", cosmos):
            result = await get_export_detail(
                request=req, export_id="exp-1", session_id="sess-1", user=_USER
            )
        assert result["hasContent"] is True
        assert result["content"] == '{"files": []}'
        cosmos.get_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cross_partition_fallback(self):
        from app.api.routes.user import get_export_detail

        doc = {
            "id": "exp-2",
            "userId": "dev@example.com",
            "fileName": "f.json",
            "content": "data",
        }
        cosmos = _mock_cosmos(get_document_return=None, query_return=[doc])
        req = MagicMock(spec=Request)
        with patch("app.api.routes.user.cosmos_client", cosmos):
            result = await get_export_detail(
                request=req, export_id="exp-2", session_id=None, user=_USER
            )
        assert result["hasContent"] is True
        cosmos.query_documents.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_other_users_artifact(self):
        from app.api.routes.user import get_export_detail

        doc = {"id": "exp-3", "userId": "someone@else.com", "content": "secret"}
        cosmos = _mock_cosmos(get_document_return=doc)
        req = MagicMock(spec=Request)
        with patch("app.api.routes.user.cosmos_client", cosmos):
            with pytest.raises(HTTPException) as exc:
                await get_export_detail(
                    request=req, export_id="exp-3", session_id="sess-x", user=_USER
                )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_not_found(self):
        from app.api.routes.user import get_export_detail

        cosmos = _mock_cosmos(get_document_return=None, query_return=[])
        req = MagicMock(spec=Request)
        with patch("app.api.routes.user.cosmos_client", cosmos):
            with pytest.raises(HTTPException) as exc:
                await get_export_detail(
                    request=req, export_id="missing", session_id=None, user=_USER
                )
        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# GET /user/uploads/{id}
# ---------------------------------------------------------------------------

class TestGetUploadDetail:
    @pytest.mark.asyncio
    async def test_returns_control_set(self):
        from app.api.routes.user import get_upload_detail

        doc = {
            "id": "up-1",
            "userId": "dev@example.com",
            "category": "controls",
            "fileName": "controls.csv",
            "controls": [{"id": "c1", "name": "n1"}],
            "columnNames": ["id", "name"],
            "rowCount": 1,
            "controlCount": 1,
        }
        cosmos = _mock_cosmos(get_document_return=doc)
        req = MagicMock(spec=Request)
        with patch("app.api.routes.user.cosmos_client", cosmos):
            result = await get_upload_detail(request=req, upload_id="up-1", user=_USER)
        assert result["controls"] == [{"id": "c1", "name": "n1"}]
        assert result["columnNames"] == ["id", "name"]

    @pytest.mark.asyncio
    async def test_rejects_non_controls_upload(self):
        from app.api.routes.user import get_upload_detail

        doc = {"id": "up-2", "userId": "dev@example.com", "category": "document"}
        cosmos = _mock_cosmos(get_document_return=doc)
        req = MagicMock(spec=Request)
        with patch("app.api.routes.user.cosmos_client", cosmos):
            with pytest.raises(HTTPException) as exc:
                await get_upload_detail(request=req, upload_id="up-2", user=_USER)
        assert exc.value.status_code == 404
