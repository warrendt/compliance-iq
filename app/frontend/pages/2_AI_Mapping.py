"""
AI Mapping Page - Map controls to MCSB using AI.
"""

import streamlit as st
from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.components import render_page_header
from utils.state_init import init_session_state, restore_workflow_state
from utils.task_manager import (
    cancel_task,
    register_task,
    update_task,
    get_task,
    has_active_task_of_type,
    get_tasks_by_type,
)
from components.log_viewer import render_log_viewer
from components.backend_log_viewer import (
    render_backend_log_viewer,
    render_job_activity,
)
from components.mapping_progress import build_mapping_activity
from components.mapping_progress import find_active_mapping_job
from components.task_status_bar import render_task_status_bar
from components.policy_display import render_policy_list
import httpx

_MAPPING_STATUS_POLL_INTERVAL = "2s"
_MAX_SAFE_MAPPING_CONCURRENCY = 10

st.set_page_config(
    page_title="AI Mapping | ComplianceIQ",
    page_icon="🛡️",
    layout="wide"
)

inject_azure_theme()
render_sidebar()
init_session_state()
restore_workflow_state()
render_task_status_bar()

# A page rerun or navigation can outlive its local state flags while the task
# registry retains the active backend job. Restore that job before rendering.
if not st.session_state.mapping_in_progress:
    active_mapping_job = find_active_mapping_job(get_tasks_by_type("ai_mapping"))
    if active_mapping_job:
        st.session_state.mapping_in_progress = True
        st.session_state.mapping_job_id = active_mapping_job

# Header
render_page_header(
    "AI control mapping",
    eyebrow="Map",
    description="Use AI to automatically map your controls to the Microsoft Cloud Security Benchmark and Sovereign Landing Zone policies.",
)

st.markdown("---")

if notice := st.session_state.pop("workflow_restored_notice", None):
    st.success(f"🔄 {notice}")

# Check if controls are loaded
if not st.session_state.controls:
    st.warning("⚠️ No controls loaded. Please upload controls first.")
    if st.button("Go to Upload Page"):
        st.switch_page("pages/1_Upload_Controls.py")
    st.stop()

# Display framework info
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Framework", st.session_state.framework_name)
with col2:
    st.metric("Controls to Map", len(st.session_state.controls))
with col3:
    mapping_metric_label = (
        "Previous Mappings"
        if st.session_state.mapping_in_progress
        else "Mappings Created"
    )
    st.metric(mapping_metric_label, len(st.session_state.mappings))

st.markdown("---")

# Mapping options
st.markdown("### ⚙️ Mapping Configuration")

col_config1, col_config2 = st.columns(2)

with col_config1:
    mapping_mode = st.radio(
        "Mapping Mode",
        options=["Batch Mapping (All Controls)", "Single Control Test"],
        help="Choose whether to map all controls at once or test with a single control first"
    )

with col_config2:
    concurrency = st.slider(
        "Parallel Mappings",
        min_value=1,
        max_value=_MAX_SAFE_MAPPING_CONCURRENCY,
        value=_MAX_SAFE_MAPPING_CONCURRENCY,
        step=1,
        help=(
            "Concurrent controls to map. The maximum matches the approved Azure OpenAI "
            "quota for the primary model deployment."
        ),
    )

st.markdown("---")

# API client
api_client = get_api_client()


def _render_mapping_progress(
    progress: int,
    mapped_controls: int,
    total_controls: int,
    status: str,
    job_activity: list[dict],
    progress_slot,
    activity_slot,
    log_slot,
) -> None:
    """Refresh only the dynamic contents of the active mapping card."""
    progress_activity = build_mapping_activity(
        progress,
        mapped_controls,
        total_controls,
        status,
    )
    state_icons = {
        "complete": "✅",
        "active": "🔄",
        "pending": "○",
    }

    with progress_slot.container():
        st.progress(
            progress,
            text=f"{progress}% complete — {progress_activity[2]['label']}",
        )
    with activity_slot.container():
        for item in progress_activity:
            st.markdown(f"{state_icons[item['state']]} {item['label']}")
    with log_slot.container():
        render_job_activity(
            job_activity,
            "Waiting for the mapping service to report its first event.",
        )


def _render_active_mapping_shell(job_id: str, num_controls: int) -> None:
    """Keep a static mapping shell mounted around fragment-only live slots."""
    with st.container(border=True):
        st.markdown(f"#### 🤖 Mapping {st.session_state.framework_name}")
        st.caption("Progress updates automatically while controls are mapped.")
        progress_slot = st.empty()
        st.markdown("**Live activity from the mapping service**")
        activity_slot = st.empty()
        st.markdown("**Recent backend events**")
        log_slot = st.empty()
    _render_active_mapping_job(
        job_id,
        num_controls,
        progress_slot,
        activity_slot,
        log_slot,
    )


def _complete_mapping_job(job_id: str, status: dict) -> None:
    """Store completed mappings and transition the page out of live polling."""
    result = status.get("result", {}) or {}
    raw_mappings = result.get("mappings", [])
    mappings = [
        {
            "control_id": mapping.get("external_control_id", "N/A"),
            "control_name": mapping.get("external_control_name", "N/A"),
            "description": next(
                (
                    control["description"]
                    for control in st.session_state.controls
                    if control["control_id"] == mapping.get("external_control_id")
                ),
                "",
            ),
            "domain": next(
                (
                    control.get("domain")
                    for control in st.session_state.controls
                    if control["control_id"] == mapping.get("external_control_id")
                ),
                None,
            ),
            "mcsb_control_id": mapping.get("mcsb_control_id", "N/A"),
            "mcsb_control_name": mapping.get("mcsb_control_name", "N/A"),
            "mcsb_domain": mapping.get("mcsb_domain", "N/A"),
            "confidence_score": mapping.get("confidence_score", 0.0),
            "reasoning": mapping.get("reasoning", ""),
            "azure_policy_ids": mapping.get("azure_policy_ids", []),
            "mapping_type": mapping.get("mapping_type", "unknown"),
            "sovereignty": mapping.get("sovereignty"),
        }
        for mapping in raw_mappings
    ]

    st.session_state.mappings = mappings
    st.session_state.mapping_in_progress = False
    st.session_state.mapping_job_id = None
    update_task(job_id, status="completed", progress=100, result=result)

    try:
        api_client = get_api_client()
        api_client.save_session(
            st.session_state["session_uuid"],
            {
                "controls": st.session_state.controls,
                "mappings": mappings,
                "framework_name": st.session_state.framework_name,
                "policy_decisions": st.session_state.get("policy_decisions", {}),
                "selected_platform": st.session_state.get("selected_platform", "azure_defender"),
                "platform_display_name": st.session_state.get("platform_display_name", ""),
            },
        )
    except Exception as exc:
        st.session_state.mapping_persistence_warning = (
            f"Mappings completed but could not be saved for recovery: {exc}"
        )

    mapped_count = result.get("mapped_count") or len(mappings)
    failed_count = max(
        (result.get("total_controls") or len(mappings)) - mapped_count,
        0,
    )
    if failed_count > 0:
        st.session_state.mapping_completed_notice = (
            f"Mapped {mapped_count} controls; {failed_count} used fallback mappings."
        )
    else:
        st.session_state.mapping_completed_notice = (
            f"Successfully mapped {mapped_count} controls."
        )


@st.fragment(run_every=_MAPPING_STATUS_POLL_INTERVAL)
def _render_active_mapping_job(
    job_id: str,
    num_controls: int,
    progress_slot,
    activity_slot,
    log_slot,
) -> None:
    """Poll and redraw only the dynamic contents of the mapping card."""
    api_client = get_api_client()
    try:
        status = api_client.get_job_status(job_id)
    except httpx.ConnectError:
        error = "Cannot connect to the mapping service."
        st.session_state.mapping_error = error
        st.session_state.mapping_in_progress = False
        st.session_state.mapping_job_id = None
        update_task(job_id, status="failed", error=error)
        st.rerun()
        return
    except Exception as exc:
        st.session_state.mapping_error = str(exc)
        st.session_state.mapping_in_progress = False
        st.session_state.mapping_job_id = None
        update_task(job_id, status="failed", error=str(exc))
        st.rerun()
        return

    mapped_controls = status.get("mapped_controls", 0)
    total_controls = status.get("total_controls", num_controls)
    progress = max(
        0,
        min(
            status.get("progress")
            or int((mapped_controls / max(total_controls, 1)) * 100),
            100,
        ),
    )
    job_status = status.get("status", "")

    if job_status == "failed":
        error = status.get("error_message", "Unknown error")
        st.session_state.mapping_error = error
        st.session_state.mapping_in_progress = False
        st.session_state.mapping_job_id = None
        update_task(job_id, status="failed", error=error)
        st.rerun()
        return

    if job_status == "completed":
        _complete_mapping_job(job_id, status)
        st.rerun()
        return

    update_task(
        job_id,
        status="running",
        progress=progress,
        stage=job_status,
        mapped=mapped_controls,
    )
    _render_mapping_progress(
        progress,
        mapped_controls,
        total_controls,
        job_status,
        status.get("activity", []),
        progress_slot,
        activity_slot,
        log_slot,
    )
    if st.button("⏹️ Cancel", key=f"cancel_mapping_{job_id}"):
        cancel_task(job_id)
        st.session_state.mapping_in_progress = False
        st.session_state.mapping_job_id = None
        st.rerun()


# Single control test mode
if mapping_mode == "Single Control Test":
    st.markdown("### 🧪 Test Single Control Mapping")
    
    # Select control
    control_options = [f"{c['control_id']} - {c['control_name']}" for c in st.session_state.controls]
    selected_control_str = st.selectbox(
        "Select a control to test",
        options=control_options
    )
    
    selected_idx = control_options.index(selected_control_str)
    selected_control = st.session_state.controls[selected_idx]
    
    # Show control details
    with st.expander("📋 Control Details", expanded=True):
        st.markdown(f"**Control ID:** {selected_control['control_id']}")
        st.markdown(f"**Name:** {selected_control['control_name']}")
        st.markdown(f"**Description:** {selected_control['description']}")
        if selected_control.get('domain'):
            st.markdown(f"**Domain:** {selected_control['domain']}")
    
    # Map button
    if st.button("🚀 Map This Control", type="primary"):
        with st.spinner("Analyzing control and finding MCSB matches..."):
            try:
                raw_result = api_client.map_single_control(
                    control_id=selected_control['control_id'],
                    control_name=selected_control['control_name'],
                    description=selected_control['description'],
                    domain=selected_control.get('domain')
                )
                
                # Unwrap the mapping key if present
                result = raw_result.get('mapping', raw_result) if isinstance(raw_result, dict) else raw_result
                
                # Display results
                st.success("✅ Mapping complete!")
                
                col_result1, col_result2 = st.columns(2)
                
                with col_result1:
                    st.markdown("#### 📊 Mapping Result")
                    st.metric("Confidence Score", f"{result['confidence_score']:.0%}")
                    st.metric("MCSB Control", result['mcsb_control_id'])
                    st.metric("Mapping Type", result['mapping_type'].replace('_', ' ').title())
                
                with col_result2:
                    st.markdown("#### 💡 AI Reasoning")
                    st.info(result['reasoning'])
                
                if result.get('azure_policy_ids'):
                    st.markdown("#### 🎯 Recommended Azure Policies")
                    render_policy_list(api_client, result['azure_policy_ids'])
                
                # Sovereignty mapping details
                sov = result.get('sovereignty')
                if sov:
                    st.markdown("#### 🏛️ Sovereignty Mapping")
                    sov_level = sov.get('sovereignty_level', 'N/A')
                    level_colors = {'L1': '🟢', 'L2': '🟡', 'L3': '🔴'}
                    level_labels = {'L1': 'Global (Data Residency)', 'L2': 'CMK (Customer-Managed Keys)', 'L3': 'Confidential Computing'}
                    st.markdown(f"**Level:** {level_colors.get(sov_level, '⚪')} **{sov_level}** — {level_labels.get(sov_level, sov_level)}")
                    
                    if sov.get('sovereignty_objectives'):
                        st.markdown("**Objectives:** " + ", ".join(sov['sovereignty_objectives']))
                    if sov.get('slz_policy_names'):
                        st.markdown("**SLZ Policies:**")
                        for pname in sov['slz_policy_names']:
                            st.caption(f"• {pname}")
                    if sov.get('target_archetype'):
                        st.markdown(f"**Target Archetype:** `{sov['target_archetype']}`")
                    if sov.get('reasoning'):
                        st.info(f"**Sovereignty Reasoning:** {sov['reasoning']}")
                
            except httpx.ConnectError:
                st.error("❌ Cannot connect to backend. Make sure it's running.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# Batch mapping mode
else:
    st.markdown("### 🚀 Batch Mapping")

    num_controls = len(st.session_state.controls)
    est_per_control = 45  # ~45 seconds per AI mapping call
    est_total = (num_controls / concurrency) * est_per_control

    if completed_notice := st.session_state.pop("mapping_completed_notice", None):
        st.success(f"✅ {completed_notice}")
        mappings = st.session_state.mappings
        col_sum1, col_sum2, col_sum3 = st.columns(3)
        with col_sum1:
            avg_confidence = (
                sum(mapping.get("confidence_score", 0) for mapping in mappings)
                / len(mappings)
                if mappings
                else 0
            )
            st.metric("Average Confidence", f"{avg_confidence:.0%}")
        with col_sum2:
            high_confidence = sum(
                1
                for mapping in mappings
                if mapping.get("confidence_score", 0) >= 0.8
            )
            st.metric("High Confidence (≥80%)", high_confidence)
        with col_sum3:
            unique_mcsb = len(
                {
                    mapping.get("mcsb_control_id", "")
                    for mapping in mappings
                }
            )
            st.metric("Unique MCSB Controls", unique_mcsb)
        st.info("👉 Go to **Review & Edit** to validate the mappings")
        st.page_link(
            "pages/3_Review_Edit.py",
            label="Continue to Review →",
            icon="➡️",
        )

    if persistence_warning := st.session_state.pop(
        "mapping_persistence_warning",
        None,
    ):
        st.warning(persistence_warning)

    # ── Show any stored error from a previous failed run ─────────────────
    if st.session_state.mapping_error:
        st.error(f"❌ Mapping job failed: {st.session_state.mapping_error}")
        if st.button("🔄 Try Again", type="primary"):
            st.session_state.mapping_error = None
            st.session_state.mapping_in_progress = False
            st.session_state.mapping_job_id = None
            st.rerun()

    # ── Active job: poll status (handles both in-session and resumed jobs) ─
    elif st.session_state.mapping_in_progress and st.session_state.mapping_job_id:
        _render_active_mapping_shell(st.session_state.mapping_job_id, num_controls)

    # ── Idle: show start button ────────────────────────────────────────────
    else:
        st.info(f"📋 Ready to map **{num_controls}** controls from **{st.session_state.framework_name}**")
        st.warning(f"⏱️ Estimated time: ~{int(est_total)} seconds ({int(est_total)//60}m {int(est_total)%60}s) with {concurrency} parallel workers")

        # Warn if there is already an active mapping task
        has_other_mapping_task = has_active_task_of_type("ai_mapping") and not (
            st.session_state.mapping_in_progress and st.session_state.mapping_job_id
        )
        if has_other_mapping_task:
            st.warning(
                "⚠️ A mapping job is already in progress. "
                "Wait for it to finish or return to the workflow that started it."
            )

        if st.button(
            "▶️ Start Batch Mapping",
            type="primary",
            use_container_width=True,
            disabled=has_other_mapping_task,
        ):
            try:
                controls_payload = [
                    {
                        "control_id": c['control_id'],
                        "control_name": c['control_name'],
                        "description": c['description'],
                        "domain": c.get('domain')
                    }
                    for c in st.session_state.controls
                ]

                job_id = api_client.start_batch_mapping(
                    controls=controls_payload,
                    framework_name=st.session_state.framework_name,
                    concurrency=concurrency,
                )
                st.session_state.mapping_job_id = job_id
                st.session_state.mapping_in_progress = True
                st.session_state.mapping_error = None

                # Register in task manager for cross-page tracking
                register_task(
                    job_id,
                    "ai_mapping",
                    description=f"{st.session_state.framework_name} ({num_controls} controls)",
                    page_origin="pages/2_AI_Mapping.py",
                    total=num_controls,
                )

            except httpx.ConnectError:
                st.error("❌ Cannot connect to backend. Make sure it's running.")
            except Exception as e:
                st.error(f"❌ Error starting batch mapping: {str(e)}")
            else:
                st.rerun()

# Show existing mappings only after the active run reaches a terminal state.
if st.session_state.mappings and not st.session_state.mapping_in_progress:
    st.markdown("---")
    st.markdown("### 📋 Current Mappings")
    
    import pandas as pd
    
    mappings_df = pd.DataFrame([
        {
            'Control ID': m.get('control_id', m.get('external_control_id', 'N/A')),
            'Control Name': m.get('control_name', m.get('external_control_name', 'N/A')),
            'MCSB Control': m.get('mcsb_control_id', 'N/A'),
            'Confidence': f"{m.get('confidence_score', 0):.0%}",
            'SLZ Level': (m.get('sovereignty') or {}).get('sovereignty_level', '—'),
            'Type': m.get('mapping_type', 'unknown')
        }
        for m in st.session_state.mappings
    ])
    
    st.dataframe(
        mappings_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Download mappings
    import json
    
    if st.download_button(
        label="📥 Download Mappings (JSON)",
        data=json.dumps(st.session_state.mappings, indent=2),
        file_name=f"{st.session_state.framework_name.replace(' ', '_')}_mappings.json",
        mime="application/json"
    ):
        st.success("✅ Mappings downloaded!")

# Sidebar
with st.sidebar:
    st.markdown("### 🎯 Mapping Status")
    
    if st.session_state.mappings:
        st.success(f"✅ {len(st.session_state.mappings)} mappings created")
        
        # Statistics
        avg_conf = sum(m.get('confidence_score', 0) for m in st.session_state.mappings) / len(st.session_state.mappings)
        st.metric("Avg Confidence", f"{avg_conf:.0%}")
    else:
        st.info("No mappings yet")
    
    st.markdown("---")
    
    st.markdown("### 💡 Tips")
    st.markdown("""
    - Start with single control test
    - Review low confidence mappings
    - AI reasoning explains decisions
    - Edit mappings in next step
    """)
    
    st.markdown("---")
    
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("← Upload", use_container_width=True):
            st.switch_page("pages/1_Upload_Controls.py")
    with col_nav2:
        if st.button("Review →", use_container_width=True):
            st.switch_page("pages/3_Review_Edit.py")

render_footer()
render_log_viewer()
render_backend_log_viewer()
