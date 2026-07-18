"""
Page 9: Version History — browse immutable Azure Policy initiative versions
generated from Export Policy or the full-union diff, download their bundles,
and revert.

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
from utils.components import render_page_header
from utils.state_init import init_session_state
from components.task_status_bar import render_task_status_bar

st.set_page_config(
    page_title="Version History | ComplianceIQ",
    page_icon="🛡️",
    layout="wide",
)

inject_azure_theme()
init_session_state()
render_sidebar()
render_task_status_bar()

api = get_api_client()

# ── Header ────────────────────────────────────────────────────────────────────

render_page_header(
    "Version history",
    eyebrow="Report",
    description=(
        "Every generated MCSB initiative, SLZ initiative, and full-union initiative "
        "is saved here as an immutable version. Download a bundle or revert to any "
        "previous version — reverting always creates a new version."
    ),
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
        "No versions yet. Generate an MCSB or SLZ initiative from **Export Policy**, "
        "or build a full-union initiative from **Gap Analysis**."
    )
    st.page_link("pages/4_📦_Export_Policy.py", label="Go to Export Policy", icon="📦")
    render_footer()
    st.stop()

st.caption(f"{len(versions)} version(s) · newest first")

_VERSION_GROUPS = (
    ("mcsb_initiative", "🛡️ MCSB Initiatives"),
    ("slz_initiative", "🏛️ SLZ Initiatives"),
    ("comparison_union", "🎯 Full-Union Initiatives"),
)


def _source(v: dict) -> str:
    return (v.get("metadata") or {}).get("source", "initiative")


def _render_version(v: dict) -> None:
    vid = v.get("id")
    semantic_version = v.get("semantic_version", "1.0.0")
    status = v.get("status", "—")
    parent = v.get("parent_version")
    src = v.get("sourceComparisonId")
    ts = v.get("timestamp", "")
    metadata = v.get("metadata") or {}
    policy_name = metadata.get("policy_name") or metadata.get("framework_name") or "Unnamed policy"
    parent_semantic_version = metadata.get("reverted_from_semantic_version")

    parent_txt = (
        f" · reverted from v{parent_semantic_version or parent}"
        if parent
        else ""
    )
    with st.expander(
        f"📦 {policy_name} · v{semantic_version} · `{status}`{parent_txt}",
        expanded=False,
    ):
        meta_cols = st.columns(4)
        meta_cols[0].metric("Version", semantic_version)
        meta_cols[1].metric("Status", status)
        meta_cols[2].metric("Parent", parent_semantic_version or "—")
        meta_cols[3].metric("Created", (ts or "—")[:19].replace("T", " "))

        if src:
            st.caption(f"Built from comparison `{src}`")

        if metadata:
            st.json(metadata, expanded=False)

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
                    file_name=f"{policy_name.replace(' ', '_')}_v{semantic_version}.zip",
                    mime="application/zip",
                    key=f"zip_{vid}",
                )
                action_cols[2].download_button(
                    "⬇️ Download .json",
                    json.dumps(payload, indent=2).encode("utf-8"),
                    file_name=f"{policy_name.replace(' ', '_')}_v{semantic_version}.json",
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
        if st.button(f"↩️ Revert to v{semantic_version}", key=f"revert_{vid}",
                     help="Creates a new version that copies this bundle."):
            try:
                new_v = api.revert_version(vid)
                st.success(
                    f"✅ Created v{new_v.get('semantic_version', '—')} "
                    f"from v{semantic_version}."
                )
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Revert failed: {exc}")


_grouped_versions = {
    source: [version for version in versions if _source(version) == source]
    for source, _ in _VERSION_GROUPS
}
_populated_groups = [
    (source, label, _grouped_versions[source])
    for source, label in _VERSION_GROUPS
    if _grouped_versions[source]
]
_unknown_versions = [
    version for version in versions
    if _source(version) not in _grouped_versions
]
if _unknown_versions:
    _populated_groups.append(("initiative", "📦 Other Initiatives", _unknown_versions))

for source, label, grouped_versions in _populated_groups:
    st.markdown(f"### {label}")
    st.caption(f"{len(grouped_versions)} version(s) · newest first")
    for version in grouped_versions:
        _render_version(version)

render_footer()
