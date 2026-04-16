"""
User Profile & History page — shows the current user's profile information,
upload history, AI mapping results, and export history.
"""

import streamlit as st
from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.state_init import init_session_state
from utils.auth import get_current_user
from components.log_viewer import render_log_viewer
from components.backend_log_viewer import render_backend_log_viewer

# ── Page configuration ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="ComplianceIQ — Profile",
    page_icon="👤",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_azure_theme()
init_session_state()
render_sidebar()

# ── Auth check ─────────────────────────────────────────────────────────────
auth_user = get_current_user()

st.markdown("## 👤 User Profile & History")
st.markdown("View your account details and activity history.")
st.markdown("---")

api = get_api_client()

# ── Profile card ───────────────────────────────────────────────────────────
col_profile, col_stats = st.columns([1, 2])

with col_profile:
    st.markdown("### 🪪 Account")
    profile = api.get_user_profile()

    if profile:
        display_name = profile.get("displayName") or (auth_user.display_name if auth_user else "Unknown")
        email = profile.get("email", "")

        st.markdown(f"**{display_name}**")
        if email:
            st.caption(email)

        st.markdown("---")

        # Editable display name
        with st.expander("✏️ Edit Profile"):
            new_name = st.text_input("Display Name", value=display_name, key="profile_display_name")
            platform_options = {
                "azure_defender": "Microsoft Defender for Cloud",
                "microsoft_365": "Microsoft 365 Compliance",
                "microsoft_purview": "Microsoft Purview",
            }
            current_platform = profile.get("preferredPlatform", "azure_defender")
            new_platform = st.selectbox(
                "Preferred Platform",
                options=list(platform_options.keys()),
                format_func=lambda k: platform_options[k],
                index=list(platform_options.keys()).index(current_platform)
                if current_platform in platform_options
                else 0,
                key="profile_preferred_platform",
            )
            if st.button("💾 Save Changes", type="primary"):
                updated = api.update_user_profile(
                    display_name=new_name if new_name != display_name else None,
                    preferred_platform=new_platform if new_platform != current_platform else None,
                )
                if updated:
                    st.success("Profile updated!")
                    st.rerun()
                else:
                    st.error("Failed to update profile. Please try again.")
    elif auth_user:
        st.markdown(f"**{auth_user.display_name}**")
        st.caption(auth_user.email)
        st.info("Sign in to load your full profile from the server.")
    else:
        st.info("🔒 Sign in to view your profile.")

with col_stats:
    st.markdown("### 📊 Activity Summary")
    if profile:
        m1, m2, m3 = st.columns(3)
        m1.metric("📁 Uploads", profile.get("uploadCount", 0))
        m2.metric("🤖 Mappings", profile.get("mappingCount", 0))
        m3.metric("📦 Exports", profile.get("exportCount", 0))

        last_active = profile.get("lastActive", "")
        if last_active:
            st.caption(f"Last active: {last_active[:19].replace('T', ' ')}")
    else:
        st.info("Profile data unavailable — backend may be offline.")

st.markdown("---")

# ── History tabs ───────────────────────────────────────────────────────────
tab_history, tab_uploads, tab_mappings, tab_exports = st.tabs([
    "🕒 All Activity",
    "📁 Uploads",
    "🤖 Mappings",
    "📦 Exports",
])

# All Activity
with tab_history:
    st.markdown("#### Recent Activity")
    history = api.get_user_history(limit=50)
    if history:
        for item in history:
            ts = item.get("timestamp", "")[:19].replace("T", " ")
            icon_map = {"upload": "📁", "mapping": "🤖", "export": "📦"}
            icon = icon_map.get(item.get("type", ""), "📋")
            summary = item.get("summary", item.get("type", "event"))
            st.markdown(f"{icon} **{summary}** &nbsp; <small style='color:#888'>{ts}</small>", unsafe_allow_html=True)
    else:
        st.info("No activity recorded yet. Start by uploading a compliance framework.")

# Uploads
with tab_uploads:
    st.markdown("#### Uploaded Files")
    uploads = api.get_user_uploads(limit=50)
    if uploads:
        for up in uploads:
            ts = up.get("timestamp", "")[:19].replace("T", " ")
            fname = up.get("fileName", "unknown")
            rows = up.get("rowCount", 0)
            size_kb = round(up.get("fileSize", 0) / 1024, 1)
            with st.container():
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(f"📄 **{fname}**")
                c2.caption(f"{rows} rows · {size_kb} KB")
                c3.caption(ts)
            st.divider()
    else:
        st.info("No uploads recorded yet.")
        if st.button("📁 Go to Upload", key="profile_goto_upload"):
            st.switch_page("pages/1_📁_Upload_Controls.py")

# Mappings
with tab_mappings:
    st.markdown("#### AI Mapping Results")
    mappings = api.get_user_mappings(limit=50)
    if mappings:
        for m in mappings:
            ts = m.get("timestamp", "")[:19].replace("T", " ")
            control_name = m.get("controlName", m.get("controlId", "unknown"))
            framework = m.get("framework", "")
            conf = m.get("confidence", None)
            conf_str = f"{conf:.0%}" if conf is not None else "—"
            with st.container():
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(f"🤖 **{control_name}** <small>({framework})</small>", unsafe_allow_html=True)
                c2.caption(f"Confidence: {conf_str}")
                c3.caption(ts)
            st.divider()
    else:
        st.info("No AI mapping results recorded yet.")
        if st.button("🤖 Go to AI Mapping", key="profile_goto_mapping"):
            st.switch_page("pages/2_🤖_AI_Mapping.py")

# Exports
with tab_exports:
    st.markdown("#### Policy Exports")
    exports = api.get_user_exports(limit=50)
    if exports:
        for exp in exports:
            ts = exp.get("timestamp", "")[:19].replace("T", " ")
            fname = exp.get("fileName", "unknown")
            framework = exp.get("framework", "")
            artifact_type = exp.get("artifactType", "")
            count = exp.get("controlCount", 0)
            with st.container():
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(f"📦 **{fname}** <small>({framework} · {artifact_type})</small>", unsafe_allow_html=True)
                c2.caption(f"{count} controls")
                c3.caption(ts)
            st.divider()
    else:
        st.info("No policy exports recorded yet.")
        if st.button("📦 Go to Export", key="profile_goto_export"):
            st.switch_page("pages/4_📦_Export_Policy.py")

render_footer()
render_log_viewer()
render_backend_log_viewer()
