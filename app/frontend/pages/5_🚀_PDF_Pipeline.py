"""
Page 5: PDF Upload — Extract controls from a compliance PDF and load into the mapping flow.
The user uploads a PDF, AI extracts the controls, user reviews/edits, then loads into Pages 2→3→4.
"""

import os
from datetime import datetime, timedelta, timezone
import pandas as pd
import streamlit as st
from utils.api_client import APIClient, get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.state_init import init_session_state
from utils.task_manager import (
    register_task,
    update_task,
    has_active_task_of_type,
    get_task,
    get_tasks_by_type,
)
from components.log_viewer import render_log_viewer
from components.backend_log_viewer import render_backend_log_viewer
from components.task_status_bar import render_task_status_bar

st.set_page_config(
    page_title="PDF Pipeline | ComplianceIQ",
    page_icon="🛡️",
    layout="wide",
)

inject_azure_theme()
render_sidebar()
init_session_state()


def _parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _reconcile_pdf_tasks() -> None:
    """Fail orphaned frontend-managed PDF tasks that can no longer complete."""
    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)

    task_id = st.session_state.get("pdf_extract_task_id")
    if task_id:
        task = get_task(task_id)
        if (
            task
            and task.get("status") in ("pending", "running")
            and not task.get("poll_backend", True)
            and not st.session_state.get("pdf_extracting")
        ):
            update_task(
                task_id,
                status="failed",
                stage="interrupted",
                error="PDF extraction was interrupted before completion. Please retry extraction.",
            )
            st.session_state["pdf_extract_task_id"] = None
            st.session_state["task_view_notice"] = (
                "A previous PDF extraction was interrupted and has been marked as failed. "
                "Please run extraction again."
            )

    for task in get_tasks_by_type("pdf_extraction"):
        if task.get("status") not in ("pending", "running"):
            continue
        if task.get("poll_backend", True):
            # Backend-polled tasks can run well beyond local page lifetimes.
            continue
        started_at = _parse_iso_utc(task.get("started_at"))
        if started_at and started_at < stale_cutoff:
            update_task(
                task["job_id"],
                status="failed",
                stage="stale",
                error="PDF extraction task expired before completion. Please retry extraction.",
            )


def _restore_active_backend_pdf_task() -> None:
    """Re-register active extraction task from persisted session data in new browser windows."""
    last_sync = _parse_iso_utc(st.session_state.get("pdf_backend_sync_last_check"))
    now_utc = datetime.now(timezone.utc)
    should_sync = last_sync is None or (now_utc - last_sync) > timedelta(seconds=5)

    if should_sync:
        try:
            saved = get_api_client().load_session(st.session_state.get("session_uuid"))
            if saved:
                if saved.get("pdf_extraction_job_id"):
                    st.session_state["pdf_extract_backend_job_id"] = saved.get("pdf_extraction_job_id")
                    st.session_state["pdf_extract_backend_status"] = saved.get("pdf_extraction_job_status")
                    st.session_state["pdf_extract_backend_progress"] = int(saved.get("pdf_extraction_job_progress") or 0)
                    st.session_state["pdf_extract_backend_stage"] = saved.get("pdf_extraction_job_stage")
                if saved.get("pdf_extraction") and not st.session_state.get("pdf_extraction"):
                    st.session_state["pdf_extraction"] = saved.get("pdf_extraction")
                    st.session_state["pdf_file_name"] = saved.get("pdf_extraction_file_name")
        except Exception:
            pass
        st.session_state["pdf_backend_sync_last_check"] = now_utc.isoformat()

    session_job_id = st.session_state.get("pdf_extract_backend_job_id")
    session_job_status = st.session_state.get("pdf_extract_backend_status")

    # If backend confirms an extraction job for this session, allow auto-restore again
    # so completed results appear without requiring a manual "View" click.
    if session_job_id and session_job_status in ("running", "completed"):
        st.session_state["pdf_disable_auto_restore"] = False

    if not session_job_id:
        return
    if session_job_status in ("completed", "failed", "cancelled"):
        return

    existing = get_task(session_job_id)
    if existing and existing.get("status") in ("pending", "running"):
        st.session_state["pdf_extract_task_id"] = session_job_id
        st.session_state["pdf_extracting"] = True
        return

    register_task(
        session_job_id,
        "pdf_extraction",
        description=f"Extract controls from {st.session_state.get('pdf_file_name') or 'PDF'}",
        page_origin="pdf_pipeline",
        poll_backend=True,
    )
    update_task(
        session_job_id,
        status="running",
        progress=int(st.session_state.get("pdf_extract_backend_progress") or 10),
        stage=st.session_state.get("pdf_extract_backend_stage") or "extracting",
    )
    st.session_state["pdf_extract_task_id"] = session_job_id
    st.session_state["pdf_extracting"] = True


def _restore_extraction_from_task_result() -> None:
    """Restore extracted controls from the latest completed PDF task result."""
    if st.session_state.get("pdf_extraction"):
        return
    if st.session_state.get("pdf_disable_auto_restore"):
        return

    session_job_id = st.session_state.get("pdf_extract_backend_job_id")
    if not session_job_id:
        return

    task = get_task(session_job_id)
    if not task or task.get("status") != "completed" or not isinstance(task.get("result"), dict):
        return
    if task.get("job_id") == st.session_state.get("pdf_last_restored_task_id"):
        return

    result = task.get("result") or {}
    extraction = result.get("extraction") or result.get("extraction_result")
    if not extraction:
        return

    st.session_state["pdf_extraction"] = extraction
    st.session_state["pdf_extracting"] = False
    st.session_state["pdf_extract_task_id"] = None
    source_file = result.get("source_file")
    if source_file:
        st.session_state["pdf_file_name"] = source_file
    st.session_state["pdf_last_restored_task_id"] = task.get("job_id")
    st.session_state["task_view_notice"] = (
        "Restored extracted controls from your latest completed PDF task."
    )


_reconcile_pdf_tasks()
_restore_active_backend_pdf_task()
_restore_extraction_from_task_result()
render_task_status_bar()

if st.session_state.get("task_view_notice"):
    st.warning(st.session_state["task_view_notice"])
    st.session_state["task_view_notice"] = None

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
    # Persist file bytes in session state so they survive page navigation
    st.session_state.pdf_file_bytes = uploaded_file.getvalue()
    st.session_state.pdf_file_name = uploaded_file.name
    st.session_state.pdf_disable_auto_restore = False

# Determine which file we're working with (freshly uploaded or persisted)
file_bytes = st.session_state.pdf_file_bytes
file_name = st.session_state.pdf_file_name

if file_bytes:
    file_size = len(file_bytes)
    st.success(f"✅ **{file_name}** ({file_size:,} bytes)")

    # ── Step 2: Extract controls ──────────────────────────────────────
    st.markdown("### 2️⃣ Extract Controls")

    st.toggle(
        "⚖️ Enrich legal/statutory references (optional)",
        key="pdf_enable_legal_enrichment",
        help=(
            "When enabled, extraction gives additional weight to legal/statutory citations and "
            "compliance obligations found in the uploaded document text."
        ),
    )
    st.caption(
        "Legal enrichment is document-grounded: it uses the uploaded PDF text and citations within it. "
        "External legal database lookup is not enabled in this mode."
    )

    extraction_in_progress = st.session_state.pdf_extracting and has_active_task_of_type("pdf_extraction")
    extract_button = False

    if extraction_in_progress:
        st.info("⏳ PDF extraction is running in this session. Task status is tracked in the task bar.")
        if st.button("🛠️ Reset Stuck Extraction", use_container_width=True, key="pdf_reset_stuck_btn"):
            task_id = st.session_state.get("pdf_extract_task_id")
            if task_id:
                update_task(
                    task_id,
                    status="failed",
                    stage="reset",
                    error="Extraction was manually reset after appearing stuck.",
                )
            st.session_state["pdf_extracting"] = False
            st.session_state["pdf_extract_task_id"] = None
            st.session_state["pdf_extract_backend_job_id"] = None
            st.session_state["pdf_extract_backend_status"] = "failed"
            st.session_state["pdf_extract_backend_stage"] = "reset"
            st.session_state["task_view_notice"] = (
                "Stuck PDF extraction was reset. You can run extraction again."
            )
            st.rerun()

    if not extraction_in_progress:
        extract_button = st.button(
            "🔍 Extract Controls from PDF",
            type="primary",
            use_container_width=True,
            key="pdf_extract_controls_btn",
            disabled=st.session_state.pdf_extraction is not None,
        )

    if extract_button:
        if has_active_task_of_type("pdf_extraction"):
            st.warning("⚠️ A PDF extraction task is already in progress.")
            st.stop()

        st.session_state.pdf_disable_auto_restore = False

        try:
            client = APIClient(base_url=api_url)
            job = client.start_pdf_extraction_job(
                pdf_bytes=file_bytes,
                filename=file_name,
                session_id=st.session_state.get("session_uuid"),
                enrich_legal_references=bool(st.session_state.get("pdf_enable_legal_enrichment", False)),
            )
            task_id = job.get("job_id")
            if not task_id:
                raise RuntimeError("Backend did not return a job id for PDF extraction")

            st.session_state.pdf_extract_task_id = task_id
            st.session_state.pdf_extracting = True
            st.session_state["pdf_extract_backend_job_id"] = task_id
            st.session_state["pdf_extract_backend_status"] = job.get("status", "running")
            st.session_state["pdf_extract_backend_progress"] = int(job.get("progress", 10))
            st.session_state["pdf_extract_backend_stage"] = job.get("stage", "extracting")
            register_task(
                task_id,
                "pdf_extraction",
                description=f"Extract controls from {file_name}",
                page_origin="pdf_pipeline",
                poll_backend=True,
            )
            update_task(
                task_id,
                status="running",
                progress=int(job.get("progress", 10)),
                stage=job.get("stage", "extracting"),
            )
            st.info("⏳ Extraction job started. Progress will update automatically (10% → 20% → 40% → 50% → 60% ...).")
            st.rerun()
        except Exception as e:
            st.session_state.pdf_extracting = False
            st.session_state.pdf_extract_task_id = None
            st.session_state["pdf_extract_backend_job_id"] = None
            st.session_state["pdf_extract_backend_status"] = "failed"
            st.session_state["pdf_extract_backend_stage"] = "failed_to_start"
            st.error(f"❌ Extraction failed to start: {e}")

# ── Step 3: Preview & edit extracted controls ─────────────────────────────
# Shown regardless of whether a file is currently in the uploader —
# this ensures results survive page navigation.
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

                    # Persist immediately so controls survive reconnects/page reloads.
                    try:
                        get_api_client().save_session(
                            st.session_state["session_uuid"],
                            {
                                "controls": st.session_state.controls,
                                "mappings": st.session_state.mappings,
                                "framework_name": st.session_state.framework_name,
                                "selected_platform": st.session_state.get("selected_platform"),
                                "platform_display_name": st.session_state.get("platform_display_name"),
                                "pdf_extraction": st.session_state.get("pdf_extraction"),
                                "pdf_extraction_file_name": st.session_state.get("pdf_file_name"),
                            },
                        )
                    except Exception:
                        pass

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
                st.session_state.pdf_disable_auto_restore = True
                st.session_state.pdf_extraction = None
                st.session_state.pdf_extracting = False
                st.session_state.pdf_extract_task_id = None
                st.session_state["pdf_last_restored_task_id"] = None
                st.session_state["pdf_extract_backend_job_id"] = None
                st.session_state["pdf_extract_backend_status"] = None
                st.session_state["pdf_extract_backend_progress"] = 0
                st.session_state["pdf_extract_backend_stage"] = None
                st.session_state.pdf_file_bytes = None
                st.session_state.pdf_file_name = None
                try:
                    get_api_client().save_session(
                        st.session_state["session_uuid"],
                        {
                            "controls": st.session_state.get("controls", []),
                            "mappings": st.session_state.get("mappings", []),
                            "framework_name": st.session_state.get("framework_name", ""),
                            "selected_platform": st.session_state.get("selected_platform"),
                            "platform_display_name": st.session_state.get("platform_display_name"),
                            "clear_pdf_extraction": True,
                        },
                    )
                except Exception:
                    pass
                st.rerun()
    else:
        st.warning("No controls were extracted from the PDF. The document may not contain structured controls.")
        if st.button("🗑️ Clear & Try Again", use_container_width=True):
            st.session_state.pdf_disable_auto_restore = True
            st.session_state.pdf_extraction = None
            st.session_state.pdf_extracting = False
            st.session_state.pdf_extract_task_id = None
            st.session_state["pdf_last_restored_task_id"] = None
            st.session_state["pdf_extract_backend_job_id"] = None
            st.session_state["pdf_extract_backend_status"] = None
            st.session_state["pdf_extract_backend_progress"] = 0
            st.session_state["pdf_extract_backend_stage"] = None
            st.session_state.pdf_file_bytes = None
            st.session_state.pdf_file_name = None
            try:
                get_api_client().save_session(
                    st.session_state["session_uuid"],
                    {
                        "controls": st.session_state.get("controls", []),
                        "mappings": st.session_state.get("mappings", []),
                        "framework_name": st.session_state.get("framework_name", ""),
                        "selected_platform": st.session_state.get("selected_platform"),
                        "platform_display_name": st.session_state.get("platform_display_name"),
                        "clear_pdf_extraction": True,
                    },
                )
            except Exception:
                pass
            st.rerun()

elif not file_bytes:
    # ── Instructions when no file is uploaded ─────────────────────────
    st.info("👆 Upload a compliance control PDF to get started")

    with st.expander("📋 What Documents This Pipeline Supports"):
        st.markdown("""
        The PDF pipeline is **not limited** to a fixed list of government frameworks.

        It supports any PDF that contains structured obligations, requirements, controls, or policy statements, including:
        - Government and national compliance frameworks
        - Financial services and banking controls (FSI)
        - Privacy and data protection regulations
        - Internal corporate control standards
        - Legal and statutory obligation documents
        - Industry standards and audit frameworks

        It works best when the PDF has identifiable sections, control IDs, headings, or requirement statements.
        """)

    with st.expander("ℹ️ How The PDF Pipeline Finds Controls"):
        st.markdown("""
        1. **Text extraction**: The pipeline extracts raw text from your uploaded PDF.
        2. **Control detection**: The AI scans the full text and identifies control statements, requirements, mandates, and sub-requirements.
        3. **Structure normalization**: It outputs each control with:
           - Control ID (from the document, or generated if missing)
           - Control title
           - Full requirement description
           - Domain classification
           - Control type and sub-controls
        4. **Metadata detection**: It also captures framework/document metadata such as authority, version, and region where available.
        5. **Human review loop**: You can edit extracted controls before loading them into mapping.

        Notes:
        - The extraction is grounded in the uploaded PDF content.
        - If your document references external laws or standards, include those references in the PDF text for best results.
        """)

render_footer()
render_log_viewer()
render_backend_log_viewer()
