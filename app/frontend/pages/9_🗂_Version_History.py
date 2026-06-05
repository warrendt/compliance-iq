"""
Page 9: Version History — browse the immutable Azure Policy initiative versions
built from the full-union diff, download their artifact bundles, and revert.

Versions are immutable: a "Revert" never mutates the target. It creates a *new*
version that copies the target's bundle, so the lineage is always preserved.
"""

import io
import json
import zipfile

import pandas as pd
import streamlit as st

from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.state_init import init_session_state
from components.task_status_bar import render_task_status_bar

st.set_page_config(
    page_title="Version History | ComplianceIQ",
    page_icon="🛡️",
    layout="wide",
)

inject_azure_theme()
render_sidebar()
init_session_state()
render_task_status_bar()

api = get_api_client()

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown('<div class="main-header">🗂 Version History</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Every initiative you build from a full-union diff is '
    'saved here as an immutable version. Download a bundle or revert to any '
    'previous version — reverting always creates a new version.</div>',
    unsafe_allow_html=True,
)


def _bundle_zip(payload: dict) -> bytes:
    """Pack the artifact files into an in-memory zip."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in payload.get("files", []) or []:
            name = f.get("name") or "artifact.txt"
            zf.writestr(name, f.get("content") or "")
    buf.seek(0)
    return buf.getvalue()


# ── Version list ──────────────────────────────────────────────────────────────

versions = api.list_versions()

if not versions:
    st.info(
        "No versions yet. Run a comparison on the **Gap Analysis** page, then use "
        "**Build initiative (full union)** to create your first version."
    )
    st.page_link("pages/8_🔀_Diff_Compare.py", label="Go to Gap Analysis", icon="🎯")
    render_footer()
    st.stop()

st.caption(f"{len(versions)} version(s) · newest first")

for v in versions:
    vid = v.get("id")
    number = v.get("version_number", "?")
    status = v.get("status", "—")
    parent = v.get("parent_version")
    src = v.get("sourceComparisonId")
    ts = v.get("timestamp", "")

    parent_txt = f" · reverted from v{parent}" if parent else ""
    with st.expander(f"📦 Version {number} · `{status}`{parent_txt}", expanded=False):
        meta_cols = st.columns(4)
        meta_cols[0].metric("Version", number)
        meta_cols[1].metric("Status", status)
        meta_cols[2].metric("Parent", parent if parent is not None else "—")
        meta_cols[3].metric("Created", (ts or "—")[:19].replace("T", " "))

        if src:
            st.caption(f"Built from comparison `{src}`")

        meta = v.get("metadata") or {}
        if meta:
            st.json(meta, expanded=False)

        action_cols = st.columns([2, 2, 2])

        # Download the artifact bundle (lazy — only fetched when expanded & clicked).
        if action_cols[0].button("📥 Load bundle", key=f"load_{vid}"):
            try:
                payload = api.download_version(vid)
                st.session_state[f"bundle_{vid}"] = payload
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not load bundle: {exc}")

        payload = st.session_state.get(f"bundle_{vid}")
        if payload:
            files = payload.get("files", []) or []
            omitted = payload.get("omitted_files", []) or []
            st.caption(f"{len(files)} file(s) in bundle"
                       + (f" · {len(omitted)} omitted (size)" if omitted else ""))
            if files:
                action_cols[1].download_button(
                    "⬇️ Download .zip",
                    _bundle_zip(payload),
                    file_name=f"initiative_v{number}.zip",
                    mime="application/zip",
                    key=f"zip_{vid}",
                )
                action_cols[2].download_button(
                    "⬇️ Download .json",
                    json.dumps(payload, indent=2).encode("utf-8"),
                    file_name=f"initiative_v{number}.json",
                    mime="application/json",
                    key=f"json_{vid}",
                )
                st.dataframe(
                    pd.DataFrame(
                        [{"File": f.get("name"), "Size (chars)": len(f.get("content") or "")}
                         for f in files]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

        # Revert — creates a new version copying this one's bundle.
        st.markdown("---")
        if st.button(f"↩️ Revert to version {number}", key=f"revert_{vid}",
                     help="Creates a new version that copies this bundle."):
            try:
                new_v = api.revert_version(vid)
                st.success(
                    f"✅ Created version {new_v.get('version_number')} "
                    f"from version {number}."
                )
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Revert failed: {exc}")

render_footer()
