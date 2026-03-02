"""
Policy Explorer Page — Browse policy definitions, initiatives, and assignments
in your Azure tenant using your Entra ID credentials.
"""

import streamlit as st
import pandas as pd
from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from components.log_viewer import render_log_viewer

st.set_page_config(
    page_title="Policy Explorer | ComplianceIQ",
    page_icon="🛡️",
    layout="wide",
)

inject_azure_theme()
render_sidebar()

# Header
st.title("🔍 Policy Explorer")
st.markdown("Browse policy definitions, initiatives, and assignments in your Azure tenant")
st.markdown("---")

# Auth check
try:
    from utils.auth import get_access_token
    _has_token = bool(get_access_token())
except Exception:
    _has_token = False

if not _has_token:
    st.warning("⚠️ Sign in with Entra ID to browse your Azure policies.")
    st.info("Use the **Sign In** button in the sidebar to authenticate.")
    st.stop()

api_client = get_api_client()

# ── Scope selector ────────────────────────────────────────────────────────
if "explorer_scopes" not in st.session_state:
    with st.spinner("Loading Azure scopes..."):
        try:
            st.session_state.explorer_scopes = api_client.list_deploy_scopes().get("scopes", [])
        except Exception as e:
            st.error(f"❌ Failed to load scopes: {e}")
            st.session_state.explorer_scopes = []

scopes = st.session_state.explorer_scopes

if not scopes:
    st.info("No subscriptions or management groups found.")
    st.stop()

scope_labels = [f"{s['type'].replace('_', ' ').title()}: {s['display']}" for s in scopes]
selected_idx = st.selectbox(
    "Azure Scope",
    range(len(scope_labels)),
    format_func=lambda i: scope_labels[i],
    key="explorer_scope_sel",
)
selected_scope = scopes[selected_idx]["scope"]

col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("🔄 Refresh", key="explorer_refresh"):
        for k in ["explorer_definitions", "explorer_initiatives", "explorer_assignments"]:
            st.session_state.pop(k, None)
        st.rerun()

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────
tab_defs, tab_inits, tab_assigns = st.tabs(["📋 Definitions", "📦 Initiatives", "🎯 Assignments"])

# helper
_custom_only = st.sidebar.checkbox("Custom policies only", value=True, key="explorer_custom_only")


def _load(key: str, fn):
    if key not in st.session_state:
        with st.spinner("Loading..."):
            try:
                st.session_state[key] = fn()
            except Exception as e:
                st.error(f"❌ {e}")
                st.session_state[key] = {}
    return st.session_state[key]


# ── Definitions tab ───────────────────────────────────────────────────────
with tab_defs:
    data = _load("explorer_definitions",
                 lambda: api_client.list_policy_definitions_arm(selected_scope, custom_only=_custom_only))
    defs = data.get("definitions", [])
    st.metric("Total Definitions", len(defs))

    if defs:
        rows = []
        for d in defs:
            props = d.get("properties", {})
            rows.append({
                "Name": d.get("name", ""),
                "Display Name": props.get("displayName", "—"),
                "Type": props.get("policyType", ""),
                "Mode": props.get("mode", ""),
                "Description": (props.get("description") or "")[:100],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No policy definitions found at this scope.")

# ── Initiatives tab ───────────────────────────────────────────────────────
with tab_inits:
    data = _load("explorer_initiatives",
                 lambda: api_client.list_policy_initiatives_arm(selected_scope, custom_only=_custom_only))
    inits = data.get("initiatives", [])
    st.metric("Total Initiatives", len(inits))

    if inits:
        rows = []
        for i in inits:
            props = i.get("properties", {})
            rows.append({
                "Name": i.get("name", ""),
                "Display Name": props.get("displayName", "—"),
                "Type": props.get("policyType", ""),
                "Policies": len(props.get("policyDefinitions", [])),
                "Description": (props.get("description") or "")[:100],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Expandable details
        for i in inits:
            props = i.get("properties", {})
            with st.expander(f"📦 {props.get('displayName', i.get('name', 'Unknown'))}"):
                st.markdown(f"**Name:** `{i.get('name', '')}`")
                st.markdown(f"**Description:** {props.get('description', '—')}")
                pol_defs = props.get("policyDefinitions", [])
                if pol_defs:
                    st.markdown(f"**Policy References ({len(pol_defs)}):**")
                    for pd_ref in pol_defs[:20]:
                        ref_id = pd_ref.get("policyDefinitionId", "")
                        st.caption(f"• `{ref_id.split('/')[-1]}`")
                    if len(pol_defs) > 20:
                        st.caption(f"  ... and {len(pol_defs) - 20} more")
    else:
        st.info("No initiative definitions found at this scope.")

# ── Assignments tab ───────────────────────────────────────────────────────
with tab_assigns:
    data = _load("explorer_assignments",
                 lambda: api_client.list_policy_assignments_arm(selected_scope))
    assigns = data.get("assignments", [])
    st.metric("Total Assignments", len(assigns))

    if assigns:
        rows = []
        for a in assigns:
            props = a.get("properties", {})
            rows.append({
                "Name": a.get("name", ""),
                "Display Name": props.get("displayName", "—"),
                "Scope": props.get("scope", ""),
                "Enforcement": props.get("enforcementMode", "Default"),
                "Policy ID": (props.get("policyDefinitionId") or "").split("/")[-1],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No policy assignments found at this scope.")

render_log_viewer()
