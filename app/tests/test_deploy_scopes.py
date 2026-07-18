"""Tests for the /deploy/scopes route's fault-tolerant scope resolution.

The endpoint must not blow up with a 500 when one ARM source fails. Management
groups commonly return 403 for users without tenant-level read access; in that
case subscriptions should still be returned, with the failure surfaced as a
non-fatal warning. Only when *both* sources fail should the route error.
"""

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.api.routes import deploy
from app.auth.azure_ad_auth import User


def _user(token: str = "arm-token") -> User:
    return User(oid="oid-1", email="u@example.com", name="u", access_token=token)


def _http_error(status: int, body: str = "") -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://management.azure.com/subscriptions")
    response = httpx.Response(status, text=body, request=request)
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


def _patch_service(subs, mgs):
    """Patch PolicyDeployService with async list methods (value or exception)."""
    svc = AsyncMock()
    svc.list_subscriptions = AsyncMock(
        side_effect=subs if isinstance(subs, Exception) else None,
        return_value=None if isinstance(subs, Exception) else subs,
    )
    svc.list_management_groups = AsyncMock(
        side_effect=mgs if isinstance(mgs, Exception) else None,
        return_value=None if isinstance(mgs, Exception) else mgs,
    )
    return patch.object(deploy, "PolicyDeployService", return_value=svc)


@pytest.mark.asyncio
async def test_both_sources_succeed():
    subs = [{"subscriptionId": "sub-123", "displayName": "Prod"}]
    mgs = [{"name": "mg-root", "properties": {"displayName": "Tenant Root"}}]
    with _patch_service(subs, mgs):
        result = await deploy.list_scopes(_user())

    scopes = result["scopes"]
    assert result["warnings"] == []
    assert {s["type"] for s in scopes} == {"subscription", "management_group"}
    sub = next(s for s in scopes if s["type"] == "subscription")
    assert sub["scope"] == "/subscriptions/sub-123"
    assert sub["display"] == "Prod"


@pytest.mark.asyncio
async def test_management_groups_forbidden_still_returns_subscriptions():
    subs = [{"subscriptionId": "sub-123", "displayName": "Prod"}]
    with _patch_service(subs, _http_error(403, "Forbidden")):
        result = await deploy.list_scopes(_user())

    scopes = result["scopes"]
    # Subscription still present despite MG failure.
    assert [s["type"] for s in scopes] == ["subscription"]
    assert len(result["warnings"]) == 1
    warn = result["warnings"][0]
    assert warn.startswith("Management groups")
    assert "access denied" in warn


@pytest.mark.asyncio
async def test_subscriptions_forbidden_still_returns_management_groups():
    mgs = [{"name": "mg-root", "properties": {"displayName": "Tenant Root"}}]
    with _patch_service(_http_error(403), mgs):
        result = await deploy.list_scopes(_user())

    scopes = result["scopes"]
    assert [s["type"] for s in scopes] == ["management_group"]
    assert result["warnings"] and result["warnings"][0].startswith("Subscriptions")


@pytest.mark.asyncio
async def test_both_sources_fail_raises_502_with_detail():
    with _patch_service(_http_error(401), _http_error(403)):
        with pytest.raises(HTTPException) as excinfo:
            await deploy.list_scopes(_user())

    assert excinfo.value.status_code == 502
    assert "Subscriptions" in excinfo.value.detail
    assert "Management groups" in excinfo.value.detail


@pytest.mark.asyncio
async def test_non_auth_arm_error_includes_status_and_body():
    subs = [{"subscriptionId": "sub-1", "displayName": "S"}]
    with _patch_service(subs, _http_error(500, "boom")):
        result = await deploy.list_scopes(_user())
    warn = result["warnings"][0]
    assert "ARM HTTP 500" in warn
    assert "boom" in warn


@pytest.mark.asyncio
async def test_missing_access_token_raises_401():
    with pytest.raises(HTTPException) as excinfo:
        await deploy.list_scopes(_user(token=""))
    assert excinfo.value.status_code == 401
