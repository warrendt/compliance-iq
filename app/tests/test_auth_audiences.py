"""Tests for multi-audience token acceptance in ``azure_ad_auth``.

The backend accepts a bearer token whose ``aud`` is either the app's own
audience *or* an ARM audience (``https://management.azure.com``). The latter
lets a token from ``az account get-access-token`` both authenticate the caller
and be reused for ARM deploy calls — which the ComplianceIQ Copilot skill and
the frontend proxy rely on.

Only the pure audience-resolution and audience-check behaviour is tested here;
JWKS/signature verification is not exercised (that needs live Entra keys).
"""

import pytest

from app.auth import azure_ad_auth as auth


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for var in ("AZURE_AD_AUDIENCE", "AZURE_AD_CLIENT_ID", "AZURE_AD_ACCEPTED_AUDIENCES"):
        monkeypatch.delenv(var, raising=False)
    yield


def test_accepted_audiences_empty_when_unconfigured():
    assert auth._get_accepted_audiences() == set()


def test_accepted_audiences_uses_client_id_fallback(monkeypatch):
    monkeypatch.setenv("AZURE_AD_CLIENT_ID", "app-guid")
    assert auth._get_accepted_audiences() == {"app-guid"}


def test_accepted_audiences_prefers_explicit_audience(monkeypatch):
    monkeypatch.setenv("AZURE_AD_CLIENT_ID", "app-guid")
    monkeypatch.setenv("AZURE_AD_AUDIENCE", "api://app-guid")
    assert auth._get_accepted_audiences() == {"api://app-guid"}


def test_accepted_audiences_merges_extra_arm(monkeypatch):
    monkeypatch.setenv("AZURE_AD_CLIENT_ID", "app-guid")
    monkeypatch.setenv(
        "AZURE_AD_ACCEPTED_AUDIENCES",
        "https://management.azure.com, https://management.azure.com/",
    )
    assert auth._get_accepted_audiences() == {
        "app-guid",
        "https://management.azure.com",
        "https://management.azure.com/",
    }


def test_accepted_audiences_ignores_blanks(monkeypatch):
    monkeypatch.setenv("AZURE_AD_ACCEPTED_AUDIENCES", " , ,https://management.azure.com, ")
    assert auth._get_accepted_audiences() == {"https://management.azure.com"}


@pytest.mark.asyncio
async def test_validate_token_accepts_arm_audience(monkeypatch):
    """A valid-signature token with an ARM aud is accepted when configured."""
    monkeypatch.setenv("AZURE_AD_CLIENT_ID", "app-guid")
    monkeypatch.setenv("AZURE_AD_ACCEPTED_AUDIENCES", "https://management.azure.com")

    async def _fake_jwks():
        return {"keys": [{"kid": "k1"}]}

    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda token: {"kid": "k1"})
    monkeypatch.setattr(auth, "_fetch_jwks", _fake_jwks)
    monkeypatch.setattr(auth, "_find_signing_key", lambda jwks, kid: {"kid": "k1"})
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *a, **k: {"aud": "https://management.azure.com", "oid": "o1"},
    )

    claims = await auth._validate_token("dummy")
    assert claims["oid"] == "o1"


@pytest.mark.asyncio
async def test_validate_token_rejects_wrong_audience(monkeypatch):
    monkeypatch.setenv("AZURE_AD_CLIENT_ID", "app-guid")
    monkeypatch.setenv("AZURE_AD_ACCEPTED_AUDIENCES", "https://management.azure.com")

    async def _fake_jwks():
        return {"keys": [{"kid": "k1"}]}

    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda token: {"kid": "k1"})
    monkeypatch.setattr(auth, "_fetch_jwks", _fake_jwks)
    monkeypatch.setattr(auth, "_find_signing_key", lambda jwks, kid: {"kid": "k1"})
    monkeypatch.setattr(auth.jwt, "decode", lambda *a, **k: {"aud": "someone-else", "oid": "o1"})

    with pytest.raises(auth.HTTPException) as exc:
        await auth._validate_token("dummy")
    assert exc.value.status_code == 401
