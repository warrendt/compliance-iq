"""
Page 5: PDF Upload — Extract controls from a compliance PDF and load into the mapping flow.
The user uploads a PDF, AI extracts the controls, user reviews/edits, then loads into Pages 2→3→4.
"""

import os
import time
from typing import TypedDict
import httpx
import pandas as pd
import streamlit as st
from utils.api_client import APIClient, get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.components import render_page_header, render_success_effect
from utils.state_init import (
    init_session_state,
    persist_workflow_state,
    restore_workflow_state,
)
from utils.task_manager import (
    cancel_task,
    get_task,
    get_tasks_by_type,
    has_active_task_of_type,
    register_task,
    replace_task_job_id,
    update_task,
)
from components.log_viewer import render_log_viewer
from components.backend_log_viewer import (
    render_backend_log_viewer,
    render_pdf_backend_activity,
)
from components.pdf_progress import build_pdf_extraction_activity
from components.pdf_upload_state import is_replacement_upload
from components.task_status_bar import render_task_status_bar

st.set_page_config(
    page_title="PDF Extraction | ComplianceIQ",
    page_icon="🛡️",
    layout="wide",
)

inject_azure_theme()
render_sidebar()
init_session_state()
restore_workflow_state()
render_task_status_bar()

# ── Platform metadata helpers ─────────────────────────────────────────────

class _PlatformMeta(TypedDict):
    icon: str
    label: str
    next_page: str
    next_label: str
    guidance: str


_PLATFORM_META: dict[str, _PlatformMeta] = {
    "azure_defender": {
        "icon": "🛡️",
        "label": "Microsoft Defender for Cloud",
        "next_page": "pages/2_AI_Mapping.py",
        "next_label": "🤖 AI Mapping",
        "guidance": (
            "Controls are loaded! Navigate to **🤖 AI Mapping** (Page 2) "
            "to map them to Azure Policy definitions, then **Review** and **Export**."
        ),
    },
    "microsoft_365": {
        "icon": "📧",
        "label": "Microsoft 365 Compliance",
        "next_page": "pages/2_AI_Mapping.py",
        "next_label": "🤖 AI Mapping",
        "guidance": (
            "Controls are loaded! Navigate to **🤖 AI Mapping** (Page 2) "
            "to map them to Microsoft 365 compliance policies (DLP, Conditional Access, Intune), "
            "then **Review** and **Export**."
        ),
    },
    "microsoft_purview": {
        "icon": "🔍",
        "label": "Microsoft Purview",
        "next_page": "pages/2_AI_Mapping.py",
        "next_label": "🤖 AI Mapping",
        "guidance": (
            "Controls are loaded! Navigate to **🤖 AI Mapping** (Page 2) "
            "to map them to Microsoft Purview configurations (sensitivity labels, DLP, retention), "
            "then **Review** and **Export**."
        ),
    },
}

_DEFAULT_PLATFORM = "azure_defender"
_PDF_STATUS_POLL_INTERVAL = "2s"


def _get_platform_meta(platform_id: str) -> _PlatformMeta:
    """Return metadata for the given platform ID, falling back to Azure Defender."""
    return _PLATFORM_META.get(platform_id, _PLATFORM_META[_DEFAULT_PLATFORM])


def _render_pdf_extraction_progress(
    task_id: str,
    progress_slot,
    activity_slot,
    log_slot,
) -> None:
    """Refresh only the dynamic contents of the extraction card."""
    task = get_task(task_id) or {}
    progress = max(0, min(int(task.get("progress", 0)), 100))
    activity = build_pdf_extraction_activity(progress, task.get("stage", ""))
    state_icons = {
        "complete": "✅",
        "active": "🔄",
        "pending": "○",
    }

    with progress_slot.container():
        st.progress(
            progress,
            text=f"{progress}% complete — {activity[2]['label']}",
        )
    with activity_slot.container():
        st.caption("Live activity from the extraction service")
        for item in activity:
            st.markdown(f"{state_icons[item['state']]} {item['label']}")
    with log_slot.container():
        st.markdown("**Recent backend events**")
        render_pdf_backend_activity(task_id)


def _render_active_pdf_extraction_shell(
    task_id: str,
    file_name: str,
    api_url: str,
) -> None:
    """Keep a static extraction shell mounted around fragment-only live slots."""
    with st.container(border=True):
        st.markdown(f"#### 📄 Scanning {file_name}")
        st.caption("Progress updates automatically while the document is scanned.")
        progress_slot = st.empty()
        st.markdown("**Live activity from the extraction service**")
        activity_slot = st.empty()
        st.markdown("**Recent backend events**")
        log_slot = st.empty()
    _render_active_pdf_extraction(
        task_id,
        api_url,
        progress_slot,
        activity_slot,
        log_slot,
    )


def _apply_pdf_extraction_status(task_id: str, status: dict) -> str:
    """Apply one backend status response and return its terminal state, if any."""
    if status.get("status") == "completed":
        result = status.get("extraction")
        if not result:
            raise RuntimeError("The extraction completed without a result. Please retry.")
        st.session_state.pdf_extraction = result
        st.session_state.pdf_extracting = False
        st.session_state.pdf_extraction_error = None
        update_task(
            task_id,
            status="completed",
            progress=100,
            stage="completed",
            result={
                "framework_name": result.get("framework_name"),
                "total_controls": result.get("total_controls", 0),
            },
        )

        # Record the PDF extraction to the user's workspace (best-effort).
        try:
            get_api_client().record_upload(
                file_name=st.session_state.get("pdf_file_name") or "document.pdf",
                file_type="application/pdf",
                category="pdf_extraction",
                row_count=result.get("total_controls", 0),
                column_names=[],
                controls=result.get("controls", []),
                metadata={"framework": result.get("framework_name")},
            )
        except Exception:
            pass  # activity logging is best-effort

        return "completed"

    if status.get("status") in {"failed", "cancelled"}:
        st.session_state.pdf_extracting = False
        error = status.get("error", "Unknown extraction error")
        update_task(task_id, status="failed", stage="failed", error=error)
        return "failed"

    update_task(
        task_id,
        status="running",
        progress=status.get("progress", 0),
        stage=status.get("stage", "Extracting controls"),
    )
    return "running"


@st.fragment(run_every=_PDF_STATUS_POLL_INTERVAL)
def _render_active_pdf_extraction(
    task_id: str,
    api_url: str,
    progress_slot,
    activity_slot,
    log_slot,
) -> None:
    """Poll and redraw only the dynamic contents of the extraction card."""
    try:
        status = APIClient(base_url=api_url).get_pipeline_status(task_id)
        outcome = _apply_pdf_extraction_status(task_id, status)
    except Exception as exc:
        st.session_state.pdf_extracting = False
        st.session_state.pdf_extraction_error = str(exc)
        update_task(task_id, status="failed", stage="failed", error=str(exc))
        st.rerun()
        return

    if outcome == "completed":
        st.rerun()
    if outcome == "failed":
        task = get_task(task_id) or {}
        st.session_state.pdf_extraction_error = task.get(
            "error",
            "Unknown extraction error",
        )
        st.rerun()
        return

    _render_pdf_extraction_progress(
        task_id,
        progress_slot,
        activity_slot,
        log_slot,
    )


def _clear_pdf_workflow() -> None:
    """Cancel every active PDF job and clear all PDF-specific browser state."""
    active_pdf_tasks = [
        task
        for task in get_tasks_by_type("pdf_extraction")
        if task["status"] in {"pending", "running"}
    ]
    cancellation_errors = []
    for task in active_pdf_tasks:
        try:
            APIClient(base_url=os.getenv("BACKEND_URL", "http://localhost:8000")).cancel_pipeline_job(
                task["job_id"]
            )
        except Exception as exc:
            cancellation_errors.append(str(exc))
        finally:
            cancel_task(
                task["job_id"],
                error="Cancelled when the user cleared the PDF workflow",
            )
    if cancellation_errors:
        st.session_state.pdf_clear_warning = (
            "The browser state was cleared, but one or more backend jobs could not "
            f"be cancelled: {'; '.join(cancellation_errors)}"
        )
    st.session_state.pdf_extraction = None
    st.session_state.pdf_extracting = False
    st.session_state.pdf_extraction_error = None
    st.session_state.pdf_extract_task_id = None
    st.session_state.pdf_extraction_task_to_view = None
    st.session_state.pdf_file_bytes = None
    st.session_state.pdf_file_name = None
    st.session_state.pdf_extraction_restore_disabled = True
    st.session_state.pdf_upload_key += 1


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

    # ── Selected platform ──────────────────────────────────────────────
    st.markdown("---")
    _current_platform = st.session_state.get("selected_platform", _DEFAULT_PLATFORM)
    _pmeta = _get_platform_meta(_current_platform)
    st.markdown(f"**🎯 Target Platform**")
    st.info(f"{_pmeta['icon']} {_pmeta['label']}")
    st.page_link("pages/0_Platform_Selection.py", label="Change Platform")

    api_url = st.text_input(
        "Backend API URL",
        value=os.getenv("BACKEND_URL", "http://localhost:8000"),
        help="URL of the ComplianceIQ backend API",
    )

# Restore completed results independently of the uploader. A View click selects
# one exact task; the fallback supports completed tasks created before that key
# was introduced.
if not st.session_state.pdf_extraction:
    selected_task_id = st.session_state.pdf_extraction_task_to_view
    completed_extractions = [
        task
        for task in get_tasks_by_type("pdf_extraction")
        if task["status"] == "completed"
    ]
    if selected_task_id:
        candidate_task_ids = [selected_task_id]
    elif st.session_state.pdf_extraction_restore_disabled:
        candidate_task_ids = []
    else:
        candidate_task_ids = [
            task["job_id"]
            for task in sorted(
                completed_extractions,
                key=lambda task: task.get("completed_at") or task.get("started_at", ""),
                reverse=True,
            )
        ]

    for task_id in candidate_task_ids:
        task = get_task(task_id)
        result = task.get("result", {}) if task else {}
        extraction = result.get("extraction")
        if not extraction:
            try:
                status = APIClient(base_url=api_url).get_pipeline_status(task_id)
            except httpx.HTTPError as exc:
                if task_id == selected_task_id:
                    st.error(f"Could not load the completed extraction: {exc}")
                continue
            extraction = status.get("extraction")
            if status.get("status") == "completed" and extraction:
                update_task(task_id, status="completed", progress=100, result=status)
            elif task_id == selected_task_id:
                st.error(
                    "This completed extraction no longer has a recoverable result. "
                    "Upload the PDF again and retry the extraction."
                )
                st.session_state.pdf_extraction_task_to_view = None

        if extraction:
            st.session_state.pdf_extraction = extraction
            st.session_state.pdf_extracting = False
            st.session_state.pdf_extract_task_id = task_id
            st.session_state.pdf_extraction_task_to_view = None
            st.session_state.pdf_extraction_restore_disabled = False
            break

# ── Main content ──────────────────────────────────────────────────────────
render_page_header(
    "PDF control extraction",
    eyebrow="Govern",
    description="Extract compliance controls from a source PDF into a structured control set.",
)

if notice := st.session_state.pop("workflow_restored_notice", None):
    st.success(f"🔄 {notice}")

# ── Platform banner ───────────────────────────────────────────────────────
_selected_platform = st.session_state.get("selected_platform", _DEFAULT_PLATFORM)
_platform_meta = _get_platform_meta(_selected_platform)
st.info(
    f"{_platform_meta['icon']} **Target Platform: {_platform_meta['label']}** — "
    "Extracted controls will be mapped for this platform. "
    "[Change platform](./0_🎯_Platform_Selection)"
)

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
    key=f"pdf_uploader_{st.session_state.pdf_upload_key}",
)

if clear_warning := st.session_state.pop("pdf_clear_warning", None):
    st.warning(clear_warning)

if uploaded_file:
    uploaded_bytes = uploaded_file.getvalue()
    if is_replacement_upload(
        st.session_state.pdf_file_bytes,
        st.session_state.pdf_file_name,
        uploaded_bytes,
        uploaded_file.name,
    ):
        _clear_pdf_workflow()

    # Persist file bytes in session state so they survive page navigation
    st.session_state.pdf_file_bytes = uploaded_bytes
    st.session_state.pdf_file_name = uploaded_file.name
    st.session_state.pdf_extraction_restore_disabled = False

# Determine which file we're working with (freshly uploaded or persisted)
file_bytes = st.session_state.pdf_file_bytes
file_name = st.session_state.pdf_file_name

if file_bytes:
    file_size = len(file_bytes)
    st.success(f"✅ **{file_name}** ({file_size:,} bytes)")

    # ── Step 2: Extract controls ──────────────────────────────────────
    st.markdown("### 2️⃣ Extract Controls")

    if st.session_state.pdf_extraction_error:
        st.error(f"❌ Extraction failed: {st.session_state.pdf_extraction_error}")

    # The backend owns extraction. A fragment redraws only this live region.
    if (
        st.session_state.pdf_extracting
        and not st.session_state.pdf_extraction
        and st.session_state.pdf_extract_task_id
    ):
        _render_active_pdf_extraction_shell(
            st.session_state.pdf_extract_task_id,
            file_name,
            api_url,
        )

    extraction_in_progress = st.session_state.pdf_extracting and has_active_task_of_type("pdf_extraction")

    extract_button = st.button(
        "🔍 Extract Controls from PDF",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.pdf_extraction is not None or extraction_in_progress,
    )

    if extract_button:
        if has_active_task_of_type("pdf_extraction"):
            st.warning("⚠️ A PDF extraction task is already in progress.")
            st.stop()

        task_id = f"pdf_extract_{st.session_state['session_uuid']}_{int(time.time())}"
        st.session_state.pdf_extract_task_id = task_id
        st.session_state.pdf_extracting = True
        st.session_state.pdf_extraction_error = None
        register_task(
            task_id,
            "pdf_extraction",
            description=f"Extract controls from {file_name}",
            page_origin="pdf_pipeline",
            poll_backend=False,
        )
        try:
            job = APIClient(base_url=api_url).start_pdf_extraction(
                pdf_bytes=file_bytes,
                filename=file_name,
            )
            backend_job_id = job["job_id"]
            if backend_job_id != task_id:
                replace_task_job_id(task_id, backend_job_id)
                st.session_state.pdf_extract_task_id = backend_job_id
            update_task(
                st.session_state.pdf_extract_task_id,
                status="running",
                progress=job.get("progress", 0),
                stage=job.get("stage", "Queued"),
            )
        except Exception as e:
            st.session_state.pdf_extracting = False
            st.session_state.pdf_extraction_error = str(e)
            update_task(task_id, status="failed", stage="failed", error=str(e))
            st.error(f"❌ Could not submit PDF extraction: {e}")
        else:
            st.rerun()

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
                    try:
                        persist_workflow_state()
                    except Exception as exc:
                        st.warning(
                            f"Controls are loaded, but could not be saved for recovery: {exc}"
                        )

                    st.success(f"✅ Loaded {len(loaded_controls)} controls from **{framework_name}**")
                    render_success_effect(f"Loaded {len(loaded_controls)} controls")

                    st.markdown("---")
                    st.markdown("### ➡️ Next Steps")
                    _load_platform = st.session_state.get("selected_platform", _DEFAULT_PLATFORM)
                    _load_meta = _get_platform_meta(_load_platform)
                    st.info(_load_meta["guidance"])
                    st.page_link(
                        _load_meta["next_page"],
                        label=f"Continue to {_load_meta['next_label']} →",
                        icon="➡️",
                    )

        with col_clear:
            st.button(
                "🗑️ Clear & Start Over",
                use_container_width=True,
                on_click=_clear_pdf_workflow,
            )
    else:
        st.warning("No controls were extracted from the PDF. The document may not contain structured controls.")
        st.button(
            "🗑️ Clear & Try Again",
            use_container_width=True,
            on_click=_clear_pdf_workflow,
        )

elif not file_bytes:
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
        2. **Extract** — pypdf extracts the text, then Azure OpenAI identifies every control
        3. **Review** — You see all extracted controls in an editable table
        4. **Load** — Click to load controls into the mapping flow
        5. **Map → Review → Export** — Continue through Pages 2, 3, and 4 as normal
        """)

render_footer()
render_log_viewer()
render_backend_log_viewer()
