"""
Upload Controls Page - Import compliance framework controls.
"""

import streamlit as st
import pandas as pd
import io
from typing import Optional, List, Dict
from utils.theme import inject_azure_theme, render_sidebar, render_footer

st.set_page_config(
    page_title="Upload Controls | ComplianceIQ",
    page_icon="🛡️",
    layout="wide"
)

inject_azure_theme()
render_sidebar()

# Initialize session state
if 'controls' not in st.session_state:
    st.session_state.controls = []
if 'framework_name' not in st.session_state:
    st.session_state.framework_name = ""
if 'uploaded_df' not in st.session_state:
    st.session_state.uploaded_df = None
if 'controls_loaded' not in st.session_state:
    st.session_state.controls_loaded = False
for key in ["control_id_col", "control_name_col", "description_col", "domain_col"]:
    if key not in st.session_state:
        st.session_state[key] = ""

# Header
st.title("📁 Upload Framework Controls")
st.markdown("Import your compliance framework controls from CSV or Excel files.")

st.markdown("---")

# Instructions
with st.expander("📋 File Format Requirements", expanded=True):
    st.markdown("""
    ### Required Columns
    
    Your file must contain at least these columns:
    - **Control ID**: Unique identifier (e.g., SAMA-AC-01, CCC-1.1)
    - **Control Name**: Short name or title
    - **Description**: Detailed control description
    - **Domain** (optional): Control category or domain
    
    ### Supported Formats
    - CSV (.csv)
    - Excel (.xlsx, .xls)
    
    ### Example Structure
    
    | Control ID | Control Name | Description | Domain |
    |------------|--------------|-------------|---------|
    | SAMA-AC-01 | Multi-Factor Authentication | Enforce MFA for all users | Access Control |
    | SAMA-NS-01 | Network Segmentation | Implement network segmentation | Network Security |
    """)

# File upload section
st.markdown("### 1️⃣ Upload Your File")

uploaded_file = st.file_uploader(
    "Choose a CSV or Excel file",
    type=['csv', 'xlsx', 'xls'],
    help="Upload your compliance framework controls file"
)

if uploaded_file is not None:
    try:
        # Read file based on type
        if uploaded_file.name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file)
            except pd.errors.ParserError:
                # Retry with flexible parsing for CSVs with inconsistent fields
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, on_bad_lines='warn', engine='python')
        else:
            df = pd.read_excel(uploaded_file)
        
        st.session_state.uploaded_df = df
        st.success(f"✅ File loaded successfully: **{uploaded_file.name}**")
        st.info(f"📊 Found {len(df)} rows and {len(df.columns)} columns")
        
        # Auto-detect columns on first upload (when no columns are mapped yet)
        if not any([st.session_state.control_id_col, st.session_state.control_name_col,
                     st.session_state.description_col, st.session_state.domain_col]):
            for col in df.columns:
                col_lower = col.lower()
                if 'id' in col_lower and not st.session_state.control_id_col:
                    st.session_state.control_id_col = col
                elif 'name' in col_lower and not st.session_state.control_name_col:
                    st.session_state.control_name_col = col
                elif ('description' in col_lower or 'desc' in col_lower) and not st.session_state.description_col:
                    st.session_state.description_col = col
                elif ('domain' in col_lower or 'category' in col_lower) and not st.session_state.domain_col:
                    st.session_state.domain_col = col
        
        # Column mapping section
        st.markdown("### 2️⃣ Map Columns")
        st.markdown("Match your file columns to the required fields:")
        
        col1, col2, col3, col4 = st.columns(4)
        
        available_columns = [''] + list(df.columns)

        def _index_for(value: str) -> int:
            return available_columns.index(value) if value in available_columns else 0
        
        with col1:
            control_id_col = st.selectbox(
                "Control ID *",
                options=available_columns,
                index=_index_for(st.session_state.control_id_col),
                help="Column containing unique control identifiers"
            )
        
        with col2:
            control_name_col = st.selectbox(
                "Control Name *",
                options=available_columns,
                index=_index_for(st.session_state.control_name_col),
                help="Column containing control names/titles"
            )
        
        with col3:
            description_col = st.selectbox(
                "Description *",
                options=available_columns,
                index=_index_for(st.session_state.description_col),
                help="Column containing detailed descriptions"
            )
        
        with col4:
            domain_col = st.selectbox(
                "Domain (optional)",
                options=available_columns,
                index=_index_for(st.session_state.domain_col),
                help="Column containing control domains/categories"
            )

        # Persist current selections
        st.session_state.control_id_col = control_id_col
        st.session_state.control_name_col = control_name_col
        st.session_state.description_col = description_col
        st.session_state.domain_col = domain_col
        
        # Auto-detect columns
        if st.button("🔍 Auto-Detect Columns"):
            # Simple heuristic matching
            for col in df.columns:
                col_lower = col.lower()
                if 'id' in col_lower and not st.session_state.control_id_col:
                    st.session_state.control_id_col = col
                elif 'name' in col_lower and not st.session_state.control_name_col:
                    st.session_state.control_name_col = col
                elif ('description' in col_lower or 'desc' in col_lower) and not st.session_state.description_col:
                    st.session_state.description_col = col
                elif ('domain' in col_lower or 'category' in col_lower) and not st.session_state.domain_col:
                    st.session_state.domain_col = col
            st.rerun()
        
        # Validation
        required_fields_mapped = all([control_id_col, control_name_col, description_col])
        
        if required_fields_mapped:
            st.success("✅ All required fields mapped!")
            
            # Preview section
            st.markdown("### 3️⃣ Preview Controls")
            
            # Create preview dataframe
            preview_df = pd.DataFrame({
                'Control ID': df[control_id_col],
                'Control Name': df[control_name_col],
                'Description': df[description_col],
            })
            
            if domain_col:
                preview_df['Domain'] = df[domain_col]
            
            # Show preview
            st.dataframe(
                preview_df.head(10),
                use_container_width=True,
                hide_index=True
            )
            
            if len(df) > 10:
                st.caption(f"Showing first 10 of {len(df)} controls")
            
            # Framework name input
            st.markdown("### 4️⃣ Framework Information")
            
            framework_name = st.text_input(
                "Framework Name *",
                value=st.session_state.framework_name,
                placeholder="e.g., SAMA Cybersecurity Framework",
                help="Enter a descriptive name for this framework"
            )
            
            # Load controls button
            st.markdown("### 5️⃣ Load Controls")
            
            col_load, col_clear = st.columns([1, 1])
            
            with col_load:
                if st.button("✅ Load Controls", type="primary", use_container_width=True):
                    if not framework_name:
                        st.error("❌ Please enter a framework name")
                    else:
                        # Convert to list of dicts
                        controls = []
                        for _, row in df.iterrows():
                            control = {
                                'control_id': str(row[control_id_col]),
                                'control_name': str(row[control_name_col]),
                                'description': str(row[description_col]),
                            }
                            if domain_col:
                                control['domain'] = str(row[domain_col])
                            else:
                                control['domain'] = None
                            controls.append(control)
                        
                        # Save to session state
                        st.session_state.controls = controls
                        st.session_state.framework_name = framework_name
                        st.session_state.mappings = []  # Reset mappings
                        
                        st.session_state.controls_loaded = True
                        st.success(f"✅ Loaded {len(controls)} controls from **{framework_name}**")
                        st.balloons()
            
            with col_clear:
                if st.button("🗑️ Clear Upload", use_container_width=True):
                    st.session_state.uploaded_df = None
                    st.session_state.controls = []
                    st.session_state.controls_loaded = False
                    st.session_state.framework_name = ""
                    st.rerun()
            
            # Show navigation after controls are loaded (persists across reruns)
            if st.session_state.get('controls_loaded') and st.session_state.controls:
                st.markdown("---")
                st.info("👉 Go to **AI Mapping** to start mapping these controls to MCSB")
                if st.button("Continue to AI Mapping →", type="primary"):
                    st.switch_page("pages/2_🤖_AI_Mapping.py")
        
        else:
            st.warning("⚠️ Please map all required fields (marked with *)")
    
    except Exception as e:
        st.error(f"❌ Error reading file: {str(e)}")
        st.exception(e)

else:
    # Show example when no file uploaded
    st.info("👆 Upload a file to get started")
    
    # Sample data button
    if st.button("📝 Load Sample Data"):
        sample_data = {
            'Control ID': [
                'SAMA-AC-01',
                'SAMA-AC-02',
                'SAMA-NS-01',
                'SAMA-DP-01',
                'SAMA-IM-01'
            ],
            'Control Name': [
                'Multi-Factor Authentication',
                'Privileged Access Management',
                'Network Segmentation',
                'Data Encryption at Rest',
                'Security Incident Response'
            ],
            'Description': [
                'Enforce multi-factor authentication for all user accounts accessing critical systems',
                'Implement privileged access management with just-in-time access and approval workflows',
                'Implement network segmentation to isolate critical assets and reduce attack surface',
                'Encrypt all sensitive data at rest using industry-standard encryption algorithms',
                'Establish and maintain an incident response plan with defined procedures and roles'
            ],
            'Domain': [
                'Access Control',
                'Access Control',
                'Network Security',
                'Data Protection',
                'Incident Management'
            ]
        }
        
        df = pd.DataFrame(sample_data)
        st.session_state.uploaded_df = df
        st.rerun()

# Sidebar
with st.sidebar:
    st.markdown("### 📊 Upload Status")
    
    if st.session_state.controls:
        st.success(f"✅ {len(st.session_state.controls)} controls loaded")
        st.info(f"**Framework:** {st.session_state.framework_name}")
        
        if st.button("View Loaded Controls"):
            st.dataframe(pd.DataFrame(st.session_state.controls))
    else:
        st.warning("No controls loaded yet")
    
    st.markdown("---")
    
    st.markdown("### 💡 Tips")
    st.markdown("""
    - Use consistent Control ID format
    - Keep descriptions concise but detailed
    - Include domain/category for better mapping
    - Remove empty rows before upload
    """)
    
    st.markdown("---")
    
    if st.button("🏠 Back to Home"):
        st.switch_page("app.py")
