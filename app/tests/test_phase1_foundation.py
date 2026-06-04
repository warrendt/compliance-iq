"""
Phase 1 unit tests — audit_service and version_service (mocked Cosmos).

Run from app/ with:
  AZURE_OPENAI_ENDPOINT=https://dummy.openai.azure.com/ ENABLE_AUTH=false \
  PYTHONPATH=backend python -m pytest tests/test_phase1_foundation.py -q -p no:cacheprovider
"""

import copy

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.auth.azure_ad_auth import User
from app.models.db_models import ComparisonDocument, PolicyVersionDocument
from app.services import audit_service, version_service


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestNewDocuments:
    def test_comparison_defaults(self):
        doc = ComparisonDocument(userId="dev@example.com")
        assert doc.status == "pending"
        assert doc.result == {}
        assert doc.counts == {}
        assert doc.direction == "internal_vs_external"

    def test_policy_version_required_number(self):
        doc = PolicyVersionDocument(userId="dev@example.com", version_number=1)
        assert doc.version_number == 1
        assert doc.parent_version is None
        assert doc.status == "active"
        assert doc.artifact_payload == {}
        # serialises cleanly for Cosmos
        body = doc.model_dump(mode="json")
        assert body["version_number"] == 1
        assert isinstance(body["timestamp"], str)

    def test_policy_version_number_is_required(self):
        with pytest.raises(Exception):
            PolicyVersionDocument(userId="dev@example.com")


# ---------------------------------------------------------------------------
# audit_service.write_audit
# ---------------------------------------------------------------------------

class TestWriteAudit:
    @pytest.mark.asyncio
    async def test_returns_none_when_db_unavailable(self):
        with patch("app.services.audit_service.cosmos_client") as mock_cosmos:
            mock_cosmos.database = None
            result = await audit_service.write_audit(
                User(oid="x", email="dev@example.com", name="Dev"),
                action="session.saved",
                resource_type="session",
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_writes_doc_with_expected_shape(self):
        captured = {}

        async def _insert(container, body):
            captured["container"] = container
            captured["body"] = body
            return body

        with patch("app.services.audit_service.cosmos_client") as mock_cosmos:
            mock_cosmos.database = MagicMock()
            mock_cosmos.AUDIT_LOGS = "audit-logs"
            mock_cosmos.ensure_container = AsyncMock()
            mock_cosmos.insert_document = AsyncMock(side_effect=_insert)

            result = await audit_service.write_audit(
                User(oid="x", email="dev@example.com", name="Dev"),
                action="session.saved",
                resource_type="session",
                resource_id="sess-1",
                metadata=None,  # must normalise to {}
            )

        # ensure_container called with the userId partition key + ttl
        mock_cosmos.ensure_container.assert_awaited_once()
        _, kwargs = mock_cosmos.ensure_container.call_args
        assert kwargs["partition_key_paths"] == ["/userId"]
        assert kwargs["default_ttl"] == audit_service._AUDIT_TTL_SECONDS

        body = captured["body"]
        assert captured["container"] == "audit-logs"
        assert body["userId"] == "dev@example.com"
        assert body["action"] == "session.saved"
        assert body["resourceType"] == "session"
        assert body["resourceId"] == "sess-1"
        assert body["metadata"] == {}  # None normalised
        # fields /user/history projects must be present
        for key in ("id", "action", "resourceType", "metadata", "timestamp"):
            assert key in body
        assert result is body

    @pytest.mark.asyncio
    async def test_swallows_insert_failure(self):
        with patch("app.services.audit_service.cosmos_client") as mock_cosmos:
            mock_cosmos.database = MagicMock()
            mock_cosmos.AUDIT_LOGS = "audit-logs"
            mock_cosmos.ensure_container = AsyncMock()
            mock_cosmos.insert_document = AsyncMock(side_effect=Exception("boom"))

            # Must not raise.
            result = await audit_service.write_audit(
                "dev@example.com", action="x", resource_type="y"
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_accepts_raw_string_user(self):
        with patch("app.services.audit_service.cosmos_client") as mock_cosmos:
            mock_cosmos.database = MagicMock()
            mock_cosmos.AUDIT_LOGS = "audit-logs"
            mock_cosmos.ensure_container = AsyncMock()
            mock_cosmos.insert_document = AsyncMock(side_effect=lambda c, b: b)

            result = await audit_service.write_audit(
                "raw@example.com", action="x", resource_type="comparison"
            )
        assert result["userId"] == "raw@example.com"


# ---------------------------------------------------------------------------
# version_service
# ---------------------------------------------------------------------------

class TestVersionService:
    @pytest.mark.asyncio
    async def test_create_first_version_is_one(self):
        with patch("app.services.version_service.cosmos_client") as mock_cosmos:
            mock_cosmos.database = MagicMock()
            mock_cosmos.POLICY_VERSIONS = "policy-versions"
            mock_cosmos.ensure_container = AsyncMock()
            mock_cosmos.query_documents = AsyncMock(return_value=[])  # no prior versions
            mock_cosmos.insert_document = AsyncMock(side_effect=lambda c, b: b)

            body = await version_service.create_version(
                "dev@example.com", artifact_payload={"a": 1}
            )

        assert body["version_number"] == 1
        assert body["userId"] == "dev@example.com"
        assert body["artifact_payload"] == {"a": 1}
        assert body["parent_version"] is None

    @pytest.mark.asyncio
    async def test_create_version_increments(self):
        with patch("app.services.version_service.cosmos_client") as mock_cosmos:
            mock_cosmos.database = MagicMock()
            mock_cosmos.POLICY_VERSIONS = "policy-versions"
            mock_cosmos.ensure_container = AsyncMock()
            mock_cosmos.query_documents = AsyncMock(return_value=[4])  # MAX = 4
            mock_cosmos.insert_document = AsyncMock(side_effect=lambda c, b: b)

            body = await version_service.create_version(
                "dev@example.com", artifact_payload={}
            )
        assert body["version_number"] == 5

    @pytest.mark.asyncio
    async def test_create_version_db_unavailable_raises_503(self):
        with patch("app.services.version_service.cosmos_client") as mock_cosmos:
            mock_cosmos.database = None
            with pytest.raises(HTTPException) as exc:
                await version_service.create_version("dev@example.com", artifact_payload={})
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_list_versions_orders_by_number(self):
        with patch("app.services.version_service.cosmos_client") as mock_cosmos:
            mock_cosmos.database = MagicMock()
            mock_cosmos.POLICY_VERSIONS = "policy-versions"
            mock_cosmos.ensure_container = AsyncMock()
            mock_cosmos.query_documents = AsyncMock(return_value=[{"version_number": 1}])

            result = await version_service.list_versions("dev@example.com")

        assert result == [{"version_number": 1}]
        args, kwargs = mock_cosmos.query_documents.call_args
        assert "ORDER BY c.version_number" in args[1] if len(args) > 1 else "ORDER BY c.version_number" in kwargs["query"]
        assert kwargs["partition_key"] == "dev@example.com"

    @pytest.mark.asyncio
    async def test_revert_creates_new_version_copying_target(self):
        target = {
            "id": "ver-1",
            "userId": "dev@example.com",
            "version_number": 2,
            "artifact_payload": {"initiative": {"name": "orig"}},
            "status": "active",
            "sourceComparisonId": "cmp-9",
            "metadata": {},
        }
        target_snapshot = copy.deepcopy(target)

        with patch("app.services.version_service.cosmos_client") as mock_cosmos:
            mock_cosmos.database = MagicMock()
            mock_cosmos.POLICY_VERSIONS = "policy-versions"
            mock_cosmos.ensure_container = AsyncMock()
            mock_cosmos.get_document = AsyncMock(return_value=target)
            mock_cosmos.query_documents = AsyncMock(return_value=[5])  # current MAX
            mock_cosmos.insert_document = AsyncMock(side_effect=lambda c, b: b)

            new_version = await version_service.revert_to_version("dev@example.com", "ver-1")

        # New, higher version number
        assert new_version["version_number"] == 6
        # Payload copied exactly from target
        assert new_version["artifact_payload"] == {"initiative": {"name": "orig"}}
        # Lineage recorded
        assert new_version["parent_version"] == 2
        assert new_version["metadata"]["reverted_from_id"] == "ver-1"
        assert new_version["metadata"]["reverted_from_version"] == 2
        assert new_version["sourceComparisonId"] == "cmp-9"
        # Target document untouched
        assert target == target_snapshot

    @pytest.mark.asyncio
    async def test_revert_missing_target_raises_404(self):
        with patch("app.services.version_service.cosmos_client") as mock_cosmos:
            mock_cosmos.database = MagicMock()
            mock_cosmos.POLICY_VERSIONS = "policy-versions"
            mock_cosmos.ensure_container = AsyncMock()
            mock_cosmos.get_document = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc:
                await version_service.revert_to_version("dev@example.com", "missing")
        assert exc.value.status_code == 404
