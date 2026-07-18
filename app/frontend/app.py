"""
Main Streamlit application for AI Control Mapping Agent.
"""

import streamlit as st
from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.components import (
    render_page_header,
    render_workflow_stepper,
    render_metric_card,
    render_status_badge,
    render_section_heading,
)
from utils.state_init import (
    clear_workflow_state,
    init_session_state,
    recover_session_state,
)
from utils.auth import get_request_path
from utils.landing import require_login
from components.task_status_bar import render_task_status_bar
from components.log_viewer import render_log_viewer
from components.backend_log_viewer import render_backend_log_viewer
import httpx

_DEEPLINK_PAGE_MAP = {
    "Platform_Selection": "pages/0_🎯_Platform_Selection.py",
    "Upload_Controls": "pages/1_📁_Upload_Controls.py",
    "AI_Mapping": "pages/2_🤖_AI_Mapping.py",
    "Review_Edit": "pages/3_✏️_Review_Edit.py",
    "Export_Policy": "pages/4_📦_Export_Policy.py",
    "PDF_Pipeline": "pages/5_🚀_PDF_Pipeline.py",
    "Policy_Explorer": "pages/6_🔍_Policy_Explorer.py",
    "Profile": "pages/7_👤_Profile.py",
}

# Page configuration
st.set_page_config(
    page_title="ComplianceIQ",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Azure theme
inject_azure_theme()

# ── Auth gate ─────────────────────────────────────────────────────────────
# With Easy Auth set to AllowAnonymous, render the branded landing page for
# unauthenticated visitors and stop; authenticated users fall through.
require_login()

# ── Centralized session state initialization ──────────────────────────────
init_session_state()

# ── Direct deep-link recovery behind reverse proxy ─────────────────────────
_request_path = get_request_path().strip("/")
if _request_path:
    _first_segment = _request_path.split("/", 1)[0]
    _target_page = _DEEPLINK_PAGE_MAP.get(_first_segment)
    if _target_page:
        st.switch_page(_target_page)

# ── Session recovery ────────────────────────────────────────────────────────
_session_recovered = False
try:
    _session_recovered = recover_session_state(get_api_client())
except Exception as exc:
    st.session_state["session_save_error"] = f"Session recovery failed: {exc}"

if _session_recovered:
    st.info(
        f"Restored **{len(st.session_state.controls)} controls** and "
        f"**{len(st.session_state.mappings)} mappings** from your latest session."
    )
    if st.button("Start a new session"):
        clear_workflow_state()
        st.rerun()

# ── Lifecycle state (drives the header stepper + dashboard) ─────────────────
_controls = st.session_state.get("controls", [])
_mappings = st.session_state.get("mappings", [])
_has_policy = bool(st.session_state.get("generated_policy"))
_platform_selected = "selected_platform" in st.session_state

if len(_controls) == 0:
    _active_stage = "Govern"
elif len(_mappings) == 0:
    _active_stage = "Map"
elif not _has_policy:
    _active_stage = "Enforce"
else:
    _active_stage = "Report"

# Main content — brand header + lifecycle stepper
render_page_header(
    "ComplianceIQ",
    eyebrow="Compliance control tower",
    description=(
        "Map regulatory control frameworks to Microsoft Defender for Cloud, "
        "Microsoft 365 and Microsoft Purview — then generate deployable policy."
    ),
)
render_workflow_stepper(_active_stage)

# Sidebar — shared branding + backend status
render_sidebar()

# ── Task status bar (shows active background jobs) ────────────────────────
render_task_status_bar()

with st.sidebar:
    st.markdown("---")
    st.markdown("#### Backend status")
    try:
        api_client = get_api_client()
        health = api_client.health_check()

        if health.get("status") == "healthy":
            st.success("Backend connected")
            st.caption(f"MCSB Controls: {health.get('mcsb_controls_loaded', 0)}")

            slz_count = health.get("slz_policy_count", 0)
            if slz_count > 0:
                st.success(f"SLZ policies: {slz_count}")
            else:
                st.warning("SLZ policies not loaded")

            if health.get("azure_openai_connected"):
                st.success("Azure OpenAI ready")
            else:
                st.warning("Azure OpenAI not configured")
        else:
            st.error("Backend issues")

    except httpx.ConnectError:
        st.error("Backend offline")
        st.caption("Start backend: `uvicorn app.main:app`")
    except Exception as e:
        st.error(f"Error: {str(e)}")

# Show selected platform
with st.sidebar:
    st.markdown("---")
    st.markdown("#### Target platform")
    platform_name = st.session_state.get('platform_display_name', 'Microsoft Defender for Cloud')
    st.info(platform_name)
    if st.button("Change platform", key="change_platform", use_container_width=True):
        st.switch_page("pages/0_🎯_Platform_Selection.py")

# ── Control-tower dashboard ────────────────────────────────────────────────
st.markdown("---")

_controls_variant, _controls_label = (
    ("success", "Loaded") if len(_controls) else ("neutral", "Not started")
)
if len(_mappings):
    _map_variant, _map_label = "success", "Mapped"
elif len(_controls):
    _map_variant, _map_label = "warning", "Pending"
else:
    _map_variant, _map_label = "neutral", "Not started"
if _has_policy:
    _policy_variant, _policy_label = "success", "Generated"
elif len(_mappings):
    _policy_variant, _policy_label = "warning", "Pending"
else:
    _policy_variant, _policy_label = "neutral", "Not started"

k0, k1, k2 = st.columns(3)
with k0:
    render_metric_card(
        "Controls loaded", len(_controls),
        sub=st.session_state.get("framework_name") or "No framework yet",
    )
    render_status_badge(_controls_variant, _controls_label)
with k1:
    render_metric_card(
        "Controls mapped", len(_mappings),
        sub="AI-mapped to platform controls",
    )
    render_status_badge(_map_variant, _map_label)
with k2:
    render_metric_card(
        "Policies generated", "Yes" if _has_policy else "0",
        sub="Ready for review & export",
    )
    render_status_badge(_policy_variant, _policy_label)

# ── Next best action (a single primary action for the whole page) ──────────
if not _platform_selected:
    _next_label, _next_page = "Choose platform", "pages/0_🎯_Platform_Selection.py"
elif len(_controls) == 0:
    _next_label, _next_page = "Upload controls", "pages/1_📁_Upload_Controls.py"
elif len(_mappings) == 0:
    _next_label, _next_page = "Run AI mapping", "pages/2_🤖_AI_Mapping.py"
elif not _has_policy:
    _next_label, _next_page = "Review & export", "pages/3_✏️_Review_Edit.py"
else:
    _next_label, _next_page = "View export package", "pages/4_📦_Export_Policy.py"

render_section_heading("Your compliance journey")
st.markdown(
    "1. **Ingest** — choose a platform and upload your control framework  \n"
    "2. **Map** — AI maps each control to platform controls with a confidence score  \n"
    "3. **Review** — confirm or adjust mappings and close control gaps  \n"
    "4. **Deploy** — generate and export policy initiatives ready for Azure"
)
if st.button(f"Continue: {_next_label}", type="primary", key="home_continue"):
    st.switch_page(_next_page)

# Quick start guide
with st.expander("How ComplianceIQ works", expanded=False):
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
