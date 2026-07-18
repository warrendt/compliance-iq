"""
Frontend authentication helper.

Resolution order:
  1. Container Apps Easy Auth headers (production)
  2. MSAL interactive browser flow (local development)
  3. Anonymous / no-auth when ENABLE_AUTH != "true"
"""

from typing import Optional
import os
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
    return header_user


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
