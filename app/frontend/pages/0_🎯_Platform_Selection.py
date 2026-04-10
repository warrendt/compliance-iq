"""
Platform Selection page for ComplianceIQ.
Allows users to choose their target compliance platform before
starting the control mapping workflow.
"""

import streamlit as st
from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.state_init import init_session_state
from components.task_status_bar import render_task_status_bar
from components.log_viewer import render_log_viewer
from components.backend_log_viewer import render_backend_log_viewer

# Page configuration
st.set_page_config(
    page_title="Platform Selection - ComplianceIQ",
    page_icon="🎯",
    layout="wide",
)

inject_azure_theme()
render_sidebar()
init_session_state()
render_task_status_bar()

st.markdown("## 🎯 Platform Selection")
st.markdown(
    "Choose your target compliance platform. This determines which policies "
    "and configurations will be generated from your compliance controls."
)

st.markdown("---")

# Platform cards
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 🛡️ Microsoft Defender for Cloud")
    st.markdown("""
    **Azure Policy & Defender Compliance**
    
    Map controls to Azure Policy definitions and deploy as policy initiatives 
    in Microsoft Defender for Cloud.
    
    **Capabilities:**
    - Azure Policy Initiatives
    - MCSB Control Mapping  
    - Defender Recommendations
    - Sovereign Landing Zone (SLZ) Policies
    
    **Best for:**
    - Azure-hosted workloads
    - Infrastructure compliance
    - Cloud security posture
    """)
    if st.button("Select Azure Defender →", key="select_azure", use_container_width=True, type="primary"):
        st.session_state.selected_platform = "azure_defender"
        st.session_state.platform_display_name = "Microsoft Defender for Cloud"
        st.success("✅ Platform selected: Microsoft Defender for Cloud")
        st.info("Navigate to **Upload Controls** to continue.")

with col2:
    st.markdown("### 📧 Microsoft 365 Compliance")
    st.markdown("""
    **M365 Compliance Policies**
    
    Map controls to Microsoft 365 policies including DLP, Conditional Access, 
    Device Compliance, and Information Protection.
    
    **Capabilities:**
    - Data Loss Prevention (DLP)
    - Conditional Access Policies
    - Device Compliance (Intune)
    - Information Protection
    
    **Best for:**
    - M365 workload protection
    - Identity & access management
    - Endpoint compliance
    """)
    if st.button("Select Microsoft 365 →", key="select_m365", use_container_width=True, type="primary"):
        st.session_state.selected_platform = "microsoft_365"
        st.session_state.platform_display_name = "Microsoft 365 Compliance"
        st.success("✅ Platform selected: Microsoft 365 Compliance")
        st.info("Navigate to **Upload Controls** to continue.")

with col3:
    st.markdown("### 🔍 Microsoft Purview")
    st.markdown("""
    **Data Governance & Protection**
    
    Map controls to Microsoft Purview configurations including sensitivity 
    labels, DLP policies, retention, and eDiscovery.
    
    **Capabilities:**
    - Sensitivity Labels
    - Purview DLP Policies
    - Retention Labels & Policies
    - eDiscovery & Records Management
    
    **Best for:**
    - Data classification & protection
    - Data lifecycle management
    - Regulatory record keeping
    """)
    if st.button("Select Microsoft Purview →", key="select_purview", use_container_width=True, type="primary"):
        st.session_state.selected_platform = "microsoft_purview"
        st.session_state.platform_display_name = "Microsoft Purview"
        st.success("✅ Platform selected: Microsoft Purview")
        st.info("Navigate to **Upload Controls** to continue.")

st.markdown("---")

# Show current selection
if "selected_platform" in st.session_state:
    st.markdown(
        f"**Current Selection:** {st.session_state.get('platform_display_name', 'None')} "
        f"(`{st.session_state.selected_platform}`)"
    )

# Comparison table
with st.expander("📊 Platform Comparison", expanded=False):
    st.markdown("""
    | Feature | Defender for Cloud | Microsoft 365 | Microsoft Purview |
    |---------|-------------------|---------------|-------------------|
    | **Primary Focus** | Infrastructure security | Workload compliance | Data governance |
    | **Policy Format** | Azure Policy JSON | Graph API JSON | Graph API JSON |
    | **Deployment** | Azure CLI / PowerShell | Microsoft Graph API | Microsoft Graph API |
    | **Dashboard** | Defender for Cloud | M365 Compliance Center | Purview Portal |
    | **Audit Mode** | DoNotEnforce | TestWithNotifications | TestWithNotifications |
    | **License Required** | Azure subscription | M365 E3/E5 | M365 E5 Compliance |
    | **API** | Azure Resource Manager | Microsoft Graph | Microsoft Graph |
    | **Sovereignty** | SLZ L1-L3 support | Regional settings | Regional settings |
    """)

with st.expander("❓ How to Choose", expanded=False):
    st.markdown("""
    ### Choosing the Right Platform
    
    **Choose Microsoft Defender for Cloud if:**
    - Your workloads run on Azure infrastructure
    - You need to enforce cloud security posture management
    - You require Azure Policy for infrastructure-level compliance
    - You need Sovereign Landing Zone (SLZ) data residency controls
    
    **Choose Microsoft 365 if:**
    - You need to protect Microsoft 365 services (Exchange, SharePoint, Teams)
    - You need Conditional Access policies for identity protection
    - You need device compliance policies via Intune
    - Your compliance requirements focus on data loss prevention
    
    **Choose Microsoft Purview if:**
    - You need data classification with sensitivity labels
    - You need data lifecycle management (retention policies)
    - You have regulatory record-keeping requirements
    - You need eDiscovery capabilities for investigations
    - You need unified data governance across M365 and beyond
    
    ### Can I Use Multiple Platforms?
    
    Yes! Many organizations use all three platforms together. You can run 
    the mapping process multiple times, once for each platform, using the 
    same compliance framework controls.
    """)

render_footer()
render_log_viewer()
render_backend_log_viewer()
