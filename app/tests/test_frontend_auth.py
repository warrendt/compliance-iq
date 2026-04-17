"""
Unit tests for the Streamlit frontend authentication helpers.
"""

from types import SimpleNamespace

import utils.auth as auth
from utils.api_client import APIClient


def _streamlit_stub():
    return SimpleNamespace(
        session_state={},
        warning=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        button=lambda *args, **kwargs: False,
        rerun=lambda: None,
        stop=lambda: None,
    )


def test_get_current_user_uses_easy_auth_headers(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(auth, "st", st_stub)
    monkeypatch.setattr(
        auth,
        "_get_request_headers",
        lambda: {
            "x-ms-client-principal-name": "alice@example.com",
            "x-ms-client-principal-id": "oid-123",
            "x-ms-token-aad-access-token": "arm-token",
        },
    )
    monkeypatch.setattr(auth, "_get_auth_me_user", lambda headers: None)

    user = auth.get_current_user()

    assert user is not None
    assert user.email == "alice@example.com"
    assert user.oid == "oid-123"
    assert user.access_token == "arm-token"


def test_get_current_user_forwards_cookie_to_auth_me(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(auth, "st", st_stub)
    monkeypatch.setattr(
        auth,
        "_get_request_headers",
        lambda: {
            "cookie": "AppServiceAuthSession=session-cookie",
            "x-forwarded-host": "frontend.example.com",
            "x-forwarded-proto": "https",
        },
    )

    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return [{
                "access_token": "arm-token",
                "user_claims": [
                    {"typ": "name", "val": "Alice Example"},
                    {"typ": "preferred_username", "val": "alice@example.com"},
                    {
                        "typ": "http://schemas.microsoft.com/identity/claims/objectidentifier",
                        "val": "oid-123",
                    },
                ],
            }]

    def fake_get(url, headers, timeout, follow_redirects):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        captured["follow_redirects"] = follow_redirects
        return FakeResponse()

    monkeypatch.setattr("httpx.get", fake_get)

    user = auth.get_current_user()

    assert user is not None
    assert user.name == "Alice Example"
    assert user.email == "alice@example.com"
    assert user.access_token == "arm-token"
    assert captured["url"] == "https://frontend.example.com/.auth/me"
    assert captured["headers"] == {"Cookie": "AppServiceAuthSession=session-cookie"}
    assert captured["timeout"] == 5
    assert captured["follow_redirects"] is False


def test_get_request_path_prefers_forwarded_uri(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(auth, "st", st_stub)
    monkeypatch.setattr(
        auth,
        "_get_request_headers",
        lambda: {
            "x-forwarded-uri": "/PDF_Pipeline?foo=bar",
            "x-original-uri": "/ignored",
        },
    )

    assert auth.get_request_path() == "/PDF_Pipeline"


def test_get_backend_auth_headers_prefers_easy_auth_headers(monkeypatch):
    st_stub = _streamlit_stub()
    user = auth.AuthUser(
        name="Alice Example",
        email="alice@example.com",
        oid="oid-123",
        access_token="arm-token",
    )
    st_stub.session_state["easy_auth_user"] = user

    monkeypatch.setattr(auth, "st", st_stub)
    monkeypatch.setattr(auth, "get_current_user", lambda: user)

    headers = auth.get_backend_auth_headers()

    assert headers == {
        "X-MS-CLIENT-PRINCIPAL-NAME": "alice@example.com",
        "X-MS-CLIENT-PRINCIPAL-ID": "oid-123",
        "X-MS-TOKEN-AAD-ACCESS-TOKEN": "arm-token",
    }


def test_get_backend_auth_headers_falls_back_to_authorization(monkeypatch):
    st_stub = _streamlit_stub()
    user = auth.AuthUser(
        name="Dev User",
        email="dev@example.com",
        oid="oid-123",
        access_token="jwt-token",
    )
    st_stub.session_state["msal_user"] = user

    monkeypatch.setattr(auth, "st", st_stub)
    monkeypatch.setattr(auth, "get_current_user", lambda: user)

    headers = auth.get_backend_auth_headers()

    assert headers == {"Authorization": "Bearer jwt-token"}


def test_api_client_uses_backend_auth_headers(monkeypatch):
    monkeypatch.setattr(
        auth,
        "get_backend_auth_headers",
        lambda: {"X-MS-CLIENT-PRINCIPAL-NAME": "alice@example.com"},
    )

    client = APIClient(base_url="https://backend.internal")
    http_client = client._get_client()
    try:
        assert http_client.headers["X-MS-CLIENT-PRINCIPAL-NAME"] == "alice@example.com"
    finally:
        http_client.close()
