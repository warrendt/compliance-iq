"""
Frontend authentication helper.

Resolution order:
  1. Container Apps Easy Auth headers (production)
  2. MSAL interactive browser flow (local development)
  3. Anonymous / no-auth when ENABLE_AUTH != "true"
"""

from typing import Optional
import os
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlsplit

import streamlit as st

# Container Apps Easy Auth built-in endpoints (served under the /.auth prefix).
_EASY_AUTH_LOGIN_PATH = "/.auth/login/aad"
_EASY_AUTH_LOGOUT_PATH = "/.auth/logout"

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class AuthUser:
    """Lightweight user model for the Streamlit frontend."""

    def __init__(self, name: str, email: str, oid: str = "", access_token: str = ""):
        self.name = name
        self.email = email
        self.oid = oid
        self.access_token = access_token

    @property
    def display_name(self) -> str:
        return self.name or self.email.split("@")[0] if self.email else "User"


# ---------------------------------------------------------------------------
# Easy Auth (Container Apps built-in authentication)
# ---------------------------------------------------------------------------

def _get_request_headers() -> dict[str, str]:
    """Return browser request headers visible to the current Streamlit session."""
    headers = st.context.headers
    return {str(key).lower(): str(value) for key, value in headers.items()}


def get_request_path() -> str:
    """Return the current browser request path when available."""
    headers = _get_request_headers()
    forwarded_uri = headers.get("x-forwarded-uri", "")
    if forwarded_uri:
        return urlsplit(forwarded_uri).path or "/"

    forwarded_path = headers.get("x-original-uri", "")
    if forwarded_path:
        return urlsplit(forwarded_path).path or "/"

    return "/"


def _claims_to_user(claims: dict[str, str], access_token: str = "") -> AuthUser:
    """Convert Easy Auth claims into the frontend auth model."""
    email = claims.get(
        "preferred_username",
        claims.get(
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
            "",
        ),
    )
    name = claims.get(
        "name",
        claims.get(
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
            "",
        ),
    )
    oid = claims.get(
        "http://schemas.microsoft.com/identity/claims/objectidentifier",
        claims.get("oid", ""),
    )
    return AuthUser(name=name, email=email, oid=oid, access_token=access_token)


def _get_easy_auth_user() -> Optional[AuthUser]:
    """Resolve the current user from Container Apps Easy Auth."""
    if "easy_auth_user" in st.session_state:
        return st.session_state["easy_auth_user"]

    headers = _get_request_headers()
    principal_name = headers.get("x-ms-client-principal-name", "")
    principal_id = headers.get("x-ms-client-principal-id", "")
    access_token = headers.get("x-ms-token-aad-access-token", "")

    header_user = None
    if principal_name:
        header_user = AuthUser(
            name=principal_name.split("@")[0] if "@" in principal_name else principal_name,
            email=principal_name,
            oid=principal_id,
            access_token=access_token,
        )

    if header_user:
        st.session_state["easy_auth_user"] = header_user
        # Capture the material needed to refresh the ARM access token later.
        # Easy Auth injects these on the initial page request; Streamlit reruns
        # over a websocket do not carry fresh headers, so the access token would
        # otherwise go stale after ~1 hour. We persist the token-store cookie and
        # the app origin so we can call /.auth/refresh + /.auth/me on demand.
        st.session_state["easy_auth_expires_on"] = headers.get(
            "x-ms-token-aad-expires-on", ""
        )
        st.session_state["easy_auth_cookie"] = headers.get("cookie", "")
        st.session_state["easy_auth_origin"] = _derive_auth_origin(headers)
    return header_user


# ---------------------------------------------------------------------------
# ARM access-token refresh (Container Apps token store)
# ---------------------------------------------------------------------------
# With the token store enabled, Container Apps auto-refreshes provider tokens.
# Calling GET /.auth/me returns the current (refreshed) access token; GET
# /.auth/refresh forces a refresh from the stored refresh token. Both require
# the user's auth session cookie, which we forward from the captured headers.

_TOKEN_REFRESH_SKEW_SECONDS = 300  # refresh when <5 min of validity remains


def _derive_auth_origin(headers: dict[str, str]) -> str:
    """Return the external ``https://host`` origin for the /.auth endpoints."""
    host = headers.get("x-forwarded-host", "") or headers.get("host", "")
    if not host:
        return ""
    proto = headers.get("x-forwarded-proto", "") or "https"
    # x-forwarded-* may be comma-separated lists; take the first entry.
    host = host.split(",")[0].strip()
    proto = proto.split(",")[0].strip() or "https"
    return f"{proto}://{host}"


def _parse_expires_on(value: str) -> Optional[datetime]:
    """Parse an Easy Auth ``expires_on`` timestamp into an aware UTC datetime."""
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    # Trim over-long fractional seconds (Easy Auth emits 7 digits) to 6.
    match = re.match(r"^(.*\.\d{6})\d*(\+\d{2}:\d{2})$", raw)
    if match:
        raw = match.group(1) + match.group(2)
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_token_expired(
    expires_on: str, now: Optional[datetime] = None,
    skew: int = _TOKEN_REFRESH_SKEW_SECONDS,
) -> bool:
    """Return True when the token is expired or within ``skew`` of expiring.

    Unknown/unparseable expiry is treated as *not* expired to avoid refresh
    storms; an explicit reload can still force a refresh.
    """
    expiry = _parse_expires_on(expires_on)
    if expiry is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now >= (expiry - timedelta(seconds=skew))


def _extract_token_from_auth_me(payload: object) -> tuple[str, str]:
    """Pull ``(access_token, expires_on)`` from a /.auth/me JSON payload."""
    if not isinstance(payload, list) or not payload:
        return "", ""
    aad = next(
        (p for p in payload if isinstance(p, dict)
         and p.get("provider_name") == "aad"),
        payload[0] if isinstance(payload[0], dict) else {},
    )
    return str(aad.get("access_token", "") or ""), str(aad.get("expires_on", "") or "")


def _refresh_easy_auth_token(origin: str, cookie: str, http_get=None) -> tuple[str, str]:
    """Refresh and return ``(access_token, expires_on)`` from the token store.

    Calls GET /.auth/me (which returns the auto-refreshed token); if the token
    still looks expired, forces GET /.auth/refresh and re-reads /.auth/me.
    Returns empty strings on any failure so callers can fall back to the cached
    token. ``http_get`` is injectable for testing.
    """
    if not origin or not cookie:
        return "", ""

    if http_get is None:
        import httpx

        def http_get(url: str) -> tuple[int, object]:  # noqa: ANN001
            resp = httpx.get(url, headers={"Cookie": cookie}, timeout=10.0,
                             follow_redirects=False)
            body: object
            try:
                body = resp.json()
            except Exception:  # noqa: BLE001
                body = None
            return resp.status_code, body

    def _read_me() -> tuple[str, str]:
        try:
            status, body = http_get(f"{origin}/.auth/me")
        except Exception:  # noqa: BLE001
            return "", ""
        if status != 200:
            return "", ""
        return _extract_token_from_auth_me(body)

    token, expires_on = _read_me()
    if token and not _is_token_expired(expires_on):
        return token, expires_on

    # Force a refresh from the stored refresh token, then re-read.
    try:
        http_get(f"{origin}/.auth/refresh")
    except Exception:  # noqa: BLE001
        pass
    refreshed_token, refreshed_expiry = _read_me()
    if refreshed_token:
        return refreshed_token, refreshed_expiry
    return token, expires_on


def get_fresh_access_token(force: bool = False) -> Optional[str]:
    """Return a valid ARM access token, refreshing via the token store if stale.

    Only acts in Easy Auth (production) mode. Falls back to the cached token on
    any refresh failure so behaviour never regresses. Set ``force=True`` to
    bypass the expiry check (used by the manual "Reload scopes" action).
    """
    user = st.session_state.get("easy_auth_user")
    if user is None:
        return None

    expires_on = st.session_state.get("easy_auth_expires_on", "")
    if not force and user.access_token and not _is_token_expired(expires_on):
        return user.access_token

    origin = st.session_state.get("easy_auth_origin", "")
    cookie = st.session_state.get("easy_auth_cookie", "")
    token, new_expiry = _refresh_easy_auth_token(origin, cookie)
    if token:
        user.access_token = token
        st.session_state["easy_auth_user"] = user
        st.session_state["easy_auth_expires_on"] = new_expiry
        return token

    return user.access_token or None


def force_token_refresh() -> bool:
    """Force an ARM token refresh. Returns True when a token is available."""
    return bool(get_fresh_access_token(force=True))


# ---------------------------------------------------------------------------
# MSAL interactive flow (local dev)
# ---------------------------------------------------------------------------

def _get_msal_user() -> Optional[AuthUser]:
    """Acquire a token interactively via MSAL (localhost redirect)."""
    if "msal_user" in st.session_state:
        return st.session_state["msal_user"]

    client_id = os.getenv("AZURE_AD_CLIENT_ID", "")
    tenant_id = os.getenv("AZURE_AD_TENANT_ID", "common")
    if not client_id:
        return None

    try:
        import msal  # optional dependency

        authority = f"https://login.microsoftonline.com/{tenant_id}"
        scopes = [
            "openid",
            "profile",
            "email",
            "https://management.azure.com/user_impersonation",
        ]

        app = msal.PublicClientApplication(client_id, authority=authority)

        # Try silent first (cached token)
        accounts = app.get_accounts()
        result = None
        if accounts:
            result = app.acquire_token_silent(scopes, account=accounts[0])

        if not result or "access_token" not in result:
            result = app.acquire_token_interactive(scopes=scopes, prompt="select_account")

        if "access_token" in result:
            id_claims = result.get("id_token_claims", {})
            user = AuthUser(
                name=id_claims.get("name", ""),
                email=id_claims.get("preferred_username", ""),
                oid=id_claims.get("oid", ""),
                access_token=result["access_token"],
            )
            st.session_state["msal_user"] = user
            return user
    except ImportError:
        pass  # msal not installed — skip
    except Exception:
        pass  # interactive flow cancelled or failed
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_current_user() -> Optional[AuthUser]:
    """Return the current user or None if unauthenticated.

    1. Easy Auth headers (production)
    2. MSAL interactive (local with ENABLE_AUTH=true + AZURE_AD_CLIENT_ID)
    3. None
    """
    user = _get_easy_auth_user()
    if user:
        return user

    auth_enabled = os.getenv("ENABLE_AUTH", "false").lower() == "true"
    if auth_enabled:
        return _get_msal_user()

    return None


def get_access_token() -> Optional[str]:
    """Return the AAD access token for the logged-in user, or None."""
    user = get_current_user()
    return user.access_token if user else None


def is_authenticated() -> bool:
    """Return True when a user is resolved from Easy Auth / MSAL."""
    return get_current_user() is not None


def has_easy_auth_session() -> bool:
    """Return True when Container Apps Easy Auth headers identify the user.

    Header-only check: unlike :func:`get_current_user`, it never falls through to
    the interactive MSAL flow, so it is safe to call on every request (e.g. the
    landing-page gate) without risking a server-side browser launch or a block.
    """
    return _get_easy_auth_user() is not None


def get_login_url(post_login_redirect_uri: str = "/") -> str:
    """Return the Easy Auth sign-in URL for Microsoft Entra ID.

    Sends the browser to the built-in ``/.auth/login/aad`` endpoint, which starts
    the Entra ID authorization-code flow and returns the user to
    ``post_login_redirect_uri`` (same domain) once signed in.
    """
    redirect = quote(post_login_redirect_uri or "/", safe="")
    return f"{_EASY_AUTH_LOGIN_PATH}?post_login_redirect_uri={redirect}"


def get_logout_url(post_logout_redirect_uri: str = "/") -> str:
    """Return the Easy Auth sign-out URL.

    Hitting ``/.auth/logout`` clears the session cookie and token store, then
    redirects to ``post_logout_redirect_uri`` (same domain) — ``/`` lands the user
    back on the branded landing page.
    """
    redirect = quote(post_logout_redirect_uri or "/", safe="")
    return f"{_EASY_AUTH_LOGOUT_PATH}?post_logout_redirect_uri={redirect}"


def get_backend_auth_headers() -> dict[str, str]:
    """Return auth headers that the backend can trust in the current runtime."""
    user = get_current_user()
    if not user:
        return {}

    if "easy_auth_user" in st.session_state:
        # Resolve a fresh (auto-refreshed) ARM token so long-lived sessions do
        # not forward an expired token that ARM would reject with 401.
        access_token = get_fresh_access_token() or user.access_token
        headers = {
            "X-MS-CLIENT-PRINCIPAL-NAME": user.email,
        }
        if user.oid:
            headers["X-MS-CLIENT-PRINCIPAL-ID"] = user.oid
        if access_token:
            headers["X-MS-TOKEN-AAD-ACCESS-TOKEN"] = access_token
        return headers

    if user.access_token:
        return {"Authorization": f"Bearer {user.access_token}"}

    return {}


def require_auth() -> AuthUser:
    """Return the current user or stop the page with a login prompt."""
    user = get_current_user()
    if user:
        return user

    st.warning("🔒 Please sign in to access this feature.")
    auth_enabled = os.getenv("ENABLE_AUTH", "false").lower() == "true"
    if auth_enabled:
        if st.button("🔑 Sign in with Microsoft"):
            user = _get_msal_user()
            if user:
                st.rerun()
            else:
                st.error("Sign-in failed or was cancelled.")
    else:
        st.info("Authentication is not enabled. Set `ENABLE_AUTH=true` and configure `AZURE_AD_CLIENT_ID`.")
    st.stop()


def logout():
    """Clear cached auth state."""
    for key in ("easy_auth_user", "msal_user", "easy_auth_expires_on",
                "easy_auth_cookie", "easy_auth_origin"):
        st.session_state.pop(key, None)
