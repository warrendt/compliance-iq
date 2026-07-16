"""
Branded landing / sign-in page for unauthenticated visitors.

When Easy Auth is set to ``AllowAnonymous`` the app renders for anonymous users,
so the entrypoint gates on :func:`require_login`. Unauthenticated users see a
branded card with a "Sign in with Entra ID" button that navigates the top-level
window to the Easy Auth ``/.auth/login/aad`` endpoint; authenticated users fall
through to the normal app.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

from utils.auth import get_login_url, is_authenticated

# ── Branding ────────────────────────────────────────────────────────────────
PRODUCT_NAME = "ComplianceIQ"
TAGLINE = (
    "AI-Powered Compliance Framework Mapping to Microsoft Defender for Cloud, "
    "Microsoft 365 &amp; Microsoft Purview"
)
_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"


@lru_cache(maxsize=1)
def _logo_data_uri() -> str:
    """Return the logo as a base64 data URI, or an empty string if missing."""
    try:
        encoded = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except OSError:
        return ""


def _landing_css() -> str:
    """Full-screen navy → light-blue gradient with a centered glass card."""
    return """
    <style>
      /* Hide app chrome so no sidebar/header leaks behind the landing page */
      [data-testid="stSidebar"],
      [data-testid="collapsedControl"],
      [data-testid="stHeader"],
      [data-testid="stToolbar"],
      footer {
        display: none !important;
      }
      [data-testid="stAppViewContainer"],
      .main .block-container {
        padding: 0 !important;
        max-width: 100% !important;
      }
      .stApp {
        background: radial-gradient(circle at 50% 18%, #163459 0%, #0d2036 55%, #081524 100%);
      }
      .ciq-landing {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 2rem 1rem;
      }
      .ciq-card {
        width: 100%;
        max-width: 460px;
        background: linear-gradient(180deg, #ffffff 0%, #f4f9ff 100%);
        border: 1px solid rgba(207, 228, 250, 0.9);
        border-radius: 20px;
        box-shadow: 0 24px 60px rgba(5, 18, 34, 0.55);
        padding: 2.5rem 2.25rem 2.75rem;
        text-align: center;
      }
      .ciq-card img.ciq-logo {
        width: 132px;
        height: auto;
        border-radius: 22px;
        box-shadow: 0 10px 26px rgba(15, 84, 140, 0.28);
        margin-bottom: 1.25rem;
      }
      .ciq-title {
        font-size: 2rem;
        font-weight: 700;
        color: #10243E;
        letter-spacing: -0.01em;
        margin: 0 0 0.5rem;
      }
      .ciq-tagline {
        font-size: 0.98rem;
        line-height: 1.5;
        color: #424242;
        margin: 0 auto 1.75rem;
        max-width: 22rem;
      }
      a.ciq-signin {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.55rem;
        width: 100%;
        box-sizing: border-box;
        padding: 0.85rem 1.25rem;
        background: linear-gradient(180deg, #0F6CBD 0%, #0E4775 100%);
        color: #ffffff !important;
        font-size: 1.02rem;
        font-weight: 600;
        text-decoration: none !important;
        border-radius: 10px;
        box-shadow: 0 8px 20px rgba(15, 108, 189, 0.35);
        transition: filter 0.15s ease, transform 0.05s ease;
      }
      a.ciq-signin:hover { filter: brightness(1.07); }
      a.ciq-signin:active { transform: translateY(1px); }
      .ciq-footnote {
        margin-top: 1.5rem;
        font-size: 0.8rem;
        color: #616161;
      }
    </style>
    """


def render_landing_page() -> None:
    """Render the branded sign-in landing page."""
    login_url = get_login_url("/")
    logo_uri = _logo_data_uri()
    logo_html = (
        f'<img class="ciq-logo" src="{logo_uri}" alt="{PRODUCT_NAME} logo" />'
        if logo_uri
        else ""
    )

    st.markdown(_landing_css(), unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="ciq-landing">
          <div class="ciq-card">
            {logo_html}
            <div class="ciq-title">{PRODUCT_NAME}</div>
            <div class="ciq-tagline">{TAGLINE}</div>
            <a class="ciq-signin" href="{login_url}" target="_top" rel="noopener">
              🔐 Sign in with Entra ID
            </a>
            <div class="ciq-footnote">Secure sign-in via Microsoft Entra ID</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def require_login() -> None:
    """Gate the app: show the landing page and stop when unauthenticated."""
    if is_authenticated():
        return
    render_landing_page()
    st.stop()
