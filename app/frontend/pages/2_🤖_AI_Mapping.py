"""
AI Mapping Page - Map controls to MCSB using AI.
"""

import streamlit as st
import time
from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.state_init import init_session_state
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

# Header
st.title("🤖 AI Control Mapping")
st.markdown("Use AI to automatically map your controls to the Microsoft Cloud Security Benchmark and Sovereign Landing Zone policies")

st.markdown("---")

# Check if controls are loaded
if not st.session_state.controls:
    st.warning("⚠️ No controls loaded. Please upload controls first.")
    if st.button("Go to Upload Page"):
        st.switch_page("pages/1_📁_Upload_Controls.py")
    st.stop()

# Display framework info
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Framework", st.session_state.framework_name)
with col2:
    st.metric("Controls to Map", len(st.session_state.controls))
with col3:
    st.metric("Mappings Created", len(st.session_state.mappings))

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
        max_value=10,
        value=5,
        step=1,
        help="Number of controls to map concurrently (higher = faster but uses more API quota)"
    )

st.markdown("---")

# API client
api_client = get_api_client()

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
                    for policy_id in result['azure_policy_ids']:
                        st.code(policy_id, language="text")
                
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
        job_id = st.session_state.mapping_job_id
        st.info(f"⏳ Mapping job in progress (job ID: `{job_id}`) — you can navigate away safely; the task will continue in the background.")

        try:
            status = api_client.get_job_status(job_id)
            mapped_controls = status.get("mapped_controls", 0)
            total_controls = status.get("total_controls", num_controls)
            progress = status.get("progress") or int((mapped_controls / max(total_controls, 1)) * 100)

            st.progress(progress / 100)
            st.text(f"Status: {status.get('status')} — {mapped_controls}/{total_controls} mapped ({progress}%)")

            # Keep task manager in sync
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
                        'control_id': m.get('external_control_id', 'N/A'),
                        'control_name': m.get('external_control_name', 'N/A'),
                        'description': next((c['description'] for c in st.session_state.controls if c['control_id'] == m.get('external_control_id')), ''),
                        'domain': next((c.get('domain') for c in st.session_state.controls if c['control_id'] == m.get('external_control_id')), None),
                        'mcsb_control_id': m.get('mcsb_control_id', 'N/A'),
                        'mcsb_control_name': m.get('mcsb_control_name', 'N/A'),
                        'mcsb_domain': m.get('mcsb_domain', 'N/A'),
                        'confidence_score': m.get('confidence_score', 0.0),
                        'reasoning': m.get('reasoning', ''),
                        'azure_policy_ids': m.get('azure_policy_ids', []),
                        'mapping_type': m.get('mapping_type', 'unknown'),
                        'sovereignty': m.get('sovereignty'),
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
                            "selected_platform": st.session_state.get("selected_platform", "azure_defender"),
                            "platform_display_name": st.session_state.get("platform_display_name", ""),
                        },
                    )
                except Exception:
                    pass  # session save is best-effort

                mapped_count = result.get('mapped_count') or len(mappings)
                failed_count = (result.get('total_controls') or len(mappings)) - mapped_count

                if failed_count > 0:
                    st.warning(f"⚠️ Mapped {mapped_count} controls, {failed_count} failed (fallback created)")
                else:
                    st.success(f"✅ Successfully mapped {mapped_count} controls!")
                st.balloons()

                st.markdown("### 📊 Mapping Summary")
                col_sum1, col_sum2, col_sum3 = st.columns(3)
                with col_sum1:
                    avg_confidence = sum(m.get('confidence_score', 0) for m in mappings) / len(mappings) if mappings else 0
                    st.metric("Average Confidence", f"{avg_confidence:.0%}")
                with col_sum2:
                    high_confidence = sum(1 for m in mappings if m.get('confidence_score', 0) >= 0.8)
                    st.metric("High Confidence (≥80%)", high_confidence)
                with col_sum3:
                    unique_mcsb = len(set(m.get('mcsb_control_id', '') for m in mappings))
                    st.metric("Unique MCSB Controls", unique_mcsb)

                st.info("👉 Go to **Review & Edit** to validate the mappings")
                st.page_link("pages/3_✏️_Review_Edit.py", label="Continue to Review →", icon="➡️")
            else:
                # Still running — poll again after a short delay
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

    # ── Idle: show start button ────────────────────────────────────────────
    else:
        st.info(f"📋 Ready to map **{num_controls}** controls from **{st.session_state.framework_name}**")
        st.warning(f"⏱️ Estimated time: ~{int(est_total)} seconds ({int(est_total)//60}m {int(est_total)%60}s) with {concurrency} parallel workers")

        # Warn if there is already an active mapping task
        if has_active_task_of_type("ai_mapping"):
            st.warning("⚠️ A mapping job is already in progress. You can start another or wait for it to finish.")

        col_start, col_cancel = st.columns([1, 1])

        with col_start:
            if st.button("▶️ Start Batch Mapping", type="primary", use_container_width=True):
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
                    )
                    st.session_state.mapping_job_id = job_id
                    st.session_state.mapping_in_progress = True
                    st.session_state.mapping_error = None

                    # Register in task manager for cross-page tracking
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

# Show existing mappings if any
if st.session_state.mappings:
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
            st.switch_page("pages/1_📁_Upload_Controls.py")
    with col_nav2:
        if st.button("Review →", use_container_width=True):
            st.switch_page("pages/3_✏️_Review_Edit.py")

render_log_viewer()
render_backend_log_viewer()
