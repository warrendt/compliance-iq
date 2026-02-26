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
st.markdown("Generate and download Azure Policy initiatives — MCSB and Sovereign Landing Zone")

st.markdown("---")

# Check if mappings exist
if not st.session_state.mappings:
    st.warning("⚠️ No mappings to export. Please complete the mapping and review steps first.")
    if st.button("Go to AI Mapping"):
        st.switch_page("pages/2_🤖_AI_Mapping.py")
    st.stop()

# Determine sovereignty status
sov_mappings = [m for m in st.session_state.mappings if m.get('sovereignty')]
has_sovereignty = len(sov_mappings) > 0

# Get API client (used by both MCSB and SLZ export)
api_client = get_api_client()

# Display mapping summary
col1, col2, col3, col4, col5 = st.columns(5)

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

with col5:
    st.metric("Sovereignty Mapped", len(sov_mappings))

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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Initiative JSON", "🔧 PowerShell Script", "📊 Bicep Template", "📖 Deployment Guide", "🔍 Policy Details"])
    
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
    
    with tab5:
        st.markdown("#### Azure Policy Details")
        st.markdown("Enriched policy information from the cache (Microsoft Learn backed)")

        # Collect all unique policy GUIDs from filtered mappings
        _all_pids = set()
        for m in filtered_mappings:
            for pid in m.get("azure_policy_ids", []):
                _all_pids.add(pid)
        _all_pids = sorted(_all_pids)

        if _all_pids:
            if "_export_policy_details" not in st.session_state:
                try:
                    st.session_state._export_policy_details = api_client.get_policy_details(_all_pids).get("policies", {})
                except Exception:
                    st.session_state._export_policy_details = {}
            _pd_map = st.session_state._export_policy_details

            import pandas as _pd_lib
            _rows = []
            for pid in _all_pids:
                d = _pd_map.get(pid, {})
                _rows.append({
                    "Policy ID": pid,
                    "Display Name": d.get("display_name", "—"),
                    "Description": d.get("description", "")[:120],
                    "Learn URL": d.get("learn_url", ""),
                })
            st.dataframe(_pd_lib.DataFrame(_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No Azure Policy GUIDs in the included mappings.")

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

# ==================================================================
# SLZ Sovereign Landing Zone Export
# ==================================================================
st.markdown("---")
st.markdown("## 🏛️ Sovereign Landing Zone Export")

if not has_sovereignty:
    st.info(
        "No sovereignty data found in current mappings. "
        "Re-run AI mapping to generate sovereignty assignments."
    )
else:
    st.success(f"**{len(sov_mappings)}** of **{len(st.session_state.mappings)}** mappings have sovereignty data")

    # SLZ configuration
    col_slz1, col_slz2 = st.columns(2)

    with col_slz1:
        slz_allowed_locations = st.text_input(
            "Allowed Locations (comma-separated)",
            value="uaenorth,uaecentral",
            help="Azure regions for data-residency policies (e.g. uaenorth,uaecentral)"
        )
        locations_list = [loc.strip() for loc in slz_allowed_locations.split(",") if loc.strip()] if slz_allowed_locations else None

    with col_slz2:
        slz_min_confidence = st.slider(
            "Min Confidence for SLZ export",
            min_value=0.0, max_value=1.0, value=0.6, step=0.05,
            help="Only include SLZ mappings with confidence >= this value"
        )

    # Filter sovereignty mappings by confidence
    slz_export_mappings = [
        m for m in sov_mappings
        if m.get('confidence_score', 0) >= slz_min_confidence
    ]

    # Level breakdown
    level_counts = {'L1': 0, 'L2': 0, 'L3': 0}
    for m in slz_export_mappings:
        lvl = m['sovereignty'].get('sovereignty_level', '')
        if lvl in level_counts:
            level_counts[lvl] += 1

    col_l1, col_l2, col_l3 = st.columns(3)
    with col_l1:
        st.metric("🟢 L1 — Global", level_counts['L1'])
    with col_l2:
        st.metric("🟡 L2 — CMK", level_counts['L2'])
    with col_l3:
        st.metric("🔴 L3 — Confidential", level_counts['L3'])

    st.info(f"📋 Will generate SLZ initiatives for **{len(slz_export_mappings)}** sovereignty-mapped controls")

    # Generate SLZ initiatives
    if 'slz_generated' not in st.session_state:
        st.session_state.slz_generated = None

    if st.button("🏛️ Generate SLZ Initiatives", type="primary", use_container_width=True):
        with st.spinner("Generating per-archetype SLZ policy initiatives..."):
            try:
                slz_result = api_client.generate_slz_initiatives(
                    mappings=slz_export_mappings,
                    framework_name=st.session_state.framework_name,
                    allowed_locations=locations_list,
                )
                st.session_state.slz_generated = slz_result
                st.success("✅ SLZ initiatives generated!")
                st.balloons()
            except httpx.ConnectError:
                st.error("❌ Cannot connect to backend.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

    # Display generated SLZ artifacts
    if st.session_state.slz_generated:
        slz_data = st.session_state.slz_generated
        archetypes = slz_data.get('archetypes', {})

        st.markdown("### 📦 SLZ Archetype Artifacts")
        st.caption(
            f"Framework: **{slz_data.get('framework_name')}** | "
            f"Sovereignty mappings: **{slz_data.get('sovereignty_mappings', 0)}**"
        )

        archetype_tabs = st.tabs([f"🏗️ {name}" for name in archetypes.keys()])

        for tab, (arch_name, arch_data) in zip(archetype_tabs, archetypes.items()):
            with tab:
                st.markdown(f"#### {arch_name}")
                st.caption(f"Policies included: **{arch_data.get('policy_count', 'N/A')}**")

                sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
                    "📋 Initiative JSON", "🔧 Bicep Template", "💻 CLI Script", "💠 PowerShell"
                ])

                with sub_tab1:
                    initiative_json_str = json.dumps(arch_data.get('initiative_json', {}), indent=2)
                    st.code(initiative_json_str, language="json", line_numbers=True)
                    st.download_button(
                        label=f"📥 Download {arch_name} Initiative JSON",
                        data=initiative_json_str,
                        file_name=f"slz_{arch_name}_initiative.json",
                        mime="application/json",
                        key=f"dl_slz_json_{arch_name}"
                    )

                with sub_tab2:
                    bicep_content = arch_data.get('bicep', '// No Bicep generated')
                    st.code(bicep_content, language="bicep", line_numbers=True)
                    st.download_button(
                        label=f"📥 Download {arch_name} Bicep",
                        data=bicep_content,
                        file_name=f"slz_{arch_name}_initiative.bicep",
                        mime="text/plain",
                        key=f"dl_slz_bicep_{arch_name}"
                    )

                with sub_tab3:
                    cli_script = (arch_data.get('scripts') or {}).get('cli', '# No CLI script')
                    st.code(cli_script, language="bash", line_numbers=True)
                    st.download_button(
                        label=f"📥 Download {arch_name} CLI Script",
                        data=cli_script,
                        file_name=f"deploy_slz_{arch_name}.sh",
                        mime="text/plain",
                        key=f"dl_slz_cli_{arch_name}"
                    )

                with sub_tab4:
                    ps_script = (arch_data.get('scripts') or {}).get('powershell', '# No PowerShell script')
                    st.code(ps_script, language="powershell", line_numbers=True)
                    st.download_button(
                        label=f"📥 Download {arch_name} PowerShell",
                        data=ps_script,
                        file_name=f"Deploy-SLZ-{arch_name}.ps1",
                        mime="text/plain",
                        key=f"dl_slz_ps_{arch_name}"
                    )

        # Download all SLZ artifacts as ZIP
        st.markdown("---")
        st.markdown("### 📦 Download Complete SLZ Package")

        slz_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(slz_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for arch_name, arch_data in archetypes.items():
                prefix = f"slz_{arch_name}"
                zf.writestr(
                    f"{prefix}/{prefix}_initiative.json",
                    json.dumps(arch_data.get('initiative_json', {}), indent=2)
                )
                zf.writestr(
                    f"{prefix}/{prefix}_initiative.bicep",
                    arch_data.get('bicep', '')
                )
                scripts = arch_data.get('scripts') or {}
                zf.writestr(
                    f"{prefix}/deploy_{arch_name}.sh",
                    scripts.get('cli', '')
                )
                zf.writestr(
                    f"{prefix}/Deploy-SLZ-{arch_name}.ps1",
                    scripts.get('powershell', '')
                )

            # Add SLZ README
            slz_readme = f"""# Sovereign Landing Zone Policy Package
## {st.session_state.framework_name}

### Archetypes Generated
{chr(10).join(f'- **{name}**: {data.get("policy_count", 0)} policies' for name, data in archetypes.items())}

### Sovereignty Levels
- **L1 (Global)**: Data residency & trusted launch — {level_counts['L1']} controls
- **L2 (CMK)**: Customer-managed keys — {level_counts['L2']} controls
- **L3 (Confidential)**: Confidential computing — {level_counts['L3']} controls

### Deployment
Each archetype folder contains:
1. `*_initiative.json` — Policy initiative definition
2. `*_initiative.bicep` — Bicep template (management-group scope)
3. `deploy_*.sh` — Azure CLI deployment script
4. `Deploy-SLZ-*.ps1` — PowerShell deployment script

Target these at the appropriate management group in your SLZ hierarchy.

### Allowed Locations
{', '.join(locations_list) if locations_list else 'Not specified'}

Generated by: AI Control Mapping Agent — SLZ Module
"""
            zf.writestr("README.md", slz_readme)

        slz_zip_buffer.seek(0)

        st.download_button(
            label="📦 Download Complete SLZ Package (ZIP)",
            data=slz_zip_buffer,
            file_name=f"{st.session_state.framework_name.replace(' ', '_')}_slz_package.zip",
            mime="application/zip",
            type="primary",
            key="dl_slz_zip_all"
        )
        st.success("✅ SLZ package: per-archetype JSON, Bicep, CLI & PowerShell scripts")

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
    
    st.markdown("---")
    
    st.markdown("### 🏛️ SLZ Status")
    if has_sovereignty:
        st.success(f"✅ {len(sov_mappings)} sovereignty mappings")
        if st.session_state.get('slz_generated'):
            st.success("✅ SLZ initiatives generated")
        else:
            st.info("⏳ Ready to generate SLZ")
    else:
        st.caption("No sovereignty data")

# Add pandas import
import pandas as pd
