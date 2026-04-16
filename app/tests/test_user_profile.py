"""
Unit tests for user profile routes, models, and auth helpers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.models.db_models import UserProfileDocument, AuditLogDocument
from app.auth.azure_ad_auth import User, get_current_user, get_optional_user


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestUserProfileDocument:
    """Tests for the UserProfileDocument Pydantic model."""

    def test_default_values(self):
        doc = UserProfileDocument(userId="user@example.com")
        assert doc.userId == "user@example.com"
        assert doc.displayName == ""
        assert doc.email == ""
        assert doc.preferredPlatform == "azure_defender"
        assert doc.uploadCount == 0
        assert doc.mappingCount == 0
        assert doc.exportCount == 0
        assert doc.lastActive is None

    def test_full_creation(self):
        now = datetime.now(timezone.utc)
        doc = UserProfileDocument(
            userId="jane@example.com",
            displayName="Jane Smith",
            email="jane@example.com",
            preferredPlatform="microsoft_365",
            uploadCount=3,
            mappingCount=10,
            exportCount=2,
            lastActive=now,
        )
        assert doc.displayName == "Jane Smith"
        assert doc.preferredPlatform == "microsoft_365"
        assert doc.uploadCount == 3
        assert doc.lastActive == now

    def test_id_auto_generated(self):
        doc1 = UserProfileDocument(userId="a@b.com")
        doc2 = UserProfileDocument(userId="c@d.com")
        assert doc1.id != doc2.id

    def test_timestamp_auto_set(self):
        doc = UserProfileDocument(userId="a@b.com")
        assert doc.timestamp is not None


class TestUser:
    """Tests for the User principal model."""

    def test_user_creation(self):
        u = User(oid="abc-123", email="user@example.com", name="Test User")
        assert u.oid == "abc-123"
        assert u.email == "user@example.com"
        assert u.name == "Test User"
        assert u.roles == []
        assert u.access_token is None

    def test_user_with_roles(self):
        u = User(oid="x", email="a@b.com", name="A", roles=["Admin", "Viewer"])
        assert "Admin" in u.roles

    def test_user_str_repr(self):
        u = User(oid="x", email="a@b.com", name="A")
        s = str(u)
        assert "a@b.com" in s


# ---------------------------------------------------------------------------
# get_optional_user — no duplicate function test
# ---------------------------------------------------------------------------

def test_get_optional_user_is_single_function():
    """Ensure get_optional_user is a single coroutine function (no duplicate)."""
    import inspect
    import app.auth.azure_ad_auth as auth_module

    # Verify there is exactly one get_optional_user attribute
    assert hasattr(auth_module, "get_optional_user")
    assert inspect.iscoroutinefunction(auth_module.get_optional_user)


# ---------------------------------------------------------------------------
# User profile route tests (mocked DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_profile_creates_if_missing():
    """get_profile should create a profile document when none exists."""
    mock_user = User(oid="abc", email="dev@example.com", name="Dev User")

    with patch("app.api.routes.user.cosmos_client") as mock_cosmos, \
         patch("app.api.routes.user.get_current_user", return_value=mock_user):

        mock_cosmos.database = MagicMock()  # truthy → DB available
        mock_cosmos.ensure_container = AsyncMock()
        mock_cosmos.get_document = AsyncMock(return_value=None)
        mock_cosmos.upsert_document = AsyncMock(return_value={
            "id": "dev@example.com",
            "userId": "dev@example.com",
            "displayName": "Dev User",
            "email": "dev@example.com",
            "preferredPlatform": "azure_defender",
            "uploadCount": 0,
            "mappingCount": 0,
            "exportCount": 0,
            "lastActive": datetime.now(timezone.utc).isoformat(),
        })

        from app.api.routes.user import _get_or_create_profile
        doc = await _get_or_create_profile(mock_user)

        assert doc["userId"] == "dev@example.com"
        mock_cosmos.upsert_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_profile_returns_existing():
    """get_profile should return an existing profile without upserting."""
    mock_user = User(oid="abc", email="dev@example.com", name="Dev User")
    existing_doc = {
        "id": "dev@example.com",
        "userId": "dev@example.com",
        "displayName": "Existing Name",
        "email": "dev@example.com",
        "preferredPlatform": "microsoft_365",
        "uploadCount": 5,
        "mappingCount": 12,
        "exportCount": 3,
        "lastActive": "2026-01-01T00:00:00+00:00",
    }

    with patch("app.api.routes.user.cosmos_client") as mock_cosmos:
        mock_cosmos.database = MagicMock()
        mock_cosmos.ensure_container = AsyncMock()
        mock_cosmos.get_document = AsyncMock(return_value=existing_doc)

        from app.api.routes.user import _get_or_create_profile
        doc = await _get_or_create_profile(mock_user)

        assert doc["displayName"] == "Existing Name"
        assert doc["uploadCount"] == 5
        mock_cosmos.upsert_document = AsyncMock()
        mock_cosmos.upsert_document.assert_not_called()


@pytest.mark.asyncio
async def test_get_profile_db_unavailable():
    """get_profile should raise 503 when Cosmos DB is not configured."""
    from fastapi import HTTPException
    from unittest.mock import MagicMock

    mock_user = User(oid="abc", email="dev@example.com", name="Dev User")

    with patch("app.api.routes.user.cosmos_client") as mock_cosmos:
        mock_cosmos.database = None  # DB not configured

        from app.api.routes.user import _get_or_create_profile
        with pytest.raises(HTTPException) as exc_info:
            await _get_or_create_profile(mock_user)

        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_uploads_db_unavailable():
    """get_uploads should raise 503 when DB is unavailable."""
    from fastapi import HTTPException, Request

    mock_user = User(oid="abc", email="dev@example.com", name="Dev User")
    mock_request = MagicMock(spec=Request)

    with patch("app.api.routes.user.cosmos_client") as mock_cosmos:
        mock_cosmos.database = None

        from app.api.routes.user import get_uploads
        with pytest.raises(HTTPException) as exc_info:
            await get_uploads(request=mock_request, limit=10, user=mock_user)

        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_history_returns_empty_on_query_failure():
    """get_history should return an empty list when query fails."""
    from fastapi import Request

    mock_user = User(oid="abc", email="dev@example.com", name="Dev User")
    mock_request = MagicMock(spec=Request)

    with patch("app.api.routes.user.cosmos_client") as mock_cosmos:
        mock_cosmos.database = MagicMock()
        mock_cosmos.ensure_container = AsyncMock()
        mock_cosmos.query_documents = AsyncMock(side_effect=Exception("DB error"))

        from app.api.routes.user import get_history
        result = await get_history(request=mock_request, limit=10, event_type=None, user=mock_user)

        assert result == []
