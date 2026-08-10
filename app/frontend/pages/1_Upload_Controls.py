"""
Upload Controls Page - Import compliance framework controls.
"""

import streamlit as st
import pandas as pd
import io
from typing import Optional, List, Dict
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.components import render_page_header, render_success_effect
from utils.api_client import get_api_client
from utils.column_mapping import (
    COLUMN_MAPPING_KEYS,
    detect_columns,
    sanitize_selection,
)
from utils.state_init import (
    init_session_state,
    persist_workflow_state,
    restore_workflow_state,
)
from components.task_status_bar import render_task_status_bar
from components.log_viewer import render_log_viewer
from components.backend_log_viewer import render_backend_log_viewer

st.set_page_config(
    page_title="Upload Controls | ComplianceIQ",
    page_icon="🛡️",
    layout="wide"
)

inject_azure_theme()
render_sidebar()
init_session_state()
restore_workflow_state()
render_task_status_bar()
for key in COLUMN_MAPPING_KEYS:
    if key not in st.session_state:
        st.session_state[key] = ""


def clear_upload_state() -> None:
    """Reset the uploaded file, its column mapping, and any loaded controls.

    Runs as a widget callback so the column-mapping selectbox keys can be
    reassigned before their widgets are re-instantiated on the next run.
    """
    st.session_state.uploaded_df = None
    st.session_state.controls = []
    st.session_state.controls_loaded = False
    st.session_state.framework_name = ""
    st.session_state.pop("upload_source", None)
    for key in COLUMN_MAPPING_KEYS:
        st.session_state[key] = ""
    # Force the file_uploader to drop its selection.
    st.session_state["controls_upload_key"] = st.session_state.get("controls_upload_key", 0) + 1
    try:
        persist_workflow_state()
    except Exception:
        pass


# Header
render_page_header(
    "Upload framework controls",
    eyebrow="Govern",
    description="Import your compliance framework controls from CSV or Excel files.",
)

st.markdown("---")

if notice := st.session_state.pop("workflow_restored_notice", None):
    st.success(f"🔄 {notice}")

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
    """)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Control ID": "SAMA-AC-01",
                    "Control Name": "Multi-Factor Authentication",
                    "Description": "Enforce MFA for all users",
                    "Domain": "Access Control",
                },
                {
                    "Control ID": "SAMA-NS-01",
                    "Control Name": "Network Segmentation",
                    "Description": "Implement network segmentation",
                    "Domain": "Network Security",
                },
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

# File upload section
st.markdown("### 1️⃣ Upload Your File")

uploaded_file = st.file_uploader(
    "Choose a CSV or Excel file",
    type=['csv', 'xlsx', 'xls'],
    help="Upload your compliance framework controls file",
    key=f"controls_uploader_{st.session_state.get('controls_upload_key', 0)}",
)

# Support both freshly uploaded files and sample data already in session state.
df: Optional[pd.DataFrame] = None
read_error: Optional[Exception] = None

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file)
            except pd.errors.ParserError:
                # Retry with flexible parsing for CSVs with inconsistent fields
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, on_bad_lines='warn', engine='python')
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as exc:  # noqa: BLE001 — surfaced to the user below
        read_error = exc
    else:
        st.session_state.uploaded_df = df
        st.success(f"✅ File loaded successfully: **{uploaded_file.name}**")
elif st.session_state.get("uploaded_df") is not None:
    df = st.session_state.uploaded_df
    st.info("✅ Using sample data from session")

# Rendering happens outside the try/except above. Streamlit signals reruns and
# page switches by raising, so control-flow calls such as st.rerun() must never
# sit inside a broad ``except Exception`` or they surface as a fake
# "Error reading file: RerunData(...)" traceback.
if read_error is not None:
    st.error(f"❌ Error reading file: {read_error}")
    st.exception(read_error)

elif df is not None:
    st.info(f"📊 Found {len(df)} rows and {len(df.columns)} columns")

    available_columns = [''] + [str(c) for c in df.columns]

    # Drop stale selections that refer to a previously uploaded file's columns,
    # otherwise Streamlit raises when the widget value is not among its options.
    for _key in COLUMN_MAPPING_KEYS:
        st.session_state[_key] = sanitize_selection(
            st.session_state.get(_key, ""), available_columns
        )

    # Auto-detect on first sight of a file (when nothing is mapped yet).
    if not any(st.session_state[key] for key in COLUMN_MAPPING_KEYS):
        for key, value in detect_columns(df.columns).items():
            st.session_state[key] = value

    def _auto_detect_columns() -> None:
        """Re-run detection over every field, overriding current choices.

        Runs as a widget callback (before the next script run) so the selectbox
        values can be reassigned safely and no explicit st.rerun() is needed.
        """
        detected = detect_columns(df.columns)
        for key, value in detected.items():
            st.session_state[key] = value
        st.session_state["column_autodetect_notice"] = sum(
            1 for value in detected.values() if value
        )

    # Column mapping section
    st.markdown("### 2️⃣ Map Columns")
    st.markdown("Match your file columns to the required fields:")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        control_id_col = st.selectbox(
            "Control ID *",
            options=available_columns,
            key="control_id_col",
            help="Column containing unique control identifiers"
        )

    with col2:
        control_name_col = st.selectbox(
            "Control Name *",
            options=available_columns,
            key="control_name_col",
            help="Column containing control names/titles"
        )

    with col3:
        description_col = st.selectbox(
            "Description *",
            options=available_columns,
            key="description_col",
            help="Column containing detailed descriptions"
        )

    with col4:
        domain_col = st.selectbox(
            "Domain (optional)",
            options=available_columns,
            key="domain_col",
            help="Column containing control domains/categories"
        )

    st.button("🔍 Auto-Detect Columns", on_click=_auto_detect_columns)

    if (detected_count := st.session_state.pop("column_autodetect_notice", None)) is not None:
        if detected_count:
            st.success(f"✅ Auto-detected {detected_count} column(s)")
        else:
            st.warning("⚠️ Could not auto-detect any columns — please map them manually")

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
                    st.session_state.upload_source = "csv"

                    st.session_state.controls_loaded = True
                    try:
                        persist_workflow_state()
                    except Exception as exc:
                        st.warning(
                            f"Controls are loaded, but could not be saved for recovery: {exc}"
                        )
                    st.success(f"✅ Loaded {len(controls)} controls from **{framework_name}**")
                    render_success_effect(f"Loaded {len(controls)} controls")

                    # Record the loaded control set to the user's workspace
                    # (best-effort; keeps the per-tenant control library + audit).
                    try:
                        get_api_client().record_upload(
                            file_name=(
                                uploaded_file.name
                                if uploaded_file is not None
                                else f"{framework_name}.csv"
                            ),
                            file_type="text/csv",
                            category="controls",
                            row_count=len(controls),
                            column_names=list(df.columns.astype(str)),
                            controls=controls,
                            metadata={"framework": framework_name},
                        )
                    except Exception:
                        pass  # activity logging is best-effort

        with col_clear:
            st.button(
                "🗑️ Clear Upload",
                use_container_width=True,
                on_click=clear_upload_state,
            )

        # Show navigation after controls are loaded (persists across reruns)
        if st.session_state.get('controls_loaded') and st.session_state.controls:
            st.markdown("---")
            st.info("👉 Go to **AI Mapping** to start mapping these controls to Azure Policy")
            if st.button("Continue to AI Mapping →", type="primary"):
                st.switch_page("pages/2_AI_Mapping.py")

    else:
        st.warning("⚠️ Please map all required fields (marked with *)")

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

render_footer()
render_log_viewer()
render_backend_log_viewer()
