"""
Review & Edit Page - Review AI-generated Azure Policy mappings and track
controls Azure cannot address.
"""

import streamlit as st
import pandas as pd
from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.components import render_page_header
from utils.state_init import init_session_state, restore_workflow_state
from utils.coverage import is_policy_mapping, is_manual_register, COVERAGE_D
from components.log_viewer import render_log_viewer
from components.backend_log_viewer import render_backend_log_viewer
from components.task_status_bar import render_task_status_bar
from components.policy_display import render_policy_list

st.set_page_config(
    page_title="Review & Edit | ComplianceIQ",
    page_icon="🛡️",
    layout="wide"
)

inject_azure_theme()
init_session_state()
restore_workflow_state()
render_sidebar()
render_task_status_bar()

# Header
render_page_header(
    "Review & edit mappings",
    eyebrow="Map",
    description="Review the AI-generated Azure Policy mappings before exporting.",
)

st.markdown("---")

# Check if mappings exist
if not st.session_state.mappings:
    st.warning("⚠️ No mappings to review. Please complete the mapping step first.")
    if st.button("Go to AI Mapping"):
        st.switch_page("pages/2_AI_Mapping.py")
    st.stop()

# Get API client
api_client = get_api_client()

# Split once, up front: Azure covers policy_mappings (A_AzurePolicy /
# B_AzureConfig, plus legacy unclassified) and constructs an initiative entry
# for them - that is the only group where "confidence", "Azure Policy
# candidates", and "sovereignty level" are meaningful review dimensions.
# manual_register (C_Process / D_MicrosoftAttestation) is Azure cannot
# address at all: no initiative entry is built, so reviewing it alongside a
# confidence score or a defaulted sovereignty archetype misrepresents both
# groups. See utils/coverage.py.
policy_mappings = [m for m in st.session_state.mappings if is_policy_mapping(m)]
manual_register = [m for m in st.session_state.mappings if is_manual_register(m)]

# Top-level split summary
col_top1, col_top2, col_top3 = st.columns(3)
with col_top1:
    st.metric("Total Controls", len(st.session_state.mappings))
with col_top2:
    st.metric(
        "🎯 Policy Mappings",
        len(policy_mappings),
        help="Controls Azure covers - an Azure Policy initiative entry is constructed for these.",
    )
with col_top3:
    st.metric(
        "📋 Manual Register",
        len(manual_register),
        help="Process, legal, contractual, or Microsoft-attested controls - Azure has no technical means to enforce these, so no initiative entry is built.",
    )

st.markdown("---")

tab_policy, tab_manual = st.tabs([
    f"🎯 Policy Mappings ({len(policy_mappings)})",
    f"📋 Manual Register ({len(manual_register)})",
])

# ── Tab 1: Policy Mappings (A_AzurePolicy / B_AzureConfig) ────────────────────
with tab_policy:
    if not policy_mappings:
        st.info(
            "No controls in this framework are Azure-enforceable — every "
            "control landed in the Manual Register. See that tab."
        )
    else:
        # Display summary
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Policy Mappings", len(policy_mappings))

        with col2:
            avg_confidence = sum(m.get('confidence_score', 0) for m in policy_mappings) / len(policy_mappings)
            st.metric("Avg Confidence", f"{avg_confidence:.0%}")

        with col3:
            high_conf_count = sum(1 for m in policy_mappings if m.get('confidence_score', 0) >= 0.8)
            st.metric("High Confidence (≥80%)", high_conf_count)

        with col4:
            low_conf_count = sum(1 for m in policy_mappings if m.get('confidence_score', 0) < 0.6)
            st.metric("Low Confidence (<60%)", low_conf_count)

        with col5:
            sov_count = sum(1 for m in policy_mappings if m.get('sovereignty'))
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
            # Get unique policy categories (server-computed from the mapped Azure
            # Policy definitions' own catalog category - see policy_category on
            # ControlMapping - rather than a fixed MCSB domain list).
            domains = sorted(set(
                m.get('policy_category') for m in policy_mappings
                if m.get('policy_category')
            ))

            domain_filter = st.selectbox(
                "Policy Category",
                options=["All"] + domains,
                index=0
            )

        with col_filter3:
            mapping_types = sorted(set(m.get('mapping_type', 'direct') for m in policy_mappings))

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
        filtered_mappings = policy_mappings.copy()

        if confidence_filter == "High (≥80%)":
            filtered_mappings = [m for m in filtered_mappings if m.get('confidence_score', 0) >= 0.8]
        elif confidence_filter == "Medium (60-80%)":
            filtered_mappings = [m for m in filtered_mappings if 0.6 <= m.get('confidence_score', 0) < 0.8]
        elif confidence_filter == "Low (<60%)":
            filtered_mappings = [m for m in filtered_mappings if m.get('confidence_score', 0) < 0.6]

        if domain_filter != "All":
            filtered_mappings = [m for m in filtered_mappings
                                 if m.get('policy_category') == domain_filter]

        if type_filter != "All":
            filtered_mappings = [m for m in filtered_mappings if m.get('mapping_type') == type_filter]

        if sov_level_filter != "All":
            if sov_level_filter == "None":
                filtered_mappings = [m for m in filtered_mappings if not m.get('sovereignty')]
            else:
                target_level = sov_level_filter.split(" ")[0]  # "L1", "L2", "L3"
                filtered_mappings = [m for m in filtered_mappings
                                     if m.get('sovereignty') and m['sovereignty'].get('sovereignty_level') == target_level]

        st.info(f"📋 Showing **{len(filtered_mappings)}** of **{len(policy_mappings)}** policy mappings")

        st.markdown("---")

        # Review each mapping
        st.markdown("### 📝 Azure Policy Mappings")

        if not filtered_mappings:
            st.warning("No mappings match the current filters.")
        else:
            for idx, mapping in enumerate(filtered_mappings):
                with st.expander(
                    f"{'⚠️' if mapping.get('confidence_score', 0) < 0.6 else '✅'} "
                    f"{mapping.get('control_id', mapping.get('external_control_id', 'N/A'))} → "
                    f"{len(mapping.get('azure_policy_ids') or [])} Azure Polic{'y' if len(mapping.get('azure_policy_ids') or []) == 1 else 'ies'} "
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
                        st.markdown("#### 🎯 Azure Policy Mapping")

                        # policy_category is server-computed from the catalog category
                        # of the mapped Azure Policy definitions (see policy_category
                        # on ControlMapping) - there is no fixed intermediate taxonomy
                        # to pick from anymore, so this is informational, not editable.
                        if mapping.get('policy_category'):
                            st.caption(f"**Category:** {mapping['policy_category']}")
                        if mapping.get('coverage_display'):
                            st.caption(f"**Coverage:** {mapping['coverage_display']}")
                        if mapping.get('outside_step'):
                            st.caption(f"**Also needs:** {mapping['outside_step']}")

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
                        render_policy_list(api_client, mapping['azure_policy_ids'])

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
                        if st.button("🗑️ Delete", key=f"delete_policy_{idx}_{delete_id}"):
                            mapping_id = mapping.get('control_id', mapping.get('external_control_id'))
                            st.session_state.mappings = [m for m in st.session_state.mappings
                                                         if m.get('control_id', m.get('external_control_id')) != mapping_id]
                            st.success(f"Deleted mapping for {delete_id}")
                            st.rerun()

        # Confidence / category statistics
        st.markdown("---")
        st.markdown("### 📊 Mapping Statistics")

        df = pd.DataFrame(policy_mappings)

        col_stat1, col_stat2 = st.columns(2)

        with col_stat1:
            st.markdown("#### Confidence Distribution")
            confidence_bins = pd.cut(df['confidence_score'], bins=[0, 0.6, 0.8, 1.0], labels=['Low', 'Medium', 'High'])
            confidence_dist = confidence_bins.value_counts().sort_index()
            st.bar_chart(confidence_dist)

        with col_stat2:
            st.markdown("#### Top Policy Categories")
            if 'policy_category' in df.columns:
                top_categories = df['policy_category'].dropna().value_counts().head(10)
                st.bar_chart(top_categories)
            else:
                st.caption("No policy category data available.")

        # Sovereignty statistics
        sov_mappings = [m for m in policy_mappings if m.get('sovereignty')]
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

# ── Tab 2: Manual Register (C_Process / D_MicrosoftAttestation) ──────────────
with tab_manual:
    st.markdown(
        "These controls are **not addressable by Azure Policy** — they are "
        "process, legal, contractual, or Microsoft-operated requirements. "
        "**No Azure Policy initiative entry is constructed for them**, so "
        "there is no confidence score, Azure Policy candidate list, or "
        "sovereignty level to review here. Where a control is matched to "
        "Microsoft's own attestation (an ISO/SOC certification clause, audit "
        "report, or published documentation), that citation is shown so an "
        "auditor can retrieve it; otherwise track it for manual attestation."
    )

    if not manual_register:
        st.success("✅ Every control in this framework is Azure-addressable — the manual register is empty.")
    else:
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Manual Register", len(manual_register))
        with col_m2:
            process_count = sum(1 for m in manual_register if m.get('coverage_category') != COVERAGE_D)
            st.metric("Process / Organisational", process_count)
        with col_m3:
            attested_count = sum(1 for m in manual_register if m.get('coverage_category') == COVERAGE_D)
            grounded_count = sum(
                1 for m in manual_register
                if m.get('coverage_category') == COVERAGE_D and m.get('attestation') and not m.get('attestation_gap')
            )
            st.metric(
                "Microsoft Attested",
                attested_count,
                help=f"{grounded_count} of {attested_count} have a grounded citation; the rest are attestation gaps.",
            )

        st.markdown("---")

        col_mfilter1, col_mfilter2 = st.columns(2)
        with col_mfilter1:
            category_filter = st.selectbox(
                "Category",
                options=["All", "Process / organisational", "Microsoft attested"],
                index=0,
                key="manual_register_category_filter",
            )
        with col_mfilter2:
            responsibility_options = sorted(set(
                m.get('responsibility') for m in manual_register if m.get('responsibility')
            ))
            responsibility_filter = st.selectbox(
                "Responsibility",
                options=["All"] + responsibility_options,
                index=0,
                key="manual_register_responsibility_filter",
            )

        filtered_manual = manual_register.copy()
        if category_filter == "Process / organisational":
            filtered_manual = [m for m in filtered_manual if m.get('coverage_category') != COVERAGE_D]
        elif category_filter == "Microsoft attested":
            filtered_manual = [m for m in filtered_manual if m.get('coverage_category') == COVERAGE_D]
        if responsibility_filter != "All":
            filtered_manual = [m for m in filtered_manual if m.get('responsibility') == responsibility_filter]

        st.info(f"📋 Showing **{len(filtered_manual)}** of **{len(manual_register)}** manual-register controls")

        st.markdown("---")

        for idx, mapping in enumerate(filtered_manual):
            control_id = mapping.get('control_id', mapping.get('external_control_id', 'N/A'))
            control_name = mapping.get('control_name', mapping.get('external_control_name', 'N/A'))
            is_attested = mapping.get('coverage_category') == COVERAGE_D
            badge = "🏛️" if is_attested else "📄"

            with st.expander(f"{badge} {control_id} — {mapping.get('coverage_display') or mapping.get('coverage_category', 'N/A')}"):
                col_a, col_b = st.columns([1, 1])

                with col_a:
                    st.markdown("#### 📋 Source Control")
                    st.markdown(f"**ID:** {control_id}")
                    st.markdown(f"**Name:** {control_name}")
                    st.markdown(f"**Description:** {mapping.get('description', 'N/A')}")
                    if mapping.get('domain'):
                        st.markdown(f"**Domain:** {mapping['domain']}")
                    if mapping.get('control_type'):
                        st.markdown(f"**Control Type:** {mapping['control_type']}")

                with col_b:
                    st.markdown("#### 📋 Coverage Classification")
                    st.markdown(f"**Category:** {mapping.get('coverage_display') or mapping.get('coverage_category', 'N/A')}")
                    if mapping.get('responsibility'):
                        st.markdown(f"**Responsibility:** {mapping['responsibility']}")
                    st.caption("No Azure Policy initiative entry is constructed for this control.")
                    if mapping.get('coverage_reason'):
                        st.info(mapping['coverage_reason'])

                if is_attested:
                    st.markdown("#### 🏛️ Microsoft Attestation")
                    attestation = mapping.get('attestation') or {}
                    if mapping.get('attestation_gap') or not attestation:
                        st.warning(
                            "⚠️ **Attestation gap** — this control was classified as "
                            "Microsoft-attested, but no grounded certification clause, "
                            "audit-report criterion, or published documentation could be "
                            "found. Escalate commercially; do not report this as covered."
                        )
                    else:
                        col_c, col_d = st.columns(2)
                        with col_c:
                            if attestation.get('scheme'):
                                st.markdown(f"**Scheme:** {attestation['scheme']}")
                            if attestation.get('citation'):
                                st.markdown(f"**Citation:** {attestation['citation']}")
                            if attestation.get('basis_kind'):
                                st.caption(f"Basis: {attestation['basis_kind']}")
                        with col_d:
                            if attestation.get('evidence_document'):
                                st.markdown(f"**Evidence document:** {attestation['evidence_document']}")
                            if attestation.get('evidence_location'):
                                st.markdown(f"**Where to retrieve it:** {attestation['evidence_location']}")
                            if attestation.get('access_condition'):
                                st.caption(f"Access: {attestation['access_condition']}")
                elif mapping.get('evidence_source'):
                    st.markdown("#### 📄 Evidence")
                    st.info(mapping['evidence_source'])

                col_del1, col_del2 = st.columns([3, 1])
                with col_del2:
                    if st.button("🗑️ Delete", key=f"delete_manual_{idx}_{control_id}"):
                        st.session_state.mappings = [
                            m for m in st.session_state.mappings
                            if m.get('control_id', m.get('external_control_id')) != control_id
                        ]
                        st.success(f"Deleted {control_id} from the manual register")
                        st.rerun()

        st.markdown("---")
        manual_df = pd.DataFrame(filtered_manual)
        if not manual_df.empty:
            _manual_cols = [
                c for c in (
                    'control_id', 'control_name', 'control_type', 'coverage_display',
                    'responsibility', 'coverage_reason',
                ) if c in manual_df.columns
            ]
            st.download_button(
                label="📥 Download Manual Register (CSV)",
                data=manual_df[_manual_cols].to_csv(index=False),
                file_name=f"{st.session_state.framework_name.replace(' ', '_')}_manual_register.csv",
                mime="text/csv",
            )

st.markdown("---")

# Action buttons
col_action1, col_action2, col_action3 = st.columns(3)

with col_action1:
    if st.button("← Back to Mapping", use_container_width=True):
        st.switch_page("pages/2_AI_Mapping.py")

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
        st.switch_page("pages/4_Export_Policy.py")

# Sidebar
with st.sidebar:
    st.markdown("### 📊 Review Status")

    st.metric("Total Controls", len(st.session_state.mappings))
    st.metric("Policy Mappings", len(policy_mappings))
    st.metric("Manual Register", len(manual_register))

    st.markdown("---")

    st.markdown("### 💡 Tips")
    st.markdown("""
    - Review low confidence policy mappings first
    - Use filters to focus on specific areas
    - Escalate ungrounded attestation gaps
    - Delete incorrect mappings
    - Download for backup
    """)

    st.markdown("---")

    st.markdown("### ⚠️ Confidence Guide")
    st.markdown("""
    - **High (≥80%)**: Strong match
    - **Medium (60-80%)**: Good match
    - **Low (<60%)**: Review needed
    - *(Manual Register controls have no confidence score — Azure was never attempted for them.)*
    """)

render_footer()
render_log_viewer()
render_backend_log_viewer()
