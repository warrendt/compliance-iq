"""Tests for Easy Auth ARM access-token refresh helpers.

Long-lived Streamlit sessions capture the Easy Auth access token once (headers
are fixed after the initial page load), so it must be refreshed via the token
store (/.auth/me + /.auth/refresh) before it expires. These tests cover the
pure helpers and the session-state-backed orchestration.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import utils.auth as auth


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")


def _future(minutes: int) -> str:
    return _iso(datetime.now(timezone.utc) + timedelta(minutes=minutes))


def _past(minutes: int) -> str:
    return _iso(datetime.now(timezone.utc) - timedelta(minutes=minutes))


def _stub():
    return SimpleNamespace(session_state={}, context=SimpleNamespace(headers={}))


# ---------------------------------------------------------------------------
# _derive_auth_origin
# ---------------------------------------------------------------------------

def test_derive_origin_prefers_forwarded_host():
    headers = {"x-forwarded-host": "app.example.io", "host": "internal:8501",
               "x-forwarded-proto": "https"}
    assert auth._derive_auth_origin(headers) == "https://app.example.io"


def test_derive_origin_falls_back_to_host_and_https():
    assert auth._derive_auth_origin({"host": "app.example.io"}) == "https://app.example.io"


def test_derive_origin_handles_comma_lists_and_empty():
    headers = {"x-forwarded-host": "a.io, b.io", "x-forwarded-proto": "https, http"}
    assert auth._derive_auth_origin(headers) == "https://a.io"
    assert auth._derive_auth_origin({}) == ""


# ---------------------------------------------------------------------------
# _parse_expires_on / _is_token_expired
# ---------------------------------------------------------------------------

def test_parse_expires_on_seven_digit_fraction_and_z():
    parsed = auth._parse_expires_on("2030-01-02T03:04:05.1234567Z")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.year == 2030 and parsed.hour == 3


def test_parse_expires_on_invalid_returns_none():
    assert auth._parse_expires_on("not-a-date") is None
    assert auth._parse_expires_on("") is None


def test_is_token_expired_variants():
    assert auth._is_token_expired(_past(10)) is True          # already expired
    assert auth._is_token_expired(_future(2)) is True         # within 5-min skew
    assert auth._is_token_expired(_future(30)) is False       # comfortably valid
    assert auth._is_token_expired("") is False                # unknown → assume valid


# ---------------------------------------------------------------------------
# _extract_token_from_auth_me
# ---------------------------------------------------------------------------

def test_extract_token_selects_aad_provider():
    payload = [
        {"provider_name": "other", "access_token": "x", "expires_on": "e1"},
        {"provider_name": "aad", "access_token": "arm-tok", "expires_on": "e2"},
    ]
    assert auth._extract_token_from_auth_me(payload) == ("arm-tok", "e2")


def test_extract_token_empty_or_bad_payload():
    assert auth._extract_token_from_auth_me([]) == ("", "")
    assert auth._extract_token_from_auth_me({"nope": 1}) == ("", "")


# ---------------------------------------------------------------------------
# _refresh_easy_auth_token (injected http_get)
# ---------------------------------------------------------------------------

def _recorder(responses):
    """Return (http_get, calls) where responses maps path-suffix -> (status, body)."""
    calls = []

    def http_get(url):
        calls.append(url)
        for suffix, resp in responses.items():
            if url.endswith(suffix):
                return resp
        return 404, None

    return http_get, calls


def test_refresh_returns_fresh_me_without_forcing_refresh():
    body = [{"provider_name": "aad", "access_token": "fresh", "expires_on": _future(30)}]
    http_get, calls = _recorder({"/.auth/me": (200, body)})
    token, exp = auth._refresh_easy_auth_token("https://app.io", "AppServiceAuthSession=abc",
                                               http_get=http_get)
    assert token == "fresh"
    assert auth._is_token_expired(exp) is False
    assert calls == ["https://app.io/.auth/me"]  # no /.auth/refresh needed


def test_refresh_forces_when_me_token_still_stale():
    stale = [{"provider_name": "aad", "access_token": "stale", "expires_on": _past(1)}]
    fresh = [{"provider_name": "aad", "access_token": "fresh", "expires_on": _future(45)}]
    seq = {"me": iter([(200, stale), (200, fresh)])}

    def http_get(url):
        if url.endswith("/.auth/me"):
            return next(seq["me"])
        return 200, None  # /.auth/refresh

    token, exp = auth._refresh_easy_auth_token("https://app.io", "cookie", http_get=http_get)
    assert token == "fresh"
    assert auth._is_token_expired(exp) is False


def test_refresh_no_origin_or_cookie_returns_empty():
    assert auth._refresh_easy_auth_token("", "cookie") == ("", "")
    assert auth._refresh_easy_auth_token("https://app.io", "") == ("", "")


# ---------------------------------------------------------------------------
# get_fresh_access_token / force_token_refresh (session-state)
# ---------------------------------------------------------------------------

def test_get_fresh_returns_cached_when_valid(monkeypatch):
    st = _stub()
    monkeypatch.setattr(auth, "st", st)
    user = auth.AuthUser(name="u", email="u@x.io", access_token="cached")
    st.session_state["easy_auth_user"] = user
    st.session_state["easy_auth_expires_on"] = _future(30)

    called = []
    monkeypatch.setattr(auth, "_refresh_easy_auth_token",
                        lambda *a, **k: called.append(1) or ("nope", ""))
    assert auth.get_fresh_access_token() == "cached"
    assert called == []  # refresh not attempted


def test_get_fresh_refreshes_when_expired(monkeypatch):
    st = _stub()
    monkeypatch.setattr(auth, "st", st)
    user = auth.AuthUser(name="u", email="u@x.io", access_token="stale")
    st.session_state["easy_auth_user"] = user
    st.session_state["easy_auth_expires_on"] = _past(5)
    st.session_state["easy_auth_origin"] = "https://app.io"
    st.session_state["easy_auth_cookie"] = "cookie"

    monkeypatch.setattr(auth, "_refresh_easy_auth_token",
                        lambda *a, **k: ("fresh", _future(40)))
    assert auth.get_fresh_access_token() == "fresh"
    assert st.session_state["easy_auth_user"].access_token == "fresh"
    assert auth._is_token_expired(st.session_state["easy_auth_expires_on"]) is False


def test_get_fresh_falls_back_to_cached_on_refresh_failure(monkeypatch):
    st = _stub()
    monkeypatch.setattr(auth, "st", st)
    user = auth.AuthUser(name="u", email="u@x.io", access_token="stale")
    st.session_state["easy_auth_user"] = user
    st.session_state["easy_auth_expires_on"] = _past(5)
    monkeypatch.setattr(auth, "_refresh_easy_auth_token", lambda *a, **k: ("", ""))
    assert auth.get_fresh_access_token() == "stale"


def test_get_fresh_none_when_no_user(monkeypatch):
    st = _stub()
    monkeypatch.setattr(auth, "st", st)
    assert auth.get_fresh_access_token() is None


def test_force_token_refresh_bypasses_valid_cache(monkeypatch):
    st = _stub()
    monkeypatch.setattr(auth, "st", st)
    user = auth.AuthUser(name="u", email="u@x.io", access_token="cached")
    st.session_state["easy_auth_user"] = user
    st.session_state["easy_auth_expires_on"] = _future(30)  # still valid
    st.session_state["easy_auth_origin"] = "https://app.io"
    st.session_state["easy_auth_cookie"] = "cookie"

    monkeypatch.setattr(auth, "_refresh_easy_auth_token",
                        lambda *a, **k: ("forced", _future(50)))
    assert auth.force_token_refresh() is True
    assert st.session_state["easy_auth_user"].access_token == "forced"


def test_backend_headers_forward_refreshed_token(monkeypatch):
    st = _stub()
    monkeypatch.setattr(auth, "st", st)
    user = auth.AuthUser(name="u", email="u@x.io", oid="oid-1", access_token="stale")
    st.session_state["easy_auth_user"] = user
    st.session_state["easy_auth_expires_on"] = _past(1)
    monkeypatch.setattr(auth, "get_current_user", lambda: user)
    monkeypatch.setattr(auth, "_refresh_easy_auth_token",
                        lambda *a, **k: ("fresh", _future(40)))
    headers = auth.get_backend_auth_headers()
    assert headers["X-MS-TOKEN-AAD-ACCESS-TOKEN"] == "fresh"
    assert headers["X-MS-CLIENT-PRINCIPAL-NAME"] == "u@x.io"
