"""
AI Mapping Page - Map controls to MCSB using AI.

UX follows a wizard pattern: ① Configure → ② Running → ③ Results
Only the active phase is displayed, reducing cognitive load.
"""

import streamlit as st
import time
import json
import pandas as pd
from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.state_init import init_session_state
from utils.animations import render_completion_animation
from utils.task_manager import (
    register_task,
    update_task,
    get_task,
    has_active_task_of_type,
    get_tasks_by_type,
)
from components.log_viewer import render_log_viewer
from components.backend_log_viewer import render_backend_log_viewer
from components.task_status_bar import render_task_status_bar
import httpx

st.set_page_config(
    page_title="AI Mapping | ComplianceIQ",
    page_icon="🛡️",
    layout="wide"
)

inject_azure_theme()
render_sidebar()
init_session_state()
render_task_status_bar()

# ── CSS for wizard step indicator & confidence badges ──────────────────────
st.markdown("""
<style>
.ciq-wizard-steps {
    display: flex;
    justify-content: center;
    gap: 0;
    margin: 0.5rem 0 1.5rem;
}
.ciq-wizard-step {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 1.2rem;
    font-size: 0.95rem;
    font-weight: 500;
    color: #888;
    border-bottom: 3px solid transparent;
}
.ciq-wizard-step.active {
    color: var(--ciq-primary, #0078D4);
    border-bottom-color: var(--ciq-primary, #0078D4);
    font-weight: 700;
}
.ciq-wizard-step.done {
    color: var(--ciq-success, #107C10);
    border-bottom-color: var(--ciq-success, #107C10);
}
.ciq-wizard-arrow {
    display: flex;
    align-items: center;
    color: #CCC;
    font-size: 1.1rem;
    padding: 0 0.2rem;
}
.ciq-badge {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 600;
}
.ciq-badge-high   { background: #E8F5E9; color: #2E7D32; }
.ciq-badge-medium { background: #FFF8E1; color: #F57F17; }
.ciq-badge-low    { background: #FFEBEE; color: #C62828; }
.ciq-mapping-card {
    border: 1px solid #E0E0E0;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    background: #FAFAFA;
}
.ciq-mapping-card:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
}
.ciq-empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: #888;
}
.ciq-empty-state .ciq-empty-icon {
    font-size: 3.5rem;
    margin-bottom: 0.5rem;
}
.ciq-empty-state p {
    font-size: 1.05rem;
    max-width: 480px;
    margin: 0 auto;
}
</style>
""", unsafe_allow_html=True)


# ── Determine wizard phase ────────────────────────────────────────────────
def _wizard_phase() -> str:
    """Return 'empty', 'configure', 'running', or 'results'."""
    if not st.session_state.controls:
        return "empty"
    if st.session_state.mapping_in_progress and st.session_state.mapping_job_id:
        return "running"
    if st.session_state.mappings:
        return "results"
    return "configure"


phase = _wizard_phase()


def _render_step_indicator(active: str):
    """Draw the 3-step wizard indicator at the top."""
    steps = [
        ("configure", "① Configure"),
        ("running",   "② Running"),
        ("results",   "③ Results"),
    ]
    order = [s[0] for s in steps]
    active_idx = order.index(active) if active in order else 0
    parts = []
    for i, (key, label) in enumerate(steps):
        if i < active_idx:
            cls = "done"
        elif key == active:
            cls = "active"
        else:
            cls = ""
        parts.append(f'<span class="ciq-wizard-step {cls}">{label}</span>')
        if i < len(steps) - 1:
            parts.append('<span class="ciq-wizard-arrow">→</span>')
    st.markdown(
        '<div class="ciq-wizard-steps">' + "".join(parts) + "</div>",
        unsafe_allow_html=True,
    )


# ── Header ────────────────────────────────────────────────────────────────
st.title("🤖 AI Control Mapping")
st.markdown(
    "Use AI to automatically map your controls to the Microsoft Cloud Security "
    "Benchmark and Sovereign Landing Zone policies"
)

# Show step indicator (except empty state)
if phase != "empty":
    _render_step_indicator(phase)

st.markdown("---")

# API client
api_client = get_api_client()

# ══════════════════════════════════════════════════════════════════════════
# Phase: EMPTY — no controls loaded
# ══════════════════════════════════════════════════════════════════════════
if phase == "empty":
    st.markdown(
        '<div class="ciq-empty-state">'
        '<div class="ciq-empty-icon">📂</div>'
        "<p><strong>No controls loaded yet.</strong><br>"
        "Upload your compliance framework first, then return here to run the AI mapping.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    col_empty1, col_empty2, col_empty3 = st.columns([1, 2, 1])
    with col_empty2:
        if st.button("📁 Go to Upload Page", type="primary", use_container_width=True):
            st.switch_page("pages/1_📁_Upload_Controls.py")
    st.stop()

# ── Framework info bar (shown in all non-empty phases) ────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Framework", st.session_state.framework_name)
with col2:
    st.metric("Controls to Map", len(st.session_state.controls))
with col3:
    st.metric("Mappings Created", len(st.session_state.mappings))

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════
# Phase: CONFIGURE
# ══════════════════════════════════════════════════════════════════════════
if phase == "configure":
    # Sensible defaults — Streamlit widgets always create their values,
    # but we define them here first so the rest of the code can reference them
    # even before the expander renders.
    mapping_mode = "Batch Mapping (All Controls)"
    concurrency = 5

    # Collapsible options panel
    with st.expander("⚙️ Mapping Options", expanded=False):
        col_config1, col_config2 = st.columns(2)
        with col_config1:
            mapping_mode = st.radio(
                "Mapping Mode",
                options=["Batch Mapping (All Controls)", "Single Control Test"],
                help="Batch maps every control at once; Single lets you test one first",
            )
        with col_config2:
            concurrency = st.slider(
                "Parallel Workers",
                min_value=1,
                max_value=10,
                value=5,
                step=1,
                help="Number of controls to map concurrently (higher = faster but more API quota)",
            )

    num_controls = len(st.session_state.controls)
    est_per_control = 45
    est_total = (num_controls / concurrency) * est_per_control

    # ── Single control test ───────────────────────────────────────────────
    if mapping_mode == "Single Control Test":
        st.markdown("### 🧪 Test Single Control")

        control_options = [
            f"{c['control_id']} — {c['control_name']}"
            for c in st.session_state.controls
        ]
        selected_control_str = st.selectbox(
            "Select a control to test",
            options=control_options,
            help="Pick one control to send through the AI mapper for a quick check",
        )

        selected_idx = control_options.index(selected_control_str)
        selected_control = st.session_state.controls[selected_idx]

        with st.expander("📋 Control Details", expanded=True):
            st.markdown(f"**Control ID:** {selected_control['control_id']}")
            st.markdown(f"**Name:** {selected_control['control_name']}")
            st.markdown(f"**Description:** {selected_control['description']}")
            if selected_control.get("domain"):
                st.markdown(f"**Domain:** {selected_control['domain']}")

        if st.button("🚀 Map This Control", type="primary"):
            with st.spinner("Analyzing control and finding MCSB matches..."):
                try:
                    raw_result = api_client.map_single_control(
                        control_id=selected_control["control_id"],
                        control_name=selected_control["control_name"],
                        description=selected_control["description"],
                        domain=selected_control.get("domain"),
                    )
                    result = (
                        raw_result.get("mapping", raw_result)
                        if isinstance(raw_result, dict)
                        else raw_result
                    )

                    render_completion_animation("Mapping complete!")

                    col_result1, col_result2 = st.columns(2)
                    with col_result1:
                        st.markdown("#### 📊 Mapping Result")
                        st.metric("Confidence Score", f"{result['confidence_score']:.0%}")
                        st.metric("MCSB Control", result["mcsb_control_id"])
                        st.metric(
                            "Mapping Type",
                            result["mapping_type"].replace("_", " ").title(),
                        )
                    with col_result2:
                        st.markdown("#### 💡 AI Reasoning")
                        st.info(result["reasoning"])

                    if result.get("azure_policy_ids"):
                        st.markdown("#### 🎯 Recommended Azure Policies")
                        for policy_id in result["azure_policy_ids"]:
                            st.code(policy_id, language="text")

                    sov = result.get("sovereignty")
                    if sov:
                        st.markdown("#### 🏛️ Sovereignty Mapping")
                        sov_level = sov.get("sovereignty_level", "N/A")
                        level_colors = {"L1": "🟢", "L2": "🟡", "L3": "🔴"}
                        level_labels = {
                            "L1": "Global (Data Residency)",
                            "L2": "CMK (Customer-Managed Keys)",
                            "L3": "Confidential Computing",
                        }
                        st.markdown(
                            f"**Level:** {level_colors.get(sov_level, '⚪')} "
                            f"**{sov_level}** — {level_labels.get(sov_level, sov_level)}"
                        )
                        if sov.get("sovereignty_objectives"):
                            st.markdown(
                                "**Objectives:** " + ", ".join(sov["sovereignty_objectives"])
                            )
                        if sov.get("slz_policy_names"):
                            st.markdown("**SLZ Policies:**")
                            for pname in sov["slz_policy_names"]:
                                st.caption(f"• {pname}")
                        if sov.get("target_archetype"):
                            st.markdown(f"**Target Archetype:** `{sov['target_archetype']}`")
                        if sov.get("reasoning"):
                            st.info(f"**Sovereignty Reasoning:** {sov['reasoning']}")

                except httpx.ConnectError:
                    st.error("❌ Cannot connect to backend. Make sure it's running.")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

    # ── Batch mapping (idle) ──────────────────────────────────────────────
    else:
        # ── Error state ───────────────────────────────────────────────────
        if st.session_state.mapping_error:
            st.error(f"❌ Mapping job failed: {st.session_state.mapping_error}")
            if st.button("🔄 Try Again", type="primary"):
                st.session_state.mapping_error = None
                st.session_state.mapping_in_progress = False
                st.session_state.mapping_job_id = None
                st.rerun()
        else:
            st.info(
                f"📋 Ready to map **{num_controls}** controls from "
                f"**{st.session_state.framework_name}**"
            )
            st.caption(
                f"⏱️ Estimated time ≈ {int(est_total)} s "
                f"({int(est_total) // 60}m {int(est_total) % 60}s) "
                f"with {concurrency} parallel workers"
            )

            if has_active_task_of_type("ai_mapping"):
                st.warning(
                    "⚠️ A mapping job is already in progress. "
                    "You can start another or wait for it to finish."
                )

            col_start, col_cancel = st.columns([1, 1])
            with col_start:
                if st.button(
                    "▶️ Start Batch Mapping",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        controls_payload = [
                            {
                                "control_id": c["control_id"],
                                "control_name": c["control_name"],
                                "description": c["description"],
                                "domain": c.get("domain"),
                            }
                            for c in st.session_state.controls
                        ]
                        job_id = api_client.start_batch_mapping(
                            controls=controls_payload,
                            framework_name=st.session_state.framework_name,
                        )
                        st.session_state.mapping_job_id = job_id
                        st.session_state.mapping_in_progress = True
                        st.session_state.mapping_error = None
                        register_task(
                            job_id,
                            "ai_mapping",
                            description=f"{st.session_state.framework_name} ({num_controls} controls)",
                            page_origin="pages/2_🤖_AI_Mapping.py",
                            total=num_controls,
                        )
                        st.rerun()
                    except httpx.ConnectError:
                        st.error("❌ Cannot connect to backend. Make sure it's running.")
                    except Exception as e:
                        st.error(f"❌ Error starting batch mapping: {str(e)}")
            with col_cancel:
                if st.button("⏹️ Cancel", use_container_width=True):
                    st.session_state.mapping_in_progress = False
                    st.session_state.mapping_job_id = None
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# Phase: RUNNING — live polling
# ══════════════════════════════════════════════════════════════════════════
elif phase == "running":
    job_id = st.session_state.mapping_job_id
    num_controls = len(st.session_state.controls)

    st.markdown(
        "💡 **Tip:** You can navigate to other pages — the mapping continues in the background."
    )

    try:
        status = api_client.get_job_status(job_id)
        mapped_controls = status.get("mapped_controls", 0)
        total_controls = status.get("total_controls", num_controls)
        progress = status.get("progress") or int(
            (mapped_controls / max(total_controls, 1)) * 100
        )

        # Rich progress card
        st.progress(progress / 100)
        remaining = total_controls - mapped_controls
        concurrency_est = 5  # default worker count for time estimate
        est_remaining = int(remaining * 45 / max(1, concurrency_est))
        st.markdown(
            f"**Mapped {mapped_controls} / {total_controls}** controls "
            f"({progress}%) — ≈ {est_remaining // 60}m {est_remaining % 60}s remaining"
        )
        st.caption(f"Job ID: `{job_id}` · Status: {status.get('status')}")

        update_task(
            job_id,
            status="running",
            progress=progress,
            stage=status.get("status", ""),
            mapped=mapped_controls,
        )

        job_status = status.get("status")
        if job_status == "failed":
            err = status.get("error_message", "Unknown error")
            st.session_state.mapping_error = err
            st.session_state.mapping_in_progress = False
            st.session_state.mapping_job_id = None
            update_task(job_id, status="failed", error=err)
            st.rerun()
        elif job_status == "completed":
            result = status.get("result", {}) or {}
            raw_mappings = result.get("mappings", [])
            mappings = []
            for m in raw_mappings:
                mapping = {
                    "control_id": m.get("external_control_id", "N/A"),
                    "control_name": m.get("external_control_name", "N/A"),
                    "description": next(
                        (
                            c["description"]
                            for c in st.session_state.controls
                            if c["control_id"] == m.get("external_control_id")
                        ),
                        "",
                    ),
                    "domain": next(
                        (
                            c.get("domain")
                            for c in st.session_state.controls
                            if c["control_id"] == m.get("external_control_id")
                        ),
                        None,
                    ),
                    "mcsb_control_id": m.get("mcsb_control_id", "N/A"),
                    "mcsb_control_name": m.get("mcsb_control_name", "N/A"),
                    "mcsb_domain": m.get("mcsb_domain", "N/A"),
                    "confidence_score": m.get("confidence_score", 0.0),
                    "reasoning": m.get("reasoning", ""),
                    "azure_policy_ids": m.get("azure_policy_ids", []),
                    "mapping_type": m.get("mapping_type", "unknown"),
                    "sovereignty": m.get("sovereignty"),
                }
                mappings.append(mapping)

            st.session_state.mappings = mappings
            st.session_state.mapping_in_progress = False
            st.session_state.mapping_job_id = None
            update_task(job_id, status="completed", progress=100, result=result)

            # Auto-save session state
            try:
                api_client.save_session(
                    st.session_state["session_uuid"],
                    {
                        "controls": st.session_state.controls,
                        "mappings": mappings,
                        "framework_name": st.session_state.framework_name,
                        "policy_decisions": st.session_state.get("policy_decisions", {}),
                        "selected_platform": st.session_state.get(
                            "selected_platform", "azure_defender"
                        ),
                        "platform_display_name": st.session_state.get(
                            "platform_display_name", ""
                        ),
                    },
                )
            except Exception:
                pass  # session save is best-effort

            st.rerun()  # move to results phase
        else:
            # Still running — cancel button + poll
            col_cancel_active, _ = st.columns([1, 3])
            with col_cancel_active:
                if st.button("⏹️ Cancel", use_container_width=True):
                    st.session_state.mapping_in_progress = False
                    st.session_state.mapping_job_id = None
                    st.rerun()
            time.sleep(2)
            st.rerun()

    except httpx.ConnectError:
        st.error("❌ Cannot connect to backend. Make sure it's running.")
        st.session_state.mapping_in_progress = False
        st.session_state.mapping_job_id = None
    except Exception as e:
        st.error(f"❌ Error checking job status: {str(e)}")
        st.session_state.mapping_in_progress = False
        st.session_state.mapping_job_id = None

# ══════════════════════════════════════════════════════════════════════════
# Phase: RESULTS — card-based mapping display
# ══════════════════════════════════════════════════════════════════════════
elif phase == "results":
    mappings = st.session_state.mappings
    mapped_count = len(mappings)
    failed_count = 0  # already filtered in batch processing

    render_completion_animation(
        message=f"Mapped {mapped_count} controls",
        detail="Head to Review & Edit to validate the results",
    )

    # ── Summary metrics ───────────────────────────────────────────────────
    st.markdown("### 📊 Mapping Summary")
    col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
    avg_confidence = (
        sum(m.get("confidence_score", 0) for m in mappings) / len(mappings)
        if mappings
        else 0
    )
    high_confidence = sum(1 for m in mappings if m.get("confidence_score", 0) >= 0.8)
    low_confidence = sum(1 for m in mappings if m.get("confidence_score", 0) < 0.6)
    unique_mcsb = len(set(m.get("mcsb_control_id", "") for m in mappings))
    with col_sum1:
        st.metric("Average Confidence", f"{avg_confidence:.0%}")
    with col_sum2:
        st.metric("🟢 High (≥80%)", high_confidence)
    with col_sum3:
        st.metric("🔴 Low (<60%)", low_confidence)
    with col_sum4:
        st.metric("Unique MCSB Controls", unique_mcsb)

    st.markdown("---")

    # ── Card-based mapping results ────────────────────────────────────────
    st.markdown("### 📋 Mapping Results")

    def _badge(score: float) -> str:
        if score >= 0.8:
            return '<span class="ciq-badge ciq-badge-high">🟢 High</span>'
        elif score >= 0.6:
            return '<span class="ciq-badge ciq-badge-medium">🟡 Medium</span>'
        return '<span class="ciq-badge ciq-badge-low">🔴 Low</span>'

    for idx, m in enumerate(mappings):
        score = m.get("confidence_score", 0)
        ctrl_id = m.get("control_id", m.get("external_control_id", "N/A"))
        ctrl_name = m.get("control_name", m.get("external_control_name", "N/A"))
        mcsb_id = m.get("mcsb_control_id", "N/A")

        with st.expander(
            f"{ctrl_id} → {mcsb_id}  ({score:.0%})",
            expanded=score < 0.6,
        ):
            st.markdown(
                f"**{ctrl_name}** → **{mcsb_id}** "
                f"({m.get('mcsb_control_name', '')}) &nbsp; {_badge(score)}",
                unsafe_allow_html=True,
            )
            st.caption(
                f"Type: {m.get('mapping_type', 'direct').replace('_', ' ').title()} · "
                f"SLZ: {(m.get('sovereignty') or {}).get('sovereignty_level', '—')}"
            )
            with st.container():
                st.markdown("**💡 AI Reasoning**")
                st.info(m.get("reasoning", "No reasoning provided"))
            if st.button("✏️ Edit in Review", key=f"edit_{idx}_{ctrl_id}"):
                st.switch_page("pages/3_✏️_Review_Edit.py")

    st.markdown("---")

    # ── Download + navigation ─────────────────────────────────────────────
    col_dl, col_review = st.columns([1, 1])
    with col_dl:
        st.download_button(
            label="📥 Download Mappings (JSON)",
            data=json.dumps(st.session_state.mappings, indent=2),
            file_name=f"{st.session_state.framework_name.replace(' ', '_')}_mappings.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_review:
        if st.button(
            "➡️ Continue to Review & Edit",
            type="primary",
            use_container_width=True,
        ):
            st.switch_page("pages/3_✏️_Review_Edit.py")

    # ── Re-run option ─────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("🔄 Run mapping again", help="Discard current results and re-map"):
        st.session_state.mappings = []
        st.session_state.mapping_error = None
        st.rerun()

# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎯 Mapping Status")

    if st.session_state.mappings:
        st.success(f"✅ {len(st.session_state.mappings)} mappings created")
        avg_conf = (
            sum(m.get("confidence_score", 0) for m in st.session_state.mappings)
            / len(st.session_state.mappings)
        )
        st.metric("Avg Confidence", f"{avg_conf:.0%}")
    else:
        st.info("No mappings yet")

    st.markdown("---")

    st.markdown("### 💡 Tips")
    st.markdown("""
    - Start with a **single control test** to preview AI quality
    - Review **low-confidence** mappings carefully
    - AI reasoning explains every decision
    - Edit mappings on the **Review & Edit** page
    """)

    st.markdown("---")

    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("← Upload", use_container_width=True):
            st.switch_page("pages/1_📁_Upload_Controls.py")
    with col_nav2:
        if st.button("Review →", use_container_width=True):
            st.switch_page("pages/3_✏️_Review_Edit.py")

render_footer()
render_log_viewer()
render_backend_log_viewer()
