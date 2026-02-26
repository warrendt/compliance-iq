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
        st.markdown("### 🛡️ CCToolkit")
        st.caption("Cloud Compliance Toolkit")
        st.markdown("---")

        st.markdown("#### 📋 Navigation")
        st.markdown(
            "1. **📁 Upload Controls**\n"
            "2. **🤖 AI Mapping**\n"
            "3. **✏️ Review & Edit**\n"
            "4. **📦 Export Policy**\n"
            "5. **🚀 PDF Pipeline**"
        )
        st.markdown("---")

        st.markdown("#### 📊 Session")
        st.metric("Controls", len(st.session_state.get("controls", [])))
        st.metric("Mappings", len(st.session_state.get("mappings", [])))
        fw = st.session_state.get("framework_name", "")
        if fw:
            st.info(f"**{fw}**")

        st.markdown("---")
        st.caption("Made by **Warren DT**")


def render_footer():
    """Render the page footer with branding."""
    st.markdown("---")
    st.markdown(
        '<div class="wdt-footer">'
        "<strong>CCToolkit — AI Control Mapping Agent</strong><br>"
        "Made by <strong>Warren DT</strong> &nbsp;|&nbsp; "
        "Powered by Azure OpenAI &bull; MCSB &bull; Sovereign Landing Zone"
        "</div>",
        unsafe_allow_html=True,
    )
