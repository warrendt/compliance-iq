"""
Shared Azure theme & branding for all Streamlit pages.
"""

import streamlit as st


AZURE_CSS = """
<style>
    /* Azure primary palette */
    :root {
        --azure-blue: #0078D4;
        --azure-dark: #003B73;
        --azure-light: #50E6FF;
        --azure-bg: #F3F2F1;
        --azure-green: #107C10;
    }

    /* Header styling */
    .main-header {
        font-size: 2.6rem;
        font-weight: 700;
        background: linear-gradient(90deg, #0078D4, #50E6FF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.25rem;
    }
    .sub-header {
        font-size: 1.1rem;
        text-align: center;
        color: #605E5C;
        margin-bottom: 1.5rem;
    }

    /* Sidebar branding */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #001D3D 0%, #003566 100%);
    }
    [data-testid="stSidebar"] * {
        color: #E0E0E0 !important;
    }
    [data-testid="stSidebar"] .stMetric label,
    [data-testid="stSidebar"] .stMetric [data-testid="stMetricValue"] {
        color: #50E6FF !important;
    }

    /* Primary buttons */
    .stButton > button[kind="primary"] {
        background-color: #0078D4;
        border: none;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #106EBE;
    }

    /* Footer */
    .wdt-footer {
        text-align: center;
        padding: 2rem 0 1rem;
        color: #8A8886;
        font-size: 0.85rem;
    }
    .wdt-footer a {
        color: #0078D4;
        text-decoration: none;
    }
</style>
"""


def inject_azure_theme():
    """Inject Azure-themed CSS into the current page."""
    st.markdown(AZURE_CSS, unsafe_allow_html=True)


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
    """Render the page footer with branding."""
    st.markdown("---")
    st.markdown(
        '<div class="wdt-footer">'
        "<strong>ComplianceIQ — AI Control Mapping Agent</strong><br>"
        "Made by <strong>Warren DT</strong> &nbsp;|&nbsp; "
        "Powered by Azure OpenAI &bull; MCSB &bull; Sovereign Landing Zone"
        "</div>",
        unsafe_allow_html=True,
    )
