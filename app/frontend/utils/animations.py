"""
Shared completion animations for ComplianceIQ.

Replaces ``st.balloons()`` with a CSS-animated success banner
(Option C — no extra pip dependency).
"""

from __future__ import annotations

import streamlit as st

# CSS keyframes + HTML for the animated success banner
_SUCCESS_BANNER_HTML = """
<style>
@keyframes ciq-slide-in {
    0% { transform: translateY(-30px); opacity: 0; }
    20% { transform: translateY(0); opacity: 1; }
    80% { transform: translateY(0); opacity: 1; }
    100% { transform: translateY(-10px); opacity: 0; }
}
@keyframes ciq-icon-pop {
    0% { transform: scale(0.3) rotate(-20deg); opacity: 0; }
    50% { transform: scale(1.2) rotate(5deg); opacity: 1; }
    70% { transform: scale(0.95) rotate(0deg); }
    100% { transform: scale(1) rotate(0deg); opacity: 1; }
}
.ciq-success-banner {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 1rem 1.5rem;
    margin: 1rem 0;
    border-radius: 12px;
    background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
    border: 1px solid #A5D6A7;
    animation: ciq-slide-in 4s ease-in-out forwards;
    box-shadow: 0 4px 12px rgba(46, 125, 50, 0.15);
}
.ciq-success-banner .ciq-icon {
    font-size: 2rem;
    animation: ciq-icon-pop 0.6s ease-out forwards;
}
.ciq-success-banner .ciq-message {
    font-size: 1.1rem;
    font-weight: 600;
    color: #2E7D32;
}
.ciq-success-banner .ciq-detail {
    font-size: 0.9rem;
    color: #558B2F;
}
</style>
<div class="ciq-success-banner">
    <span class="ciq-icon">✅</span>
    <div>
        <div class="ciq-message">{message}</div>
        <div class="ciq-detail">{detail}</div>
    </div>
</div>
"""


def render_completion_animation(
    message: str = "Task completed successfully!",
    detail: str = "",
) -> None:
    """Render a CSS-animated success banner.

    Drop-in replacement for ``st.balloons()`` — no extra dependency.

    Parameters
    ----------
    message:
        Primary success text shown in bold green.
    detail:
        Optional secondary line below the message.
    """
    html = _SUCCESS_BANNER_HTML.format(
        message=message,
        detail=detail,
    )
    st.markdown(html, unsafe_allow_html=True)
