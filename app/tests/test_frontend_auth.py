"""
Unit tests for the Streamlit frontend authentication helpers.
"""

from types import SimpleNamespace

import utils.auth as auth
from utils.api_client import APIClient


def _streamlit_stub():
    return SimpleNamespace(
        session_state={},
        context=SimpleNamespace(headers={}),
        warning=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        button=lambda *args, **kwargs: False,
        rerun=lambda: None,
        stop=lambda: None,
    )


def test_get_request_headers_uses_streamlit_context_headers(monkeypatch):
    st_stub = _streamlit_stub()
    st_stub.context.headers = {
        "X-MS-Client-Principal-Name": "alice@example.com",
        "X-Forwarded-Proto": "https",
    }
    monkeypatch.setattr(auth, "st", st_stub)

    assert auth._get_request_headers() == {
        "x-ms-client-principal-name": "alice@example.com",
        "x-forwarded-proto": "https",
    }


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
    user = auth.get_current_user()

    assert user is not None
    assert user.email == "alice@example.com"
    assert user.oid == "oid-123"
    assert user.access_token == "arm-token"


def test_get_current_user_does_not_make_an_auth_me_request(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(auth, "st", st_stub)
    monkeypatch.setattr(
        auth,
        "_get_request_headers",
        lambda: {
            "x-ms-client-principal-name": "alice@example.com",
            "x-ms-client-principal-id": "oid-123",
        },
    )

    user = auth.get_current_user()

    assert user is not None
    assert user.email == "alice@example.com"
    assert user.access_token == ""


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


def test_get_login_url_targets_easy_auth_aad_endpoint():
    assert auth.get_login_url("/") == "/.auth/login/aad?post_login_redirect_uri=%2F"


def test_get_login_url_encodes_redirect_path():
    url = auth.get_login_url("/Policy_Explorer?x=1")
    assert url == (
        "/.auth/login/aad?post_login_redirect_uri=%2FPolicy_Explorer%3Fx%3D1"
    )


def test_get_logout_url_returns_to_landing_by_default():
    assert auth.get_logout_url() == "/.auth/logout?post_logout_redirect_uri=%2F"


def test_is_authenticated_reflects_current_user(monkeypatch):
    monkeypatch.setattr(auth, "get_current_user", lambda: None)
    assert auth.is_authenticated() is False

    user = auth.AuthUser(name="Alice", email="alice@example.com")
    monkeypatch.setattr(auth, "get_current_user", lambda: user)
    assert auth.is_authenticated() is True

def test_has_easy_auth_session_true_with_easy_auth_headers(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(auth, "st", st_stub)
    monkeypatch.setattr(
        auth,
        "_get_request_headers",
        lambda: {"x-ms-client-principal-name": "alice@example.com"},
    )
    assert auth.has_easy_auth_session() is True


def test_has_easy_auth_session_false_without_headers(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(auth, "st", st_stub)
    monkeypatch.setattr(auth, "_get_request_headers", lambda: {})
    assert auth.has_easy_auth_session() is False


def test_has_easy_auth_session_never_triggers_msal(monkeypatch):
    """Regression: the gate check must not fall through to the interactive
    MSAL flow, which would try to launch a browser server-side in production."""
    st_stub = _streamlit_stub()
    monkeypatch.setattr(auth, "st", st_stub)
    monkeypatch.setenv("ENABLE_AUTH", "true")
    monkeypatch.setattr(auth, "_get_request_headers", lambda: {})

    def _boom():
        raise AssertionError("MSAL interactive flow must not be invoked")

    monkeypatch.setattr(auth, "_get_msal_user", _boom)

    assert auth.has_easy_auth_session() is False
