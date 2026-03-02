"""
Frontend authentication helper.

Resolution order:
  1. Container Apps Easy Auth headers (production)
  2. MSAL interactive browser flow (local development)
  3. Anonymous / no-auth when ENABLE_AUTH != "true"
"""

import os
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

def _get_easy_auth_user() -> Optional[AuthUser]:
    """Read identity from Easy Auth reverse-proxy headers.

    These headers are injected by Container Apps when authentication is
    configured on the frontend app and are NOT forgeable by the client.
    """
    # Streamlit doesn't expose inbound HTTP headers directly; however when
    # running behind Container Apps Easy Auth the /.auth/me endpoint returns
    # the user's claims.  We cache the result in session_state.
    if "easy_auth_user" in st.session_state:
        return st.session_state["easy_auth_user"]

    try:
        import httpx

        # /.auth/me is served by the Easy Auth sidecar on the same origin
        resp = httpx.get(
            f"{_frontend_origin()}/.auth/me",
            timeout=5,
            follow_redirects=False,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                claims = {c["typ"]: c["val"] for c in data[0].get("user_claims", [])}
                user = AuthUser(
                    name=claims.get("name", ""),
                    email=claims.get(
                        "preferred_username",
                        claims.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress", ""),
                    ),
                    oid=claims.get("http://schemas.microsoft.com/identity/claims/objectidentifier", ""),
                    access_token=data[0].get("access_token", ""),
                )
                st.session_state["easy_auth_user"] = user
                return user
    except Exception:
        pass
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

def _frontend_origin() -> str:
    """Best-guess origin of the running Streamlit app."""
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
