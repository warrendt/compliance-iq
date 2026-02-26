"""
Review & Edit Page - Review and modify AI-generated mappings.
"""

import streamlit as st
import pandas as pd
from utils.api_client import get_api_client

st.set_page_config(
    page_title="Review & Edit | AI Mapping Agent",
    page_icon="✏️",
    layout="wide"
)

# Initialize session state
if 'mappings' not in st.session_state:
    st.session_state.mappings = []
if 'framework_name' not in st.session_state:
    st.session_state.framework_name = ""
if 'mcsb_controls' not in st.session_state:
    st.session_state.mcsb_controls = None

# Header
st.title("✏️ Review & Edit Mappings")
st.markdown("Review and refine the AI-generated mappings before exporting")

st.markdown("---")

# Check if mappings exist
if not st.session_state.mappings:
    st.warning("⚠️ No mappings to review. Please complete the mapping step first.")
    if st.button("Go to AI Mapping"):
        st.switch_page("pages/2_🤖_AI_Mapping.py")
    st.stop()

# Get API client
api_client = get_api_client()

# Load MCSB controls for reference (cached)
if st.session_state.mcsb_controls is None:
    with st.spinner("Loading MCSB controls..."):
        try:
            st.session_state.mcsb_controls = api_client.get_mcsb_controls()
        except Exception as e:
            st.error(f"❌ Error loading MCSB controls: {str(e)}")
            st.session_state.mcsb_controls = []

# Create MCSB lookup dictionary
mcsb_lookup = {c['control_id']: c for c in st.session_state.mcsb_controls} if st.session_state.mcsb_controls else {}
mcsb_options = sorted([c['control_id'] for c in st.session_state.mcsb_controls]) if st.session_state.mcsb_controls else []

# Display summary
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total Mappings", len(st.session_state.mappings))

with col2:
    avg_confidence = sum(m.get('confidence_score', 0) for m in st.session_state.mappings) / len(st.session_state.mappings)
    st.metric("Avg Confidence", f"{avg_confidence:.0%}")

with col3:
    high_conf_count = sum(1 for m in st.session_state.mappings if m.get('confidence_score', 0) >= 0.8)
    st.metric("High Confidence (≥80%)", high_conf_count)

with col4:
    low_conf_count = sum(1 for m in st.session_state.mappings if m.get('confidence_score', 0) < 0.6)
    st.metric("Low Confidence (<60%)", low_conf_count)

with col5:
    sov_count = sum(1 for m in st.session_state.mappings if m.get('sovereignty'))
    st.metric("Sovereignty Mapped", sov_count)

st.markdown("---")

# Filter options
st.markdown("### 🔍 Filter Mappings")

col_filter1, col_filter2, col_filter3, col_filter4 = st.columns(4)

with col_filter1:
    confidence_filter = st.selectbox(
        "Confidence Level",
        options=["All", "High (≥80%)", "Medium (60-80%)", "Low (<60%)"],
        index=0
    )

with col_filter2:
    # Get unique MCSB domains
    domains = sorted(set(mcsb_lookup[m.get('mcsb_control_id', '')].get('domain', 'Unknown') 
                        for m in st.session_state.mappings 
                        if m.get('mcsb_control_id', '') in mcsb_lookup))
    
    domain_filter = st.selectbox(
        "MCSB Domain",
        options=["All"] + domains,
        index=0
    )

with col_filter3:
    mapping_types = sorted(set(m.get('mapping_type', 'direct') for m in st.session_state.mappings))
    
    type_filter = st.selectbox(
        "Mapping Type",
        options=["All"] + mapping_types,
        index=0
    )

with col_filter4:
    sov_level_filter = st.selectbox(
        "Sovereignty Level",
        options=["All", "L1 — Global", "L2 — CMK", "L3 — Confidential", "None"],
        index=0,
        help="Filter by AI-recommended sovereignty level"
    )

# Apply filters
filtered_mappings = st.session_state.mappings.copy()

if confidence_filter == "High (≥80%)":
    filtered_mappings = [m for m in filtered_mappings if m.get('confidence_score', 0) >= 0.8]
elif confidence_filter == "Medium (60-80%)":
    filtered_mappings = [m for m in filtered_mappings if 0.6 <= m.get('confidence_score', 0) < 0.8]
elif confidence_filter == "Low (<60%)":
    filtered_mappings = [m for m in filtered_mappings if m.get('confidence_score', 0) < 0.6]

if domain_filter != "All" and mcsb_lookup:
    filtered_mappings = [m for m in filtered_mappings 
                         if m.get('mcsb_control_id', '') in mcsb_lookup 
                         and mcsb_lookup[m.get('mcsb_control_id', '')].get('domain') == domain_filter]

if type_filter != "All":
    filtered_mappings = [m for m in filtered_mappings if m.get('mapping_type') == type_filter]

if sov_level_filter != "All":
    if sov_level_filter == "None":
        filtered_mappings = [m for m in filtered_mappings if not m.get('sovereignty')]
    else:
        target_level = sov_level_filter.split(" ")[0]  # "L1", "L2", "L3"
        filtered_mappings = [m for m in filtered_mappings
                             if m.get('sovereignty') and m['sovereignty'].get('sovereignty_level') == target_level]

st.info(f"📋 Showing **{len(filtered_mappings)}** of **{len(st.session_state.mappings)}** mappings")

st.markdown("---")

# Review and edit each mapping
st.markdown("### 📝 Edit Mappings")

if not filtered_mappings:
    st.warning("No mappings match the current filters.")
else:
    # Track if any changes were made
    changes_made = False
    
    for idx, mapping in enumerate(filtered_mappings):
        with st.expander(
            f"{'⚠️' if mapping.get('confidence_score', 0) < 0.6 else '✅'} "
            f"{mapping.get('control_id', mapping.get('external_control_id', 'N/A'))} → {mapping.get('mcsb_control_id', 'N/A')} "
            f"({mapping.get('confidence_score', 0):.0%})",
            expanded=mapping.get('confidence_score', 0) < 0.6
        ):
            col_edit1, col_edit2 = st.columns([1, 1])
            
            with col_edit1:
                st.markdown("#### 📋 Source Control")
                control_id = mapping.get('control_id', mapping.get('external_control_id', 'N/A'))
                control_name = mapping.get('control_name', mapping.get('external_control_name', 'N/A'))
                st.markdown(f"**ID:** {control_id}")
                st.markdown(f"**Name:** {control_name}")
                st.markdown(f"**Description:** {mapping.get('description', 'N/A')}")
                if mapping.get('domain'):
                    st.markdown(f"**Domain:** {mapping['domain']}")
            
            with col_edit2:
                st.markdown("#### 🎯 MCSB Mapping")
                
                # Edit MCSB control
                current_mcsb = mapping.get('mcsb_control_id', '')
                current_idx = mcsb_options.index(current_mcsb) if current_mcsb in mcsb_options else 0
                control_id_key = mapping.get('control_id', mapping.get('external_control_id', f'unknown_{idx}'))
                
                new_mcsb = st.selectbox(
                    "MCSB Control",
                    options=mcsb_options,
                    index=current_idx,
                    key=f"mcsb_{idx}_{control_id_key}"
                )
                
                if new_mcsb != current_mcsb:
                    # Find the original mapping in session state and update it
                    mapping_id = mapping.get('control_id', mapping.get('external_control_id'))
                    for i, m in enumerate(st.session_state.mappings):
                        m_id = m.get('control_id', m.get('external_control_id'))
                        if m_id == mapping_id:
                            st.session_state.mappings[i]['mcsb_control_id'] = new_mcsb
                            st.session_state.mappings[i]['manual_override'] = True
                            changes_made = True
                            break
                
                # Show MCSB control details
                if new_mcsb in mcsb_lookup:
                    mcsb_control = mcsb_lookup[new_mcsb]
                    st.caption(f"**Title:** {mcsb_control['title']}")
                    st.caption(f"**Domain:** {mcsb_control.get('domain', 'N/A')}")
                
                # Confidence score (read-only if not manually overridden)
                st.metric("Confidence Score", f"{mapping.get('confidence_score', 0):.0%}")
                
                # Mapping type
                st.caption(f"**Type:** {mapping.get('mapping_type', 'direct').replace('_', ' ').title()}")
            
            # AI Reasoning
            st.markdown("#### 💡 AI Reasoning")
            st.info(mapping.get('reasoning', 'No reasoning provided'))
            
            # Azure Policies
            if mapping.get('azure_policy_ids'):
                st.markdown("#### 🎯 Recommended Azure Policies")
                # Batch-fetch display names from cache
                _pids = mapping['azure_policy_ids']
                _cache_key = f"_policy_detail_cache_{hash(tuple(_pids))}"
                if _cache_key not in st.session_state:
                    try:
                        st.session_state[_cache_key] = api_client.get_policy_details(_pids).get("policies", {})
                    except Exception:
                        st.session_state[_cache_key] = {}
                _details = st.session_state[_cache_key]
                for policy_id in _pids:
                    _pd = _details.get(policy_id)
                    if _pd and _pd.get("display_name"):
                        _url = _pd.get("learn_url", "")
                        if _url:
                            st.markdown(f"- **{_pd['display_name']}** — `{policy_id}` ([docs]({_url}))")
                        else:
                            st.markdown(f"- **{_pd['display_name']}** — `{policy_id}`")
                    else:
                        st.code(policy_id, language="text")
            
            # Sovereignty mapping
            sov = mapping.get('sovereignty')
            if sov:
                st.markdown("#### 🏛️ Sovereignty Mapping")
                sov_level = sov.get('sovereignty_level', 'N/A')
                _level_colors = {'L1': '🟢', 'L2': '🟡', 'L3': '🔴'}
                _level_labels = {
                    'L1': 'Global (Data Residency + Trusted Launch)',
                    'L2': 'CMK (Customer-Managed Keys)',
                    'L3': 'Confidential Computing',
                }
                col_sov1, col_sov2 = st.columns(2)
                with col_sov1:
                    st.markdown(
                        f"**Level:** {_level_colors.get(sov_level, '⚪')} **{sov_level}** — "
                        f"{_level_labels.get(sov_level, sov_level)}"
                    )
                    if sov.get('sovereignty_objectives'):
                        st.markdown("**Objectives:** " + ", ".join(sov['sovereignty_objectives']))
                    if sov.get('target_archetype'):
                        st.markdown(f"**Target Archetype:** `{sov['target_archetype']}`")
                with col_sov2:
                    if sov.get('slz_policy_names'):
                        st.markdown("**SLZ Policies:**")
                        for pname in sov['slz_policy_names'][:5]:
                            st.caption(f"• {pname}")
                        if len(sov['slz_policy_names']) > 5:
                            st.caption(f"  ... and {len(sov['slz_policy_names']) - 5} more")
                    if sov.get('reasoning'):
                        st.info(sov['reasoning'])
            
            # Delete mapping option
            col_delete1, col_delete2 = st.columns([3, 1])
            with col_delete2:
                delete_id = mapping.get('control_id', mapping.get('external_control_id', f'unknown_{idx}'))
                if st.button("🗑️ Delete", key=f"delete_{idx}_{delete_id}"):
                    # Remove from session state
                    mapping_id = mapping.get('control_id', mapping.get('external_control_id'))
                    st.session_state.mappings = [m for m in st.session_state.mappings 
                                                 if m.get('control_id', m.get('external_control_id')) != mapping_id]
                    st.success(f"Deleted mapping for {delete_id}")
                    st.rerun()

# Show changes notification
if changes_made:
    st.success("✅ Changes saved! Mappings have been updated.")

# Export statistics
st.markdown("---")
st.markdown("### 📊 Mapping Statistics")

if st.session_state.mappings:
    # Create DataFrame for analysis
    df = pd.DataFrame(st.session_state.mappings)
    
    col_stat1, col_stat2 = st.columns(2)
    
    with col_stat1:
        st.markdown("#### Confidence Distribution")
        confidence_bins = pd.cut(df['confidence_score'], bins=[0, 0.6, 0.8, 1.0], labels=['Low', 'Medium', 'High'])
        confidence_dist = confidence_bins.value_counts().sort_index()
        st.bar_chart(confidence_dist)
    
    with col_stat2:
        st.markdown("#### Top MCSB Controls")
        top_mcsb = df['mcsb_control_id'].value_counts().head(10)
        st.bar_chart(top_mcsb)
    
    # Sovereignty statistics
    sov_mappings = [m for m in st.session_state.mappings if m.get('sovereignty')]
    if sov_mappings:
        st.markdown("#### 🏛️ Sovereignty Level Distribution")
        col_sov_stat1, col_sov_stat2, col_sov_stat3 = st.columns(3)
        level_counts = {'L1': 0, 'L2': 0, 'L3': 0}
        for m in sov_mappings:
            lvl = m['sovereignty'].get('sovereignty_level', '')
            if lvl in level_counts:
                level_counts[lvl] += 1
        with col_sov_stat1:
            st.metric("🟢 L1 — Global", level_counts['L1'])
        with col_sov_stat2:
            st.metric("🟡 L2 — CMK", level_counts['L2'])
        with col_sov_stat3:
            st.metric("🔴 L3 — Confidential", level_counts['L3'])

# Action buttons
st.markdown("---")

col_action1, col_action2, col_action3 = st.columns(3)

with col_action1:
    if st.button("← Back to Mapping", use_container_width=True):
        st.switch_page("pages/2_🤖_AI_Mapping.py")

with col_action2:
    # Download current mappings
    import json
    
    if st.download_button(
        label="📥 Download Mappings (JSON)",
        data=json.dumps(st.session_state.mappings, indent=2),
        file_name=f"{st.session_state.framework_name.replace(' ', '_')}_mappings_reviewed.json",
        mime="application/json",
        use_container_width=True
    ):
        st.success("✅ Mappings downloaded!")

with col_action3:
    if st.button("Continue to Export →", type="primary", use_container_width=True):
        st.switch_page("pages/4_📦_Export_Policy.py")

# Sidebar
with st.sidebar:
    st.markdown("### 📊 Review Status")
    
    st.metric("Mappings", len(st.session_state.mappings))
    st.metric("Filtered View", len(filtered_mappings))
    
    manual_overrides = sum(1 for m in st.session_state.mappings if m.get('manual_override', False))
    if manual_overrides > 0:
        st.metric("Manual Edits", manual_overrides)
    
    st.markdown("---")
    
    st.markdown("### 💡 Tips")
    st.markdown("""
    - Review low confidence mappings first
    - Use filters to focus on specific areas
    - Change MCSB control if needed
    - Delete incorrect mappings
    - Download for backup
    """)
    
    st.markdown("---")
    
    st.markdown("### ⚠️ Confidence Guide")
    st.markdown("""
    - **High (≥80%)**: Strong match
    - **Medium (60-80%)**: Good match
    - **Low (<60%)**: Review needed
    """)
