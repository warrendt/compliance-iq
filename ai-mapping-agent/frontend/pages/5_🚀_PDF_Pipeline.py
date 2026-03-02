"""
Page 5: PDF Upload — Extract controls from a compliance PDF and load into the mapping flow.
The user uploads a PDF, AI extracts the controls, user reviews/edits, then loads into Pages 2→3→4.
"""

import os
import pandas as pd
import streamlit as st
from utils.api_client import APIClient
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from components.log_viewer import render_log_viewer

st.set_page_config(
    page_title="PDF Pipeline | ComplianceIQ",
    page_icon="🛡️",
    layout="wide",
)

inject_azure_theme()
render_sidebar()

# ── Session state init ────────────────────────────────────────────────────
if "controls" not in st.session_state:
    st.session_state.controls = []
if "framework_name" not in st.session_state:
    st.session_state.framework_name = ""
if "controls_loaded" not in st.session_state:
    st.session_state.controls_loaded = False
if "pdf_extraction" not in st.session_state:
    st.session_state.pdf_extraction = None

# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📊 Session Status")
    if st.session_state.controls:
        st.success(f"✅ {len(st.session_state.controls)} controls loaded")
        st.caption(f"Framework: {st.session_state.framework_name}")
        if st.session_state.get("upload_source"):
            st.caption(f"Source: {st.session_state.upload_source}")
    else:
        st.info("No controls loaded yet")

    api_url = st.text_input(
        "Backend API URL",
        value=os.getenv("BACKEND_URL", "http://localhost:8000"),
        help="URL of the ComplianceIQ backend API",
    )

# ── Main content ──────────────────────────────────────────────────────────
st.title("📄 PDF Control Extraction")
st.markdown("""
Upload a compliance framework PDF and AI will extract all controls automatically.
After review, load them into the **Map → Review → Export** flow.
""")

st.divider()

# ── Step 1: Upload PDF ───────────────────────────────────────────────────
st.markdown("### 1️⃣ Upload Compliance PDF")

uploaded_file = st.file_uploader(
    "Choose a compliance control PDF",
    type=["pdf"],
    help="Upload the regulatory framework PDF (e.g., SAMA, ADHICS, Oman CDC, NCA, CCC)",
)

if uploaded_file:
    file_size = len(uploaded_file.getvalue())
    st.success(f"✅ **{uploaded_file.name}** ({file_size:,} bytes)")

    # ── Step 2: Extract controls ──────────────────────────────────────
    st.markdown("### 2️⃣ Extract Controls")

    extract_button = st.button(
        "🔍 Extract Controls from PDF",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.pdf_extraction is not None,
    )

    if extract_button:
        client = APIClient(base_url=api_url)

        with st.spinner("🤖 AI is reading the PDF and extracting controls... This may take a minute."):
            try:
                result = client.extract_controls_from_pdf(
                    pdf_bytes=uploaded_file.getvalue(),
                    filename=uploaded_file.name,
                )
                st.session_state.pdf_extraction = result
                st.rerun()
            except Exception as e:
                st.error(f"❌ Extraction failed: {e}")

    # ── Step 3: Preview & edit extracted controls ─────────────────────
    extraction = st.session_state.pdf_extraction
    if extraction:
        st.markdown("### 3️⃣ Review Extracted Controls")

        # Framework metadata
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Framework", extraction.get("framework_name", "Unknown"))
        with col2:
            st.metric("Controls Found", extraction.get("total_controls", 0))
        with col3:
            st.metric("Version", extraction.get("framework_version") or "—")
        with col4:
            st.metric("Region", extraction.get("country_or_region") or "—")

        controls = extraction.get("controls", [])
        if controls:
            # Convert to DataFrame for editing
            df = pd.DataFrame(controls)

            # Show editable table
            edited_df = st.data_editor(
                df,
                num_rows="dynamic",
                use_container_width=True,
                key="pdf_controls_editor",
                column_config={
                    "control_id": st.column_config.TextColumn("Control ID", width="small"),
                    "control_name": st.column_config.TextColumn("Control Name", width="medium"),
                    "description": st.column_config.TextColumn("Description", width="large"),
                    "domain": st.column_config.TextColumn("Domain", width="medium"),
                    "control_type": st.column_config.TextColumn("Type", width="small"),
                    "requirements": st.column_config.TextColumn("Requirements", width="medium"),
                },
            )

            st.caption(f"📝 {len(edited_df)} controls — edit, add, or remove rows as needed")

            # ── Step 4: Framework name & load ─────────────────────────
            st.markdown("### 4️⃣ Confirm & Load Controls")

            framework_name = st.text_input(
                "Framework Name *",
                value=extraction.get("framework_name", ""),
                placeholder="e.g., SAMA Cybersecurity Framework",
                help="Confirm or edit the framework name",
            )

            col_load, col_clear = st.columns([1, 1])

            with col_load:
                if st.button("✅ Load Controls into Mapping Flow", type="primary", use_container_width=True):
                    if not framework_name:
                        st.error("❌ Please enter a framework name")
                    elif len(edited_df) == 0:
                        st.error("❌ No controls to load")
                    else:
                        # Convert edited DataFrame to list of dicts
                        loaded_controls = []
                        for _, row in edited_df.iterrows():
                            control = {
                                "control_id": str(row.get("control_id", "")),
                                "control_name": str(row.get("control_name", "")),
                                "description": str(row.get("description", "")),
                                "domain": str(row.get("domain", "")) if pd.notna(row.get("domain")) else None,
                                "control_type": str(row.get("control_type", "")) if pd.notna(row.get("control_type")) else None,
                            }
                            loaded_controls.append(control)

                        # Save to session state — same format as CSV upload (Page 1)
                        st.session_state.controls = loaded_controls
                        st.session_state.framework_name = framework_name
                        st.session_state.mappings = []  # Reset any previous mappings
                        st.session_state.controls_loaded = True
                        st.session_state.upload_source = "pdf"

                        st.success(f"✅ Loaded {len(loaded_controls)} controls from **{framework_name}**")
                        st.balloons()

                        st.markdown("---")
                        st.markdown("### ➡️ Next Steps")
                        st.info(
                            "Controls are loaded! Navigate to **🤖 AI Mapping** (Page 2) "
                            "to map them to Azure policies, then **Review** and **Export**."
                        )

            with col_clear:
                if st.button("🗑️ Clear & Start Over", use_container_width=True):
                    st.session_state.pdf_extraction = None
                    st.rerun()
        else:
            st.warning("No controls were extracted from the PDF. The document may not contain structured controls.")

else:
    # ── Instructions when no file is uploaded ─────────────────────────
    st.info("👆 Upload a compliance control PDF to get started")

    with st.expander("📋 Supported frameworks"):
        st.markdown("""
        - **SAMA** — Saudi Arabian Monetary Authority Cybersecurity Framework
        - **NCA** — National Cybersecurity Authority (Saudi Arabia)
        - **NDMO** — National Data Management Office (Saudi Arabia)
        - **ADHICS** — Abu Dhabi Health Information & Cyber Security Standard
        - **Oman CDC** — Cyber Defense Centre Cloud Security Controls
        - **CCC** — Cloud Computing Controls (Dubai)
        - **POPIA** — Protection of Personal Information Act (South Africa)
        - **SITA** — State Information Technology Agency (South Africa)
        - Any other regulatory/compliance framework PDF
        """)

    with st.expander("ℹ️ How it works"):
        st.markdown("""
        1. **Upload** — Your PDF is sent to the backend
        2. **Extract** — pypdf extracts the text, then Azure OpenAI (GPT-4.1) identifies every control
        3. **Review** — You see all extracted controls in an editable table
        4. **Load** — Click to load controls into the mapping flow
        5. **Map → Review → Export** — Continue through Pages 2, 3, and 4 as normal
        """)

render_log_viewer()
