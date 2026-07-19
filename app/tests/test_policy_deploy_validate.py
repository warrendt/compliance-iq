"""Tests for the non-destructive initiative validation path.

`PolicyDeployService.validate_initiative` must NEVER write to the tenant: it only
runs structural checks plus read-only GETs of referenced policy definitions.
"""

import httpx
import pytest

from app.services import policy_deploy_service as mod
from app.services.policy_deploy_service import PolicyDeployService

_GUID_A = "aaaaaaaa-1111-2222-3333-444444444444"
_GUID_B = "bbbbbbbb-1111-2222-3333-444444444444"


def _pdef(guid: str, ref: str, groups=None) -> dict:
    entry = {
        "policyDefinitionId": f"/providers/Microsoft.Authorization/policyDefinitions/{guid}",
        "policyDefinitionReferenceId": ref,
        "parameters": {},
    }
    if groups:
        entry["groupNames"] = groups
    return entry


def _initiative(defs, groups=None) -> dict:
    props = {"displayName": "Test Initiative", "policyDefinitions": defs}
    if groups is not None:
        props["policyDefinitionGroups"] = groups
    return {"properties": props}


def _svc() -> PolicyDeployService:
    return PolicyDeployService("fake-token")


# ---------------------------------------------------------------------------
# Structural validation (no network — check_references=False)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_initiative_passes_structural_checks():
    body = _initiative(
        [_pdef(_GUID_A, "ref-a", ["grp1"]), _pdef(_GUID_B, "ref-b", ["grp1"])],
        groups=[{"name": "grp1"}],
    )
    result = await _svc().validate_initiative(
        scope="/subscriptions/sub", initiative_name="my-initiative",
        body=body, check_references=False,
    )
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["summary"]["policy_count"] == 2
    assert result["summary"]["unique_policy_count"] == 2
    assert result["summary"]["group_count"] == 1
    assert result["summary"]["references_checked"] == 0


@pytest.mark.asyncio
async def test_empty_policy_definitions_is_invalid():
    result = await _svc().validate_initiative(
        scope="/subscriptions/sub", initiative_name="x",
        body=_initiative([]), check_references=False,
    )
    assert result["valid"] is False
    assert any("at least one" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_duplicate_reference_id_is_invalid():
    body = _initiative([_pdef(_GUID_A, "dup"), _pdef(_GUID_B, "dup")])
    result = await _svc().validate_initiative(
        scope="/subscriptions/sub", initiative_name="x",
        body=body, check_references=False,
    )
    assert result["valid"] is False
    assert any("Duplicate policyDefinitionReferenceId" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_non_guid_policy_id_is_invalid():
    body = _initiative([_pdef("not-a-guid", "ref-a")])
    result = await _svc().validate_initiative(
        scope="/subscriptions/sub", initiative_name="x",
        body=body, check_references=False,
    )
    assert result["valid"] is False
    assert any("non-GUID" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_group_reference_must_exist():
    body = _initiative(
        [_pdef(_GUID_A, "ref-a", ["missing-group"])],
        groups=[{"name": "grp1"}],
    )
    result = await _svc().validate_initiative(
        scope="/subscriptions/sub", initiative_name="x",
        body=body, check_references=False,
    )
    assert result["valid"] is False
    assert any("undefined group 'missing-group'" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_invalid_initiative_name_is_invalid():
    body = _initiative([_pdef(_GUID_A, "ref-a")])
    result = await _svc().validate_initiative(
        scope="/subscriptions/sub", initiative_name="bad/name#",
        body=body, check_references=False,
    )
    assert result["valid"] is False
    assert any("characters ARM does not allow" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_shared_policy_deduped_in_unique_count():
    # Same GUID referenced twice (distinct reference ids) -> 2 defs, 1 unique id.
    body = _initiative([_pdef(_GUID_A, "ref-a"), _pdef(_GUID_A, "ref-b")])
    result = await _svc().validate_initiative(
        scope="/subscriptions/sub", initiative_name="x",
        body=body, check_references=False,
    )
    assert result["valid"] is True
    assert result["summary"]["policy_count"] == 2
    assert result["summary"]["unique_policy_count"] == 1


# ---------------------------------------------------------------------------
# Reference resolution (read-only GETs, mocked transport)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_arm(monkeypatch):
    """Patch httpx.AsyncClient so reference GETs hit a MockTransport.

    Records every request so tests can assert only GETs are issued (never a PUT).
    """
    real_client = httpx.AsyncClient
    seen: list[httpx.Request] = []

    def install(handler):
        def factory(*args, **kwargs):
            kwargs.pop("timeout", None)
            return real_client(transport=httpx.MockTransport(handler), **kwargs)

        monkeypatch.setattr(mod.httpx, "AsyncClient", factory)

    return install, seen


@pytest.mark.asyncio
async def test_reference_check_flags_missing_definition(mock_arm):
    install, seen = mock_arm

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if _GUID_A in str(request.url):
            return httpx.Response(200, json={"id": str(request.url)})
        return httpx.Response(404, json={"error": {"code": "PolicyDefinitionNotFound"}})

    install(handler)
    body = _initiative([_pdef(_GUID_A, "ref-a"), _pdef(_GUID_B, "ref-b")])
    result = await _svc().validate_initiative(
        scope="/subscriptions/sub", initiative_name="x",
        body=body, check_references=True,
    )

    assert result["valid"] is False
    assert result["summary"]["references_checked"] == 2
    assert result["summary"]["unresolved_references"] == 1
    assert any(_GUID_B in e for e in result["errors"])
    # Non-destructive: only read-only GETs were issued.
    assert seen and all(r.method == "GET" for r in seen)


@pytest.mark.asyncio
async def test_reference_check_all_resolved_is_valid(mock_arm):
    install, seen = mock_arm

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": str(request.url)})

    install(handler)
    body = _initiative([_pdef(_GUID_A, "ref-a"), _pdef(_GUID_B, "ref-b")])
    result = await _svc().validate_initiative(
        scope="/subscriptions/sub", initiative_name="x",
        body=body, check_references=True,
    )

    assert result["valid"] is True
    assert result["summary"]["references_checked"] == 2
    assert result["summary"]["unresolved_references"] == 0
    assert all(r.method == "GET" for r in seen)


@pytest.mark.asyncio
async def test_reference_check_transient_error_is_warning(mock_arm):
    install, seen = mock_arm

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(429, json={"error": {"code": "TooManyRequests"}})

    install(handler)
    body = _initiative([_pdef(_GUID_A, "ref-a")])
    result = await _svc().validate_initiative(
        scope="/subscriptions/sub", initiative_name="x",
        body=body, check_references=True,
    )

    # A 429 is not a definitive "missing" -> warning, not error.
    assert result["summary"]["unresolved_references"] == 0
    assert any("429" in w for w in result["warnings"])
    assert result["valid"] is True
