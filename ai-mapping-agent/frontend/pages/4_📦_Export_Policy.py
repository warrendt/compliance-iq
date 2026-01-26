"""
Export Policy Page - Generate and download Azure Policy initiatives.
"""

import streamlit as st
import json
import httpx
from utils.api_client import get_api_client

st.set_page_config(
    page_title="Export Policy | AI Mapping Agent",
    page_icon="📦",
    layout="wide"
)

# Initialize session state
if 'mappings' not in st.session_state:
    st.session_state.mappings = []
if 'framework_name' not in st.session_state:
    st.session_state.framework_name = ""
if 'generated_policy' not in st.session_state:
    st.session_state.generated_policy = None

# Header
st.title("📦 Export Azure Policy Initiative")
st.markdown("Generate and download Azure Policy Initiative with deployment scripts")

st.markdown("---")

# Check if mappings exist
if not st.session_state.mappings:
    st.warning("⚠️ No mappings to export. Please complete the mapping and review steps first.")
    if st.button("Go to AI Mapping"):
        st.switch_page("pages/2_🤖_AI_Mapping.py")
    st.stop()

# Display mapping summary
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Framework", st.session_state.framework_name)

with col2:
    st.metric("Total Mappings", len(st.session_state.mappings))

with col3:
    avg_confidence = sum(m.get('confidence_score', 0) for m in st.session_state.mappings) / len(st.session_state.mappings)
    st.metric("Avg Confidence", f"{avg_confidence:.0%}")

with col4:
    unique_mcsb = len(set(m.get('mcsb_control_id', '') for m in st.session_state.mappings if m.get('mcsb_control_id')))
    st.metric("Unique MCSB Controls", unique_mcsb)

st.markdown("---")

# Export configuration
st.markdown("### ⚙️ Export Configuration")

col_config1, col_config2 = st.columns(2)

with col_config1:
    min_confidence = st.slider(
        "Minimum Confidence Score",
        min_value=0.0,
        max_value=1.0,
        value=0.6,
        step=0.05,
        help="Only include mappings with confidence score >= this value"
    )
    
    initiative_name = st.text_input(
        "Initiative Name",
        value=f"{st.session_state.framework_name} Compliance",
        help="Display name for the Azure Policy Initiative"
    )

with col_config2:
    include_manual = st.checkbox(
        "Include Manual Overrides",
        value=True,
        help="Include mappings that were manually edited"
    )
    
    initiative_description = st.text_area(
        "Initiative Description",
        value=f"Azure Policy Initiative for {st.session_state.framework_name} compliance based on MCSB mappings",
        height=100,
        help="Description for the Azure Policy Initiative"
    )

# Filter mappings based on config
filtered_mappings = [
    m for m in st.session_state.mappings
    if m.get('confidence_score', 0) >= min_confidence
    and (include_manual or not m.get('manual_override', False))
]

st.info(f"📋 Will include **{len(filtered_mappings)}** of **{len(st.session_state.mappings)}** mappings based on filters")

if len(filtered_mappings) == 0:
    st.error("⚠️ No mappings meet the criteria. Adjust your filters.")
    st.stop()

st.markdown("---")

# Generate policy button
if st.button("🚀 Generate Azure Policy Initiative", type="primary", use_container_width=True):
    with st.spinner("Generating Azure Policy Initiative..."):
        api_client = get_api_client()
        
        try:
            # Prepare request
            request_data = {
                "framework_name": st.session_state.framework_name,
                "mappings": filtered_mappings,
                "initiative_name": initiative_name,
                "initiative_description": initiative_description
            }
            
            # Call API
            result = api_client.generate_policy_initiative(request_data)
            
            st.session_state.generated_policy = result
            st.success("✅ Policy initiative generated successfully!")
            st.balloons()
            
        except httpx.ConnectError:
            st.error("❌ Cannot connect to backend. Make sure it's running.")
        except Exception as e:
            st.error(f"❌ Error generating policy: {str(e)}")

# Display generated policy
if st.session_state.generated_policy:
    st.markdown("---")
    st.markdown("### 📄 Generated Policy Initiative")
    
    policy = st.session_state.generated_policy
    
    # Summary
    col_sum1, col_sum2, col_sum3 = st.columns(3)
    
    with col_sum1:
        st.metric("Initiative ID", policy.get('initiative_id', 'N/A'))
    
    with col_sum2:
        policy_refs = policy.get('initiative_json', {}).get('properties', {}).get('policyDefinitionGroups', [])
        st.metric("Policy Groups", len(policy_refs))
    
    with col_sum3:
        policy_defs = policy.get('initiative_json', {}).get('properties', {}).get('policyDefinitions', [])
        st.metric("Policy Definitions", len(policy_defs))
    
    st.markdown("---")
    
    # Tabs for different outputs
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Initiative JSON", "🔧 PowerShell Script", "📊 Bicep Template", "📖 Deployment Guide"])
    
    with tab1:
        st.markdown("#### Azure Policy Initiative JSON")
        st.markdown("Use this JSON to create the policy initiative via Azure Portal or Azure CLI")
        
        initiative_json = json.dumps(policy.get('initiative_json', {}), indent=2)
        st.code(initiative_json, language="json", line_numbers=True)
        
        st.download_button(
            label="📥 Download Initiative JSON",
            data=initiative_json,
            file_name=f"{st.session_state.framework_name.replace(' ', '_')}_initiative.json",
            mime="application/json"
        )
    
    with tab2:
        st.markdown("#### PowerShell Deployment Script")
        st.markdown("Run this script to deploy the initiative to your Azure subscription")
        
        powershell_script = policy.get('powershell_script', '# No script generated')
        st.code(powershell_script, language="powershell", line_numbers=True)
        
        st.download_button(
            label="📥 Download PowerShell Script",
            data=powershell_script,
            file_name=f"Deploy-{st.session_state.framework_name.replace(' ', '_')}Initiative.ps1",
            mime="text/plain"
        )
    
    with tab3:
        st.markdown("#### Bicep Template")
        st.markdown("Use this Bicep template for Infrastructure as Code deployment")
        
        bicep_template = policy.get('bicep_template', '# No template generated')
        st.code(bicep_template, language="bicep", line_numbers=True)
        
        st.download_button(
            label="📥 Download Bicep Template",
            data=bicep_template,
            file_name=f"{st.session_state.framework_name.replace(' ', '_')}_initiative.bicep",
            mime="text/plain"
        )
    
    with tab4:
        st.markdown("#### 📖 Deployment Guide")
        
        st.markdown("""
        ### Prerequisites
        - Azure subscription with Owner or Contributor role
        - Azure PowerShell module or Azure CLI installed
        - Authenticated to Azure (run `Connect-AzAccount` or `az login`)
        
        ### Deployment Options
        
        #### Option 1: Azure Portal
        1. Download the Initiative JSON
        2. Go to Azure Portal → Policy → Definitions
        3. Click "+ Policy definition" → "Initiative definition"
        4. Paste the JSON content
        5. Save and assign to desired scope
        
        #### Option 2: PowerShell
        ```powershell
        # Download and run the PowerShell script
        Connect-AzAccount
        ./Deploy-{initiative_name.replace(' ', '')}.ps1
        ```
        
        #### Option 3: Azure CLI
        ```bash
        # Create the initiative
        az policy set-definition create \\
            --name "{initiative_name.replace(' ', '-')}" \\
            --display-name "{initiative_name}" \\
            --description "{initiative_description}" \\
            --definitions @{st.session_state.framework_name.replace(' ', '_')}_initiative.json
        ```
        
        #### Option 4: Bicep/IaC
        ```bash
        # Deploy using Bicep
        az deployment sub create \\
            --location eastus \\
            --template-file {st.session_state.framework_name.replace(' ', '_')}_initiative.bicep
        ```
        
        ### Post-Deployment
        1. Verify the initiative appears in Policy Definitions
        2. Assign the initiative to your subscription, resource groups, or management groups
        3. Configure assignment parameters as needed
        4. Monitor compliance in the Azure Policy compliance dashboard
        
        ### Troubleshooting
        - **Policy not found**: Ensure all referenced policies exist in your tenant
        - **Parameter errors**: Check parameter types match policy definitions
        - **Permission denied**: Verify you have appropriate RBAC roles
        
        ### Additional Resources
        - [Azure Policy documentation](https://learn.microsoft.com/azure/governance/policy/)
        - [Policy assignment tutorial](https://learn.microsoft.com/azure/governance/policy/assign-policy-portal)
        - [Compliance monitoring](https://learn.microsoft.com/azure/governance/policy/how-to/get-compliance-data)
        """)
    
    # Download all as ZIP
    st.markdown("---")
    st.markdown("### 📦 Download Complete Package")
    
    import io
    import zipfile
    
    # Create ZIP file
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add JSON
        zip_file.writestr(
            f"{st.session_state.framework_name.replace(' ', '_')}_initiative.json",
            initiative_json
        )
        
        # Add PowerShell script
        zip_file.writestr(
            f"Deploy-{st.session_state.framework_name.replace(' ', '_')}Initiative.ps1",
            powershell_script
        )
        
        # Add Bicep template
        zip_file.writestr(
            f"{st.session_state.framework_name.replace(' ', '_')}_initiative.bicep",
            bicep_template
        )
        
        # Add mappings JSON
        zip_file.writestr(
            f"{st.session_state.framework_name.replace(' ', '_')}_mappings.json",
            json.dumps(filtered_mappings, indent=2)
        )
        
        # Add README
        readme_content = f"""# {initiative_name}

## Overview
This package contains the Azure Policy Initiative for {st.session_state.framework_name} compliance.

## Contents
- `*_initiative.json`: Azure Policy Initiative definition
- `Deploy-*_Initiative.ps1`: PowerShell deployment script
- `*_initiative.bicep`: Bicep IaC template
- `*_mappings.json`: Control mappings used to generate the initiative

## Statistics
- Framework: {st.session_state.framework_name}
- Total Mappings: {len(filtered_mappings)}
- Average Confidence: {avg_confidence:.0%}
- Unique MCSB Controls: {unique_mcsb}

## Quick Start
1. Review the mappings in `*_mappings.json`
2. Choose a deployment method (Portal, PowerShell, CLI, or Bicep)
3. Follow the deployment guide in the frontend application
4. Assign the initiative to your desired scope
5. Monitor compliance in Azure Portal

## Support
For questions or issues, refer to Azure Policy documentation:
https://learn.microsoft.com/azure/governance/policy/

Generated by: AI Control Mapping Agent
Generated on: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        zip_file.writestr("README.md", readme_content)
    
    zip_buffer.seek(0)
    
    st.download_button(
        label="📦 Download Complete Package (ZIP)",
        data=zip_buffer,
        file_name=f"{st.session_state.framework_name.replace(' ', '_')}_policy_package.zip",
        mime="application/zip",
        type="primary"
    )
    
    st.success("✅ Package includes: JSON, PowerShell, Bicep, Mappings, and README")

# Action buttons
st.markdown("---")

col_action1, col_action2, col_action3 = st.columns(3)

with col_action1:
    if st.button("← Back to Review", use_container_width=True):
        st.switch_page("pages/3_✏️_Review_Edit.py")

with col_action2:
    if st.button("🔄 Start New Mapping", use_container_width=True):
        # Clear session state
        st.session_state.controls = []
        st.session_state.mappings = []
        st.session_state.framework_name = ""
        st.session_state.generated_policy = None
        st.switch_page("pages/1_📁_Upload_Controls.py")

with col_action3:
    if st.button("🏠 Go to Home", use_container_width=True):
        st.switch_page("app.py")

# Sidebar
with st.sidebar:
    st.markdown("### 📦 Export Status")
    
    if st.session_state.generated_policy:
        st.success("✅ Policy generated")
    else:
        st.info("⏳ Ready to generate")
    
    st.metric("Mappings to Export", len(filtered_mappings))
    
    st.markdown("---")
    
    st.markdown("### 💡 Tips")
    st.markdown("""
    - Adjust confidence threshold
    - Review JSON before deployment
    - Test in non-prod first
    - Use Bicep for IaC
    - Keep mappings for reference
    """)
    
    st.markdown("---")
    
    st.markdown("### 📋 Deployment Methods")
    st.markdown("""
    1. **Portal**: Manual upload
    2. **PowerShell**: Automated script
    3. **Azure CLI**: Command line
    4. **Bicep**: Infrastructure as Code
    """)

# Add pandas import
import pandas as pd
