"""
Page 5: PDF Pipeline — Automated PDF to Defender for Cloud Initiative
Upload a compliance PDF and get a ready-to-deploy Azure Policy initiative.
"""

import time
import os
import io
import csv
import streamlit as st
from utils.api_client import APIClient

st.set_page_config(
    page_title="PDF Pipeline — CCToolkit",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 PDF to Defender for Cloud Pipeline")
st.markdown("""
Upload a compliance control PDF and the pipeline will automatically:
1. **Extract** all controls from the document using AI
2. **Map** each control to Azure Policy definitions
3. **Validate** the mappings for correctness
4. **Generate** a deployable initiative for Defender for Cloud
""")

st.divider()

# ── Configuration ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Pipeline Settings")

    min_confidence = st.slider(
        "Minimum Confidence",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.1,
        help="Controls below this confidence will be flagged for review",
    )

    locations_input = st.text_input(
        "Allowed Azure Regions (comma-separated)",
        placeholder="e.g., uaenorth, uaecentral",
        help="Optional: restrict resources to specific Azure regions",
    )

    api_url = st.text_input(
        "Backend API URL",
        value=os.getenv("BACKEND_URL", "http://localhost:8000"),
        help="URL of the CCToolkit backend API",
    )

# ── File Upload ───────────────────────────────────────────────────────────
st.header("📄 Upload Compliance PDF")

uploaded_file = st.file_uploader(
    "Choose a compliance control PDF",
    type=["pdf"],
    help="Upload the regulatory framework PDF (e.g., SAMA, ADHICS, Oman CDC, NCA, NDMO)",
)

if uploaded_file:
    file_size = len(uploaded_file.getvalue())
    st.success(f"✅ **{uploaded_file.name}** ({file_size:,} bytes)")

    col1, col2 = st.columns([1, 3])
    with col1:
        run_button = st.button("🚀 Run Pipeline", type="primary", use_container_width=True)

    if run_button:
        client = APIClient(base_url=api_url)

        # Submit the job
        with st.spinner("Submitting PDF to pipeline..."):
            try:
                locations = locations_input.strip() if locations_input else None

                job = client.run_pipeline(
                    pdf_bytes=uploaded_file.getvalue(),
                    filename=uploaded_file.name,
                    min_confidence=min_confidence,
                    allowed_locations=locations,
                )
                job_id = job["job_id"]
                st.info(f"Pipeline job started: `{job_id}`")

            except Exception as e:
                st.error(f"Failed to submit pipeline job: {e}")
                st.stop()

        # ── Poll for status ───────────────────────────────────────────
        st.header("📊 Pipeline Progress")

        progress_bar = st.progress(0)
        status_text = st.empty()
        stage_container = st.container()

        stages_shown = set()
        completed = False

        while not completed:
            time.sleep(2)

            try:
                status = client.get_pipeline_status(job_id)
            except Exception as e:
                status_text.warning(f"Polling error: {e}")
                continue

            progress = status.get("progress", 0)
            stage = status.get("stage", "")
            job_status = status.get("status", "")

            progress_bar.progress(progress / 100)
            status_text.text(f"[{progress}%] {stage}")

            # Show stage milestones
            if stage and stage not in stages_shown:
                stages_shown.add(stage)
                with stage_container:
                    st.write(f"  ✓ {stage}")

            if job_status == "completed":
                completed = True
                progress_bar.progress(100)
                st.balloons()

            elif job_status == "failed":
                completed = True
                error = status.get("error", "Unknown error")
                st.error(f"❌ Pipeline failed: {error}")
                st.stop()

        # ── Show results ──────────────────────────────────────────────
        st.divider()
        st.header("✅ Pipeline Complete")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Framework", status.get("framework_name", "Unknown"))
        with col2:
            st.metric("Controls Extracted", status.get("controls_extracted", 0))
        with col3:
            st.metric("Controls Mapped", status.get("controls_mapped", 0))
        with col4:
            st.metric("Status", "✅ Valid" if job_status == "completed" else "❌ Failed")

        # ── Download artifacts ────────────────────────────────────────
        st.header("📦 Download Initiative")

        with st.spinner("Preparing download..."):
            try:
                zip_bytes = client.download_pipeline_output(job_id)
                fw_name = status.get("framework_name", "initiative").replace(" ", "_")

                st.download_button(
                    label=f"📥 Download {fw_name}_Initiative.zip",
                    data=zip_bytes,
                    file_name=f"{fw_name}_Initiative.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Failed to download: {e}")

        # ── Review & Edit Mappings ───────────────────────────────────
        st.divider()
        st.header("📝 Review & Edit Mappings")

        with st.spinner("Fetching artifacts for review..."):
            artifacts = None
            try:
                artifacts = client.get_pipeline_artifacts(job_id)
            except Exception as e:
                st.warning(f"Artifacts not available: {e}")

        if artifacts:
            files = artifacts.get("files", {})

            with st.expander("Mappings (edit as needed)", expanded=True):
                mappings = files.get("mappings", [])
                if mappings:
                    edited_rows = st.data_editor(
                        mappings,
                        num_rows="dynamic",
                        use_container_width=True,
                        key="mappings_editor",
                        column_config={
                            "Azure_Policy_IDs": st.column_config.TextColumn(help="Semicolon-separated policy definition IDs"),
                            "Azure_Policy_Names": st.column_config.TextColumn(help="Semicolon-separated policy names"),
                            "Manual_Note": st.column_config.TextColumn(help="Notes for manual attestation"),
                            "Mapping_Rationale": st.column_config.TextColumn(help="Reasoning / justification"),
                        },
                    )

                    def _to_csv(rows):
                        if not rows:
                            return ""
                        fieldnames = rows[0].keys()
                        buf = io.StringIO()
                        writer = csv.DictWriter(buf, fieldnames=fieldnames)
                        writer.writeheader()
                        for r in rows:
                            writer.writerow(r)
                        return buf.getvalue()

                    csv_data = _to_csv(edited_rows)
                    st.download_button(
                        "💾 Download edited mappings CSV",
                        data=csv_data,
                        file_name="Edited_Mappings.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                    st.caption("Note: This exports the edited mappings CSV. Replace the CSV inside the ZIP if you want to deploy with these edits.")

                    repack_col1, repack_col2 = st.columns([1, 2])
                    with repack_col1:
                        repack = st.button("📦 Repack ZIP with edits", use_container_width=True)
                    if repack:
                        if not csv_data.strip():
                            st.warning("Edited mappings CSV is empty; cannot repack.")
                        else:
                            with st.spinner("Repacking ZIP with edited mappings..."):
                                try:
                                    zip_bytes = client.repack_pipeline_output(job_id, csv_data)
                                    st.download_button(
                                        "📥 Download edited initiative ZIP",
                                        data=zip_bytes,
                                        file_name=f"{status.get('framework_name','initiative').replace(' ','_')}_Initiative_Edited.zip",
                                        mime="application/zip",
                                        use_container_width=True,
                                    )
                                except Exception as e:
                                    st.error(f"Failed to repack ZIP: {e}")
                else:
                    st.info("No mappings found in artifacts.")

            with st.expander("Initiative JSON (read-only)", expanded=False):
                initiative = files.get("initiative")
                if initiative:
                    st.json(initiative, expanded=False)
                else:
                    st.info("Initiative file not found.")

            with st.expander("Validation report", expanded=False):
                vr = files.get("validation_report")
                if vr:
                    st.json(vr, expanded=False)
                else:
                    st.info("Validation report not found.")

            with st.expander("Groups / Policies / Params", expanded=False):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.subheader("Groups")
                    st.json(files.get("groups"))
                with col_b:
                    st.subheader("Policies")
                    st.json(files.get("policies"))
                with col_c:
                    st.subheader("Params")
                    st.json(files.get("params"))

        # ── Deployment instructions ───────────────────────────────────
        st.header("🚀 Deploy to Azure")

        st.markdown("""
**After downloading and extracting the ZIP:**

**PowerShell:**
```powershell
cd <extracted-folder>
Connect-AzAccount
.\\Deploy-Initiative.ps1

# Or target a management group:
.\\Deploy-Initiative.ps1 -ManagementGroupId "mg-compliance"

# Create and assign in one step:
.\\Deploy-Initiative.ps1 -AssignAfterCreation
```

**Azure CLI:**
```bash
cd <extracted-folder>
az login
bash deploy-initiative.sh

# Or target a management group:
bash deploy-initiative.sh --management-group mg-compliance
```

**After deployment:**
1. Go to **Azure Portal → Policy → Definitions** to verify the initiative
2. **Assign** the initiative to your desired scope (subscription or management group)
3. **Defender for Cloud → Regulatory Compliance** will show the new standard within 24 hours
4. Review non-compliant resources and remediate
""")

else:
    # ── Show instructions when no file is uploaded ────────────────────
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
        2. **Extract** — pypdf extracts the text, then Azure OpenAI (GPT-5) identifies every control
        3. **Map** — Each control is mapped to Azure Policy definitions and MCSB controls
        4. **Validate** — Policy GUIDs are verified, confidence scores are checked
        5. **Generate** — Initiative JSON, PowerShell scripts, and CSV reports are created
        6. **Download** — Get a ZIP with everything needed to deploy to Azure
        """)
