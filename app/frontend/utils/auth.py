"""
Frontend authentication helper.

Resolution order:
  1. Container Apps Easy Auth headers (production)
  2. MSAL interactive browser flow (local development)
  3. Anonymous / no-auth when ENABLE_AUTH != "true"
"""

import os
from urllib.parse import urlsplit
from typing import Optional

import streamlit as st

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
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers

        headers = _get_websocket_headers() or {}
        return {str(key).lower(): str(value) for key, value in headers.items()}
    except Exception:
        return {}


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


def _get_auth_me_user(headers: dict[str, str]) -> Optional[AuthUser]:
    """Query /.auth/me using the caller's session cookie when available."""
    cookie = headers.get("cookie", "")
    session_token = headers.get("x-zumo-auth", "")
    if not cookie and not session_token:
        return None

    try:
        import httpx

        request_headers = {}
        if cookie:
            request_headers["Cookie"] = cookie
        if session_token:
            request_headers["X-ZUMO-AUTH"] = session_token

        resp = httpx.get(
            f"{_frontend_origin(headers)}/.auth/me",
            headers=request_headers,
            timeout=5,
            follow_redirects=False,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not data:
            return None

        claims = {c["typ"]: c["val"] for c in data[0].get("user_claims", [])}
        return _claims_to_user(claims, access_token=data[0].get("access_token", ""))
    except Exception:
        return None


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

    auth_me_user = _get_auth_me_user(headers)
    user = header_user or auth_me_user
    if user and auth_me_user:
        user.name = auth_me_user.name or user.name
        user.email = auth_me_user.email or user.email
        user.oid = auth_me_user.oid or user.oid
        user.access_token = auth_me_user.access_token or user.access_token

    if user:
        st.session_state["easy_auth_user"] = user
        return user

    return None


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

def _frontend_origin(headers: Optional[dict[str, str]] = None) -> str:
    """Best-guess origin of the running Streamlit app."""
    headers = headers or _get_request_headers()
    forwarded_host = headers.get("x-forwarded-host", headers.get("host", ""))
    if forwarded_host:
        scheme = headers.get("x-forwarded-proto", "https").split(",")[0].strip() or "https"
        host = forwarded_host.split(",")[0].strip()
        if host:
            return f"{scheme}://{host}"
    return os.getenv("FRONTEND_URL", "http://localhost:8501")


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


def get_backend_auth_headers() -> dict[str, str]:
    """Return auth headers that the backend can trust in the current runtime."""
    user = get_current_user()
    if not user:
        return {}

    if "easy_auth_user" in st.session_state:
        headers = {
            "X-MS-CLIENT-PRINCIPAL-NAME": user.email,
        }
        if user.oid:
            headers["X-MS-CLIENT-PRINCIPAL-ID"] = user.oid
        if user.access_token:
            headers["X-MS-TOKEN-AAD-ACCESS-TOKEN"] = user.access_token
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
    for key in ("easy_auth_user", "msal_user"):
        st.session_state.pop(key, None)
