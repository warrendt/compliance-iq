"""
Shared theme & branding for all Streamlit pages.

Supports multiple configurable colour presets selected via
``st.session_state["selected_theme"]``.
"""

from __future__ import annotations

from typing import Dict

import streamlit as st


# ── Theme presets ─────────────────────────────────────────────────────────

THEME_PRESETS: Dict[str, Dict[str, str]] = {
    "azure_blue": {
        "label": "Azure Blue",
        "primary": "#0078D4",
        "primary_dark": "#003B73",
        "primary_hover": "#106EBE",
        "accent": "#50E6FF",
        "bg": "#F3F2F1",
        "success": "#107C10",
        "sidebar_gradient_start": "#001D3D",
        "sidebar_gradient_end": "#003566",
        "sidebar_text": "#E0E0E0",
        "sidebar_metric": "#50E6FF",
        "header_text": "#605E5C",
        "footer_text": "#8A8886",
    },
    "dark_mode": {
        "label": "Dark Mode",
        "primary": "#4FC3F7",
        "primary_dark": "#0277BD",
        "primary_hover": "#29B6F6",
        "accent": "#80DEEA",
        "bg": "#121212",
        "success": "#66BB6A",
        "sidebar_gradient_start": "#1A1A2E",
        "sidebar_gradient_end": "#16213E",
        "sidebar_text": "#E0E0E0",
        "sidebar_metric": "#80DEEA",
        "header_text": "#B0BEC5",
        "footer_text": "#757575",
    },
    "high_contrast": {
        "label": "High Contrast",
        "primary": "#FFD600",
        "primary_dark": "#000000",
        "primary_hover": "#FFEA00",
        "accent": "#FFFFFF",
        "bg": "#000000",
        "success": "#00E676",
        "sidebar_gradient_start": "#000000",
        "sidebar_gradient_end": "#1A1A1A",
        "sidebar_text": "#FFFFFF",
        "sidebar_metric": "#FFD600",
        "header_text": "#FFFFFF",
        "footer_text": "#BDBDBD",
    },
    "green_compliance": {
        "label": "Green Compliance",
        "primary": "#2E7D32",
        "primary_dark": "#1B5E20",
        "primary_hover": "#388E3C",
        "accent": "#A5D6A7",
        "bg": "#F1F8E9",
        "success": "#43A047",
        "sidebar_gradient_start": "#1B3A1B",
        "sidebar_gradient_end": "#2E5A2E",
        "sidebar_text": "#E8F5E9",
        "sidebar_metric": "#A5D6A7",
        "header_text": "#558B2F",
        "footer_text": "#8A8886",
    },
}


def _get_active_theme() -> Dict[str, str]:
    """Return the currently active theme dict."""
    key = st.session_state.get("selected_theme", "azure_blue")
    return THEME_PRESETS.get(key, THEME_PRESETS["azure_blue"])


def _build_css(theme: Dict[str, str]) -> str:
    """Build the full CSS string from a theme dict."""
    return f"""<style>
    /* Dynamic palette */
    :root {{
        --ciq-primary: {theme["primary"]};
        --ciq-primary-dark: {theme["primary_dark"]};
        --ciq-accent: {theme["accent"]};
        --ciq-bg: {theme["bg"]};
        --ciq-success: {theme["success"]};
    }}

    /* Header styling */
    .main-header {{
        font-size: 2.6rem;
        font-weight: 700;
        background: linear-gradient(90deg, {theme["primary"]}, {theme["accent"]});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.25rem;
    }}
    .sub-header {{
        font-size: 1.1rem;
        text-align: center;
        color: {theme["header_text"]};
        margin-bottom: 1.5rem;
    }}

    /* Sidebar branding */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {theme["sidebar_gradient_start"]} 0%, {theme["sidebar_gradient_end"]} 100%);
    }}
    [data-testid="stSidebar"] * {{
        color: {theme["sidebar_text"]} !important;
    }}
    [data-testid="stSidebar"] .stMetric label,
    [data-testid="stSidebar"] .stMetric [data-testid="stMetricValue"] {{
        color: {theme["sidebar_metric"]} !important;
    }}

    /* Primary buttons */
    .stButton > button[kind="primary"] {{
        background-color: {theme["primary"]};
        border: none;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: {theme["primary_hover"]};
    }}

    /* Footer */
    .wdt-footer {{
        text-align: center;
        padding: 2rem 0 1rem;
        color: {theme["footer_text"]};
        font-size: 0.85rem;
    }}
    .wdt-footer a {{
        color: {theme["primary"]};
        text-decoration: none;
    }}

    /* ── Mobile responsiveness ──────────────────────────────────────────── */

    /* Responsive step-card grid (replaces hard st.columns(4)) */
    .ciq-step-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 1.2rem;
        margin-bottom: 1rem;
    }}
    .ciq-step-card {{
        border: 1px solid #E0E0E0;
        border-radius: 12px;
        padding: 1.2rem;
        background: white;
        transition: box-shadow 0.2s ease;
    }}
    .ciq-step-card:hover {{
        box-shadow: 0 4px 16px rgba(0,0,0,0.10);
    }}
    .ciq-step-card h3 {{
        margin-top: 0;
        font-size: 1.15rem;
    }}
    .ciq-step-card p {{
        font-size: 0.92rem;
        color: #555;
    }}

    /* Floating mobile bottom nav */
    .ciq-mobile-nav {{
        display: none;
    }}

    @media (max-width: 768px) {{
        /* Force single-column step cards */
        .ciq-step-grid {{
            grid-template-columns: 1fr;
        }}
        /* Reduce header font */
        .main-header {{
            font-size: 1.8rem;
        }}
        .sub-header {{
            font-size: 0.95rem;
        }}
        /* Smaller metric cards */
        .stMetric {{
            padding: 0.5rem !important;
        }}
        [data-testid="stMetricValue"] {{
            font-size: 1.2rem !important;
        }}
        /* Show mobile bottom nav */
        .ciq-mobile-nav {{
            display: flex;
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: {theme["sidebar_gradient_end"]};
            padding: 0.6rem 0.4rem;
            justify-content: space-around;
            z-index: 9999;
            box-shadow: 0 -2px 8px rgba(0,0,0,0.15);
        }}
        .ciq-mobile-nav a {{
            color: {theme["sidebar_text"]} !important;
            text-decoration: none;
            font-size: 0.72rem;
            text-align: center;
            flex: 1;
        }}
        /* Add bottom padding so content isn't hidden behind nav */
        .main .block-container {{
            padding-bottom: 4rem !important;
        }}
    }}

    @media (max-width: 480px) {{
        .main-header {{
            font-size: 1.5rem;
        }}
        .sub-header {{
            font-size: 0.85rem;
            margin-bottom: 0.8rem;
        }}
        .ciq-step-card {{
            padding: 0.8rem;
        }}
    }}
</style>

<!-- Auto-collapse sidebar on mobile -->
<script>
(function() {{
    if (window.innerWidth < 768) {{
        var btn = window.parent.document.querySelector('[data-testid="stSidebar"] button[kind="header"]');
        if (btn) btn.click();
    }}
}})();
</script>
"""


# ── Public API ────────────────────────────────────────────────────────────

def inject_azure_theme():
    """Inject themed CSS into the current page using the active preset."""
    theme = _get_active_theme()
    st.markdown(_build_css(theme), unsafe_allow_html=True)


def render_sidebar():
    """Render a consistent branded sidebar across all pages."""
    with st.sidebar:
        st.markdown("### 🛡️ ComplianceIQ")
        st.caption("AI-Powered Compliance Mapping")
        st.markdown("---")

        # ── Clickable navigation ──
        st.page_link("app.py", label="🏠 Home", icon=None)
        st.page_link("pages/1_📁_Upload_Controls.py", label="📁 Upload Controls")
        st.page_link("pages/2_🤖_AI_Mapping.py", label="🤖 AI Mapping")
        st.page_link("pages/3_✏️_Review_Edit.py", label="✏️ Review & Edit")
        st.page_link("pages/4_📦_Export_Policy.py", label="📦 Export Policy")
        st.page_link("pages/5_🚀_PDF_Pipeline.py", label="🚀 PDF Pipeline")
        st.page_link("pages/6_🔍_Policy_Explorer.py", label="🔍 Policy Explorer")
        st.markdown("---")

        # ── Appearance ──
        st.markdown("#### 🎨 Appearance")
        theme_labels = [v["label"] for v in THEME_PRESETS.values()]
        theme_keys = list(THEME_PRESETS.keys())
        current_idx = theme_keys.index(
            st.session_state.get("selected_theme", "azure_blue")
        ) if st.session_state.get("selected_theme", "azure_blue") in theme_keys else 0
        chosen_label = st.selectbox(
            "Color theme",
            options=theme_labels,
            index=current_idx,
            key="_theme_selector",
            help="Choose a colour preset — takes effect immediately",
        )
        chosen_key = theme_keys[theme_labels.index(chosen_label)]
        if chosen_key != st.session_state.get("selected_theme"):
            st.session_state["selected_theme"] = chosen_key
            st.rerun()

        st.markdown("---")

        # ── Progress tracker ──
        controls = st.session_state.get("controls", [])
        mappings = st.session_state.get("mappings", [])
        fw = st.session_state.get("framework_name", "")

        steps_done = sum([
            len(controls) > 0,
            len(mappings) > 0,
            bool(st.session_state.get("generated_policy")),
        ])
        total_steps = 3
        pct = int(steps_done / total_steps * 100)

        st.markdown("#### 📊 Progress")
        st.progress(pct / 100, text=f"{pct}% complete")

        step_icons = [
            ("Upload controls", len(controls) > 0),
            ("Run AI mapping", len(mappings) > 0),
            ("Generate policy", bool(st.session_state.get("generated_policy"))),
        ]
        for label, done in step_icons:
            st.markdown(f"{'✅' if done else '⬜'} {label}")

        st.markdown("---")

        # ── Session metrics ──
        if fw:
            st.info(f"🗂️ **{fw}**")
        col1, col2 = st.columns(2)
        col1.metric("Controls", len(controls))
        col2.metric("Mappings", len(mappings))

        # ── Developer tools ──
        st.markdown("---")
        st.checkbox("📡 Show API Logs", key="show_api_logs",
                     help="Show request/response log panel at the bottom of each page")
        st.checkbox("📋 Show Backend Logs", key="show_backend_logs",
                     help="Show live application logs from the backend container")
        if st.session_state.get("show_backend_logs"):
            st.selectbox(
                "Poll interval (seconds)",
                options=[5, 10, 30, 60],
                index=1,
                key="backend_log_poll_interval",
                help="How often to refresh backend logs",
            )

        st.markdown("---")
        st.caption("Made by **Warren DT**")

        # ── Authenticated user ──
        try:
            from utils.auth import get_current_user, logout

            user = get_current_user()
            if user:
                st.markdown("---")
                st.markdown(f"👤 **{user.display_name}**")
                st.caption(user.email)
                if st.button("Sign out", key="sidebar_signout"):
                    logout()
                    st.rerun()
        except Exception:
            pass  # auth module may not be available


def render_footer():
    """Render the page footer with branding and mobile bottom nav."""
    st.markdown("---")
    st.markdown(
        '<div class="wdt-footer">'
        "<strong>ComplianceIQ — AI Control Mapping Agent</strong><br>"
        "Made by <strong>Warren DT</strong> &nbsp;|&nbsp; "
        "Powered by Azure OpenAI &bull; MCSB &bull; Sovereign Landing Zone"
        "</div>",
        unsafe_allow_html=True,
    )
    # Mobile-only floating bottom navigation
    st.markdown(
        '<nav class="ciq-mobile-nav">'
        '<a href="/">🏠<br>Home</a>'
        '<a href="/Upload_Controls">📁<br>Upload</a>'
        '<a href="/AI_Mapping">🤖<br>Map</a>'
        '<a href="/Review_Edit">✏️<br>Review</a>'
        '<a href="/Export_Policy">📦<br>Export</a>'
        "</nav>",
        unsafe_allow_html=True,
    )
