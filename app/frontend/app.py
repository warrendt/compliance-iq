"""
Main Streamlit application for AI Control Mapping Agent.
"""

import streamlit as st
from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
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

# Initialize session state
if 'controls' not in st.session_state:
    st.session_state.controls = []
if 'mappings' not in st.session_state:
    st.session_state.mappings = []
if 'framework_name' not in st.session_state:
    st.session_state.framework_name = ""
if 'job_id' not in st.session_state:
    st.session_state.job_id = None
if 'selected_platform' not in st.session_state:
    st.session_state.selected_platform = "azure_defender"
if 'platform_display_name' not in st.session_state:
    st.session_state.platform_display_name = "Microsoft Defender for Cloud"

# Main content
st.markdown('<div class="main-header">🛡️ ComplianceIQ</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered Compliance Framework Mapping to Microsoft Defender for Cloud, Microsoft 365 &amp; Microsoft Purview</div>', unsafe_allow_html=True)

# Sidebar — shared branding + backend status
render_sidebar()

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

# Welcome message and instructions
col0, col1, col2, col3 = st.columns(4)

with col0:
    st.markdown("### 🎯 Step 0: Platform")
    st.markdown("""
    Choose your target compliance platform.
    
    **Options:**
    - Defender for Cloud
    - Microsoft 365
    - Microsoft Purview
    """)
    if st.button("Select Platform →", key="nav_platform", use_container_width=True):
        st.switch_page("pages/0_🎯_Platform_Selection.py")

with col1:
    st.markdown("### 📁 Step 1: Upload")
    st.markdown("""
    Upload your compliance framework controls in CSV or Excel format.
    
    **Required columns:**
    - Control ID
    - Control Name  
    - Description
    - Domain (optional)
    """)
    if st.button("Go to Upload →", key="nav_upload", use_container_width=True):
        st.switch_page("pages/1_📁_Upload_Controls.py")

with col2:
    st.markdown("### 🤖 Step 2: Map")
    st.markdown("""
    Use AI to automatically map your controls to the Microsoft Cloud Security Benchmark.
    
    **Features:**
    - AI-powered analysis
    - Confidence scoring
    - Sovereignty level assignment
    - Detailed reasoning
    """)
    if st.button("Go to Mapping →", key="nav_mapping", use_container_width=True):
        st.switch_page("pages/2_🤖_AI_Mapping.py")

with col3:
    st.markdown("### 📦 Step 3: Export")
    st.markdown("""
    Generate Azure Policy initiatives ready for deployment.
    
    **Outputs:**
    - MCSB Policy Initiative
    - SLZ Sovereign Initiatives
    - Bicep templates & scripts
    """)
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
