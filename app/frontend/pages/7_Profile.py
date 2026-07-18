"""
User Profile & History page — shows the current user's profile information,
upload history, AI mapping results, and export history.
"""

import csv
import io
import json

import streamlit as st
from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.components import render_page_header
from utils.state_init import init_session_state
from utils.auth import get_current_user
from components.log_viewer import render_log_viewer
from components.backend_log_viewer import render_backend_log_viewer


def _files_from_envelope(content: str, fallback_name: str):
    """Parse a stored artifact envelope into ``(name, data, mime)`` tuples.

    Artifacts are stored as ``{"files": [{name, mime, content}, ...]}`` so each
    generated format can be re-downloaded. Falls back to a single file for any
    legacy/plain content.
    """
    try:
        obj = json.loads(content)
        files = obj.get("files") if isinstance(obj, dict) else None
        if isinstance(files, list) and files:
            return [
                (
                    f.get("name") or fallback_name or "artifact.txt",
                    f.get("content") or "",
                    f.get("mime") or "text/plain",
                )
                for f in files
                if f.get("content")
            ]
    except (ValueError, TypeError):
        pass
    return [(fallback_name or "artifact.txt", content, "application/octet-stream")]


def _controls_to_csv(controls: list, column_names: list) -> str:
    """Rebuild a CSV from a stored control set for re-download."""
    if not controls:
        return ""
    headers = list(column_names) if column_names else list(controls[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in controls:
        writer.writerow({h: row.get(h, "") for h in headers})
    return buf.getvalue()

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

render_page_header(
    "My workspace",
    eyebrow="Report",
    description=(
        "Your one-stop compliance workspace — every document, control set, mapping, "
        "edit, and policy you build is captured here for your tenant."
    ),
)
st.markdown("---")

api = get_api_client()

# Stable per-user prefix so cached download payloads in session_state never leak
# across accounts on a shared browser session.
ws_user_key = (auth_user.email if auth_user else "anon")

# ── Quick actions ──────────────────────────────────────────────────────────
qa1, qa2, qa3, qa4 = st.columns(4)
if qa1.button("📁 Upload controls", use_container_width=True):
    st.switch_page("pages/1_Upload_Controls.py")
if qa2.button("🤖 AI mapping", use_container_width=True):
    st.switch_page("pages/2_AI_Mapping.py")
if qa3.button("🎯 Gap analysis", use_container_width=True):
    st.switch_page("pages/8_Diff_Compare.py")
if qa4.button("📦 Export policy", use_container_width=True):
    st.switch_page("pages/4_Export_Policy.py")

st.markdown("---")

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

# Load the workspace streams once and reuse across summary + tabs.
uploads = api.get_user_uploads(limit=200)
documents = [u for u in uploads if u.get("category") != "controls"]
control_sets = [u for u in uploads if u.get("category") == "controls"]

with col_stats:
    st.markdown("### 📊 Activity Summary")
    if profile:
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("📄 Documents", len(documents))
        m2.metric("📋 Control sets", len(control_sets))
        m3.metric("🤖 Mappings", profile.get("mappingCount", 0))
        m4.metric("📦 Exports", profile.get("exportCount", 0))
        # Document versions = total document uploads (each re-upload bumps version).
        m5.metric("🗂 Versions", len(documents))

        last_active = profile.get("lastActive", "")
        if last_active:
            st.caption(f"Last active: {last_active[:19].replace('T', ' ')}")
    else:
        st.info("Profile data unavailable — backend may be offline.")

st.markdown("---")

# ── Workspace streams ──────────────────────────────────────────────────────
(
    tab_history,
    tab_documents,
    tab_controls,
    tab_mappings,
    tab_changes,
    tab_exports,
) = st.tabs([
    "🕒 All Activity",
    "📄 Documents",
    "📋 Controls",
    "🤖 Mappings",
    "✏️ Changes",
    "📦 Policies",
])

# All Activity
with tab_history:
    st.markdown("#### Recent Activity")
    history = api.get_user_history(limit=50)
    if history:
        for item in history:
            ts = item.get("timestamp", "")[:19].replace("T", " ")
            icon_map = {
                "upload": "📄",
                "mapping": "🤖",
                "export": "📦",
                "edit": "✏️",
                "comparison": "🎯",
                "policy_version": "🗂",
            }
            icon = icon_map.get(item.get("type", ""), "📋")
            summary = item.get("summary", item.get("type", "event"))
            st.markdown(f"{icon} **{summary}** &nbsp; <small style='color:var(--neutral-fg-3)'>{ts}</small>", unsafe_allow_html=True)
    else:
        st.info("No activity recorded yet. Start by uploading a compliance framework.")

# Documents (with versions — stream #3/#6)
with tab_documents:
    st.markdown("#### Uploaded Documents")
    if documents:
        for up in documents:
            ts = up.get("timestamp", "")[:19].replace("T", " ")
            fname = up.get("fileName", "unknown")
            version = up.get("version", 1)
            rows = up.get("rowCount", 0)
            size_kb = round((up.get("fileSize", 0) or 0) / 1024, 1)
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f"📄 **{fname}** &nbsp;<small style='color:var(--neutral-fg-3)'>v{version}</small>", unsafe_allow_html=True)
            c2.caption(f"{rows} controls · {size_kb} KB")
            c3.caption(ts)
            st.divider()
    else:
        st.info("No documents uploaded yet.")
        if st.button("📄 Upload a document (PDF)", key="ws_goto_pdf"):
            st.switch_page("pages/5_PDF_Pipeline.py")

# Controls (stream #5)
with tab_controls:
    st.markdown("#### Stored Control Sets")
    if control_sets:
        for up in control_sets:
            ts = up.get("timestamp", "")[:19].replace("T", " ")
            fname = up.get("fileName", "unknown")
            version = up.get("version", 1)
            count = up.get("controlCount", up.get("rowCount", 0))
            up_id = up.get("id", "")
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.markdown(f"📋 **{fname}** &nbsp;<small style='color:var(--neutral-fg-3)'>v{version}</small>", unsafe_allow_html=True)
            c2.caption(f"{count} controls")
            c3.caption(ts)
            cache_key = f"ws_ctrl:{ws_user_key}:{up_id}"
            if c4.button("⬇️ Prepare", key=f"prep_ctrl_{up_id}"):
                st.session_state[cache_key] = api.get_user_upload(up_id) or {}
            detail = st.session_state.get(cache_key)
            if detail is not None:
                csv_text = _controls_to_csv(
                    detail.get("controls", []), detail.get("columnNames", [])
                )
                if csv_text:
                    dl_name = fname if fname.lower().endswith(".csv") else f"{fname}.csv"
                    st.download_button(
                        "⬇️ Download CSV",
                        data=csv_text,
                        file_name=dl_name,
                        mime="text/csv",
                        key=f"dl_ctrl_{up_id}",
                    )
                else:
                    st.caption("⚠️ Control rows are no longer available for re-download.")
            st.divider()
    else:
        st.info("No control sets stored yet.")
        if st.button("📁 Load controls", key="ws_goto_upload"):
            st.switch_page("pages/1_Upload_Controls.py")

# Mappings (stream #1)
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
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f"🤖 **{control_name}** <small>({framework})</small>", unsafe_allow_html=True)
            c2.caption(f"Confidence: {conf_str}")
            c3.caption(ts)
            st.divider()
    else:
        st.info("No AI mapping results recorded yet.")
        if st.button("🤖 Go to AI Mapping", key="profile_goto_mapping"):
            st.switch_page("pages/2_AI_Mapping.py")

# Changes (stream #2 — edits, audit-only)
with tab_changes:
    st.markdown("#### Changes You've Made")
    changes = api.get_user_history(limit=50, event_type="edit")
    if changes:
        for item in changes:
            ts = item.get("timestamp", "")[:19].replace("T", " ")
            summary = item.get("summary", "Edit")
            st.markdown(f"✏️ **{summary}** &nbsp; <small style='color:var(--neutral-fg-3)'>{ts}</small>", unsafe_allow_html=True)
            st.divider()
    else:
        st.info("No edits recorded yet. Changes you make in Review & Edit appear here.")

# Policies / exports (stream #4)
with tab_exports:
    st.markdown("#### Policy Exports & Builds")
    exports = api.get_user_exports(limit=50)
    if exports:
        for exp in exports:
            ts = exp.get("timestamp", "")[:19].replace("T", " ")
            fname = exp.get("fileName", "unknown")
            framework = exp.get("framework", "")
            artifact_type = exp.get("artifactType", "")
            count = exp.get("controlCount", 0)
            exp_id = exp.get("id", "")
            has_content = exp.get("contentAvailable", True)
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.markdown(f"📦 **{fname}** <small>({framework} · {artifact_type})</small>", unsafe_allow_html=True)
            c2.caption(f"{count} controls")
            c3.caption(ts)
            cache_key = f"ws_exp:{ws_user_key}:{exp_id}"
            if has_content:
                if c4.button("⬇️ Prepare", key=f"prep_exp_{exp_id}"):
                    st.session_state[cache_key] = api.get_user_export(
                        exp_id, session_id=exp.get("session_id")
                    ) or {}
            else:
                c4.caption("—")
            detail = st.session_state.get(cache_key)
            if detail is not None:
                if detail.get("hasContent"):
                    files = _files_from_envelope(
                        detail.get("content", ""), detail.get("fileName", fname)
                    )
                    dcols = st.columns(min(len(files), 4) or 1)
                    for i, (name, data, mime) in enumerate(files):
                        dcols[i % len(dcols)].download_button(
                            f"⬇️ {name}",
                            data=data,
                            file_name=name,
                            mime=mime,
                            key=f"dl_exp_{exp_id}_{i}",
                        )
                else:
                    reason = detail.get("contentSkippedReason")
                    if reason == "too_large":
                        st.caption("⚠️ Artifact too large to download from the workspace.")
                    else:
                        st.caption("No downloadable content available for this export.")
            st.divider()
    else:
        st.info("No policy exports recorded yet.")
        if st.button("📦 Go to Export", key="profile_goto_export"):
            st.switch_page("pages/4_Export_Policy.py")

render_footer()
render_log_viewer()
render_backend_log_viewer()
