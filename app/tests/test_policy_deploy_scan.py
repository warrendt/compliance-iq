"""Tests for the on-demand compliance-scan trigger.

``PolicyDeployService.trigger_compliance_scan`` maps to
``az policy state trigger-scan`` (Policy Insights ``triggerEvaluation``). It must:
  * hit the correct ARM endpoint/api-version for subscription and RG scopes,
  * skip unsupported scopes (management groups) WITHOUT any network call,
  * be best-effort — swallow ARM errors and never raise (a failed scan must not
    fail the deploy that triggered it).
"""

import httpx
import pytest

from app.services import policy_deploy_service as mod
from app.services.policy_deploy_service import (
    PolicyDeployService,
    _scan_supported_scope,
)

_SUB = "/subscriptions/00000000-0000-0000-0000-000000000000"
_RG = f"{_SUB}/resourceGroups/rg-demo"
_MG = "/providers/Microsoft.Management/managementGroups/mg-root"


def _svc() -> PolicyDeployService:
    return PolicyDeployService("fake-token")


# ---------------------------------------------------------------------------
# Pure scope classifier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "scope,expected",
    [
        (_SUB, _SUB),
        (_SUB + "/", _SUB),
        (_RG, _RG),
        # A resource-level scope collapses to its resource group.
        (_RG + "/providers/Microsoft.Storage/storageAccounts/sa1", _RG),
        # Case-insensitive segment matching, canonical output casing.
        ("/Subscriptions/abc/ResourceGroups/RgX", "/subscriptions/abc/resourceGroups/RgX"),
        # Unsupported / undecidable -> None.
        (_MG, None),
        (_MG.lower(), None),
        ("", None),
        ("   ", None),
        ("/providers/Microsoft.Authorization", None),
    ],
)
def test_scan_supported_scope(scope, expected):
    assert _scan_supported_scope(scope) == expected


# ---------------------------------------------------------------------------
# Skip path — no network for unsupported scopes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_management_group_scope_is_skipped_without_network(monkeypatch):
    def _boom(*a, **k):  # pragma: no cover - must never be called
        raise AssertionError("no ARM call should be made for a skipped scope")

    monkeypatch.setattr(mod.httpx, "AsyncClient", _boom)
    result = await _svc().trigger_compliance_scan(_MG)

    assert result["triggered"] is False
    assert result["skipped"] is True
    assert result["scope"] is None
    assert "management group" in result["reason"].lower()


# ---------------------------------------------------------------------------
# Success + error paths (mocked transport)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_arm(monkeypatch):
    real_client = httpx.AsyncClient
    seen: list[httpx.Request] = []

    def install(handler):
        def factory(*args, **kwargs):
            kwargs.pop("timeout", None)
            return real_client(transport=httpx.MockTransport(handler), **kwargs)

        monkeypatch.setattr(mod.httpx, "AsyncClient", factory)

    return install, seen


@pytest.mark.asyncio
async def test_subscription_scan_posts_to_policy_insights(mock_arm):
    install, seen = mock_arm

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202, headers={"Location": "https://arm/op/123"})

    install(handler)
    result = await _svc().trigger_compliance_scan(_SUB)

    assert result["triggered"] is True
    assert result["skipped"] is False
    assert result["scope"] == _SUB
    assert result["status_code"] == 202
    assert result["location"] == "https://arm/op/123"

    assert len(seen) == 1
    req = seen[0]
    assert req.method == "POST"
    assert "Microsoft.PolicyInsights/policyStates/latest/triggerEvaluation" in str(req.url)
    assert "api-version=2019-10-01" in str(req.url)
    assert str(req.url).startswith(
        "https://management.azure.com/subscriptions/"
    )


@pytest.mark.asyncio
async def test_resource_group_scope_targets_resource_group(mock_arm):
    install, seen = mock_arm
    install(lambda r: (seen.append(r), httpx.Response(202))[1])

    result = await _svc().trigger_compliance_scan(_RG)

    assert result["triggered"] is True
    assert result["scope"] == _RG
    assert "/resourceGroups/rg-demo/providers/Microsoft.PolicyInsights" in str(seen[0].url)


@pytest.mark.asyncio
async def test_arm_error_is_swallowed_best_effort(mock_arm):
    install, _ = mock_arm

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"code": "AuthorizationFailed"}})

    install(handler)
    result = await _svc().trigger_compliance_scan(_SUB)

    # Never raises: reports failure but leaves the deploy result intact.
    assert result["triggered"] is False
    assert result["skipped"] is False
    assert result["scope"] == _SUB
    assert "403" in result["reason"]


# ---------------------------------------------------------------------------
# Route wiring — scan only fires once an assignment exists
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, patch  # noqa: E402

from app.api.routes import deploy as deploy_route  # noqa: E402
from app.auth.azure_ad_auth import User  # noqa: E402


def _user() -> User:
    return User(oid="oid-1", email="u@example.com", name="u", access_token="arm-token")


def _req(**over):
    base = dict(
        scope=_SUB,
        initiative_name="my-initiative",
        initiative_body={"properties": {"policyDefinitions": []}},
    )
    base.update(over)
    return deploy_route.DeployRequest(**base)


def _mock_service():
    svc = AsyncMock()
    svc.deploy_initiative = AsyncMock(return_value={"id": f"{_SUB}/.../my-initiative"})
    svc.create_assignment = AsyncMock(return_value={"id": f"{_SUB}/.../assign"})
    svc.trigger_compliance_scan = AsyncMock(
        return_value={"triggered": True, "skipped": False, "scope": _SUB}
    )
    return svc


@pytest.mark.asyncio
async def test_route_triggers_scan_after_assignment():
    svc = _mock_service()
    with patch.object(deploy_route, "PolicyDeployService", return_value=svc):
        result = await deploy_route.deploy_initiative(
            _req(assign=True, trigger_scan=True), _user()
        )
    svc.trigger_compliance_scan.assert_awaited_once_with(_SUB)
    assert result["scan"]["triggered"] is True


@pytest.mark.asyncio
async def test_route_skips_scan_without_assignment():
    svc = _mock_service()
    with patch.object(deploy_route, "PolicyDeployService", return_value=svc):
        result = await deploy_route.deploy_initiative(
            _req(assign=False, trigger_scan=True), _user()
        )
    svc.trigger_compliance_scan.assert_not_awaited()
    assert result["scan"] is None


@pytest.mark.asyncio
async def test_route_respects_trigger_scan_opt_out():
    svc = _mock_service()
    with patch.object(deploy_route, "PolicyDeployService", return_value=svc):
        result = await deploy_route.deploy_initiative(
            _req(assign=True, trigger_scan=False), _user()
        )
    svc.trigger_compliance_scan.assert_not_awaited()
    assert result["scan"] is None


def test_deploy_request_defaults_trigger_scan_true():
    assert _req().trigger_scan is True

