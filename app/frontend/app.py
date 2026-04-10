"""
Main Streamlit application for AI Control Mapping Agent.
"""

import streamlit as st
from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.state_init import init_session_state
from components.task_status_bar import render_task_status_bar
from components.log_viewer import render_log_viewer
from components.backend_log_viewer import render_backend_log_viewer
import httpx

# Page configuration
st.set_page_config(
    page_title="ComplianceIQ",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Azure theme
inject_azure_theme()

# ── Centralized session state initialization ──────────────────────────────
init_session_state()

# ── Session recovery — check if a saved session exists in Cosmos DB ───────
if (
    not st.session_state.get("controls")
    and not st.session_state.get("_session_recovery_checked")
):
    st.session_state["_session_recovery_checked"] = True
    try:
        _api = get_api_client()
        _saved = _api.load_session(st.session_state["session_uuid"])
        if _saved and (_saved.get("controls") or _saved.get("mappings")):
            st.session_state["_recovery_data"] = _saved
    except Exception:
        pass  # backend unavailable — skip silently

_recovery = st.session_state.pop("_recovery_data", None)
if _recovery:
    with st.container():
        _n_ctrl = len(_recovery.get("controls", []))
        _n_map = len(_recovery.get("mappings", []))
        _saved_at = _recovery.get("saved_at", "unknown")[:19]
        st.info(
            f"🔄 **Previous session found** — {_n_ctrl} controls, "
            f"{_n_map} mappings (saved {_saved_at})"
        )
        col_restore, col_skip = st.columns([1, 1])
        with col_restore:
            if st.button("♻️ Restore session", type="primary"):
                for key in ("controls", "mappings", "framework_name",
                            "policy_decisions", "generated_policy",
                            "selected_platform", "platform_display_name"):
                    if key in _recovery:
                        st.session_state[key] = _recovery[key]
                st.rerun()
        with col_skip:
            if st.button("🗑️ Start fresh"):
                st.rerun()

# Main content
st.markdown('<div class="main-header">🛡️ ComplianceIQ</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered Compliance Framework Mapping to Microsoft Defender for Cloud, Microsoft 365 &amp; Microsoft Purview</div>', unsafe_allow_html=True)

# Sidebar — shared branding + backend status
render_sidebar()

# ── Task status bar (shows active background jobs) ────────────────────────
render_task_status_bar()

with st.sidebar:
    st.markdown("---")
    st.markdown("#### 🔌 Backend Status")
    try:
        api_client = get_api_client()
        health = api_client.health_check()

        if health.get("status") == "healthy":
            st.success("✅ Backend Connected")
            st.caption(f"MCSB Controls: {health.get('mcsb_controls_loaded', 0)}")

            slz_count = health.get("slz_policy_count", 0)
            if slz_count > 0:
                st.success(f"✅ SLZ Policies: {slz_count}")
            else:
                st.warning("⚠️ SLZ Policies not loaded")

            if health.get("azure_openai", {}).get("status") == "configured":
                st.success("✅ Azure OpenAI Ready")
            else:
                st.warning("⚠️ Azure OpenAI not configured")
        else:
            st.error("❌ Backend Issues")

    except httpx.ConnectError:
        st.error("❌ Backend Offline")
        st.caption("Start backend: `uvicorn app.main:app`")
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

# Show selected platform
with st.sidebar:
    st.markdown("---")
    st.markdown("#### 🎯 Target Platform")
    platform_name = st.session_state.get('platform_display_name', 'Microsoft Defender for Cloud')
    platform_icons = {
        "Microsoft Defender for Cloud": "🛡️",
        "Microsoft 365 Compliance": "📧",
        "Microsoft Purview": "🔍",
    }
    st.info(f"{platform_icons.get(platform_name, '🎯')} {platform_name}")
    if st.button("Change Platform", key="change_platform", use_container_width=True):
        st.switch_page("pages/0_🎯_Platform_Selection.py")

# Main page content
st.markdown("---")

# Welcome message and instructions — responsive CSS grid
st.markdown(
    """
    <div class="ciq-step-grid">
        <div class="ciq-step-card">
            <h3>🎯 Step 0: Platform</h3>
            <p>Choose your target compliance platform.</p>
            <p><strong>Options:</strong></p>
            <ul><li>Defender for Cloud</li><li>Microsoft 365</li><li>Microsoft Purview</li></ul>
        </div>
        <div class="ciq-step-card">
            <h3>📁 Step 1: Upload</h3>
            <p>Upload your compliance framework controls in CSV or Excel format.</p>
            <p><strong>Required columns:</strong></p>
            <ul><li>Control ID</li><li>Control Name</li><li>Description</li><li>Domain (optional)</li></ul>
        </div>
        <div class="ciq-step-card">
            <h3>🤖 Step 2: Map</h3>
            <p>Use AI to automatically map your controls to the Microsoft Cloud Security Benchmark.</p>
            <p><strong>Features:</strong></p>
            <ul><li>AI-powered analysis</li><li>Confidence scoring</li><li>Sovereignty level assignment</li><li>Detailed reasoning</li></ul>
        </div>
        <div class="ciq-step-card">
            <h3>📦 Step 3: Export</h3>
            <p>Generate Azure Policy initiatives ready for deployment.</p>
            <p><strong>Outputs:</strong></p>
            <ul><li>MCSB Policy Initiative</li><li>SLZ Sovereign Initiatives</li><li>Bicep templates &amp; scripts</li></ul>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Navigation buttons (below the grid)
col0, col1, col2, col3 = st.columns(4)
with col0:
    if st.button("Select Platform →", key="nav_platform", use_container_width=True):
        st.switch_page("pages/0_🎯_Platform_Selection.py")
with col1:
    if st.button("Go to Upload →", key="nav_upload", use_container_width=True):
        st.switch_page("pages/1_📁_Upload_Controls.py")
with col2:
    if st.button("Go to Mapping →", key="nav_mapping", use_container_width=True):
        st.switch_page("pages/2_🤖_AI_Mapping.py")
with col3:
    if st.button("Go to Export →", key="nav_export", use_container_width=True):
        st.switch_page("pages/4_📦_Export_Policy.py")

st.markdown("---")

# Quick start guide
with st.expander("📖 Quick Start Guide", expanded=False):
    st.markdown("""
    ### How to Use This Tool
    
    0. **Select Your Platform**
       - Choose your target: Azure Defender, Microsoft 365, or Microsoft Purview
       - Each platform generates different policy types and deployment scripts
    
    1. **Prepare Your Framework**
       - Export your compliance framework controls to CSV or Excel
       - Ensure you have Control ID, Name, and Description columns
    
    2. **Upload Controls**
       - Navigate to the Upload page
       - Select your file and validate the column mapping
       - Preview your controls before proceeding
    
    3. **Run AI Mapping**
       - The AI will analyze each control
       - Match it to the most relevant controls for your selected platform
       - Provide confidence scores and reasoning
    
    4. **Review & Adjust**
       - Review the AI-generated mappings
       - Edit any mappings that need adjustment
       - Filter by confidence threshold
    
    5. **Generate Policies**
       - **Azure Defender:** Azure Policy initiatives (JSON, Bicep, scripts)
       - **Microsoft 365:** DLP, Conditional Access, Device Compliance policies
       - **Microsoft Purview:** Sensitivity labels, retention labels, DLP policies
    
    6. **Deploy**
       - **Azure Defender:** Azure CLI / PowerShell / Portal
       - **Microsoft 365:** Microsoft Graph API / PowerShell
       - **Microsoft Purview:** Microsoft Graph API / PowerShell
    
    ### Supported Platforms
    
    | Platform | Policy Types | Deployment |
    |----------|-------------|------------|
    | **Defender for Cloud** | Azure Policy, MCSB, SLZ | Azure CLI / PS |
    | **Microsoft 365** | DLP, CA, Device, Info Protection | Graph API / PS |
    | **Microsoft Purview** | Labels, DLP, Retention, eDiscovery | Graph API / PS |
    
    ### Supported Frameworks
    
    This tool has been tested with:
    - SAMA (Saudi Arabian Monetary Authority)
    - CCC (UAE Cloud Computing Compliance)
    - ADHICS (Abu Dhabi Healthcare)
    - SITA (South African IT Architecture)
    - POPIA (South African Data Protection)
    - And more!
    
    ### Need Help?
    
    - Check the documentation in each page
    - Review example files in `/data/examples/`
    - Contact support for assistance
    """)

# Footer
render_footer()

# Log viewers
render_log_viewer()
render_backend_log_viewer()
