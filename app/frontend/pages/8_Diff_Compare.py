"""
Page 8: Diff Compare — compare an internal control set (uploaded PDF) against an
external regulatory framework and bucket every control as matched / partial /
gap / extra.

Flow: pick an external framework → upload the internal PDF → run. The job runs
on the backend; this page polls its status and renders a colour-coded diff.
"""

import time

import pandas as pd
import streamlit as st

from utils.api_client import get_api_client
from utils.theme import inject_azure_theme, render_sidebar, render_footer
from utils.components import render_page_header
from utils.state_init import init_session_state
from components.task_status_bar import render_task_status_bar

st.set_page_config(
    page_title="Gap Analysis | ComplianceIQ",
    page_icon="🛡️",
    layout="wide",
)

inject_azure_theme()
render_sidebar()
init_session_state()
render_task_status_bar()

api = get_api_client()

# ── Bucket presentation ───────────────────────────────────────────────────────

_BUCKETS = ["matched", "partial-overlap", "gap", "extra"]
_BUCKET_META = {
    "matched": {"label": "Matched", "variant": "success", "color": "#15803D",
                "help": "Internal control fully covered by the external framework."},
    "partial-overlap": {"label": "Partial", "variant": "warning", "color": "#B45309",
                        "help": "Internal control only partially covered."},
    "gap": {"label": "Gap", "variant": "danger", "color": "#B42318",
            "help": "Internal control with no external equivalent."},
    "extra": {"label": "Extra", "variant": "info", "color": "#2563EB",
              "help": "External control with no internal equivalent."},
}

# ── Header ────────────────────────────────────────────────────────────────────

render_page_header(
    "Gap analysis",
    eyebrow="Report",
    description=(
        "See how your internal controls measure up against an external framework — "
        "what is matched, partially covered, missing, or extra."
    ),
)

# ── Session keys ──────────────────────────────────────────────────────────────

st.session_state.setdefault("cmp_id", None)
st.session_state.setdefault("cmp_status", None)
st.session_state.setdefault("cmp_result", None)
st.session_state.setdefault("cmp_building", None)

# ── Step 1: choose external framework ─────────────────────────────────────────

st.markdown("### 1️⃣ Choose an external framework")

frameworks = api.list_comparison_frameworks()
if not frameworks:
    st.warning(
        "No external frameworks are available. Ensure the backend is reachable and "
        "catalogue files are bundled."
    )
    render_footer()
    st.stop()

fw_labels = {
    f["key"]: f"{f['display_name']} ({f.get('control_count', 0)} controls)"
    for f in frameworks
}
selected_key = st.selectbox(
    "External framework",
    options=list(fw_labels.keys()),
    format_func=lambda k: fw_labels.get(k, k),
    help="The regulatory framework to compare your internal controls against.",
)

# ── Step 2: upload internal PDF ───────────────────────────────────────────────

st.markdown("### 2️⃣ Upload your internal controls (PDF)")

uploaded = st.file_uploader(
    "Internal control document",
    type=["pdf"],
    help="A PDF of your organisation's own policy / control set.",
)

run_disabled = uploaded is None or st.session_state.cmp_status in ("pending", "running")
if st.button("🔀 Run comparison", type="primary", use_container_width=True, disabled=run_disabled):
    try:
        with st.spinner("Submitting comparison job..."):
            resp = api.run_comparison(uploaded.getvalue(), uploaded.name, selected_key)
        st.session_state.cmp_id = resp.get("comparison_id")
        st.session_state.cmp_status = resp.get("status", "pending")
        st.session_state.cmp_result = None
        st.rerun()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to start comparison: {exc}")

# ── Step 3: poll status / render result ───────────────────────────────────────

cmp_id = st.session_state.cmp_id
if cmp_id:
    st.markdown("---")
    st.markdown("### 3️⃣ Comparison")

    status = st.session_state.cmp_status
    if status in ("pending", "running", None):
        try:
            poll = api.get_comparison_status(cmp_id)
        except Exception as exc:  # noqa: BLE001 — stop the loop, don't trap the user
            st.error(
                f"Could not fetch comparison status: {exc}. "
                "The job may have expired or is unavailable."
            )
            if st.button("🆕 Start over"):
                st.session_state.cmp_id = None
                st.session_state.cmp_status = None
                st.session_state.cmp_result = None
                st.rerun()
            st.stop()
        status = poll.get("status", status or "pending")
        st.session_state.cmp_status = status
        stage = poll.get("stage", "")

        if status in ("pending", "running"):
            stage_labels = {
                "queued": "Queued…",
                "extracting_text": "Reading the PDF…",
                "extracting_controls": "Extracting internal controls…",
                "comparing": "Comparing against the external framework…",
            }
            st.info(f"⏳ {stage_labels.get(stage, 'Working…')}")
            st.progress(
                {"queued": 10, "extracting_text": 30, "extracting_controls": 55,
                 "comparing": 80}.get(stage, 20) / 100
            )
            if st.button("🔄 Refresh"):
                st.rerun()
            time.sleep(2.5)
            st.rerun()
        elif status == "failed":
            st.error(f"❌ Comparison failed: {poll.get('error') or 'Unknown error'}")

    # Load the full result for any completed comparison (incl. reopened history).
    if status == "completed" and st.session_state.cmp_result is None:
        try:
            st.session_state.cmp_result = api.get_comparison(cmp_id)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not load result: {exc}")

    result = st.session_state.cmp_result
    if status == "completed" and result:
        data = result.get("result", {}) or {}
        counts = result.get("counts", {}) or {}
        matches = data.get("matches", []) or []

        # Header metadata
        meta_cols = st.columns(4)
        meta_cols[0].metric("Internal framework", data.get("internal_framework", "—"))
        meta_cols[1].metric("External framework", data.get("external_framework", "—"))
        meta_cols[2].metric("Internal controls", data.get("internal_count", 0))
        meta_cols[3].metric("External controls", data.get("external_count", 0))

        if data.get("summary"):
            st.info(data["summary"])

        # Colour-coded bucket counts
        st.markdown("#### Coverage")
        cols = st.columns(len(_BUCKETS))
        for col, bucket in zip(cols, _BUCKETS):
            meta = _BUCKET_META[bucket]
            col.metric(meta['label'], counts.get(bucket, 0),
                       help=meta["help"])

        # Filter + table
        st.markdown("#### Details")
        selected_buckets = st.multiselect(
            "Show buckets",
            options=_BUCKETS,
            default=_BUCKETS,
            format_func=lambda b: _BUCKET_META[b]['label'],
        )
        rows = [m for m in matches if m.get("bucket") in selected_buckets]
        if rows:
            df = pd.DataFrame([
                {
                    "Bucket": _BUCKET_META.get(m.get('bucket'), {}).get(
                        'label', m.get('bucket')),
                    "Internal ID": m.get("internal_control_id") or "—",
                    "Internal control": m.get("internal_control_title") or "—",
                    "External ID": m.get("external_control_id") or "—",
                    "External control": m.get("external_control_name") or "—",
                    "Similarity": round(float(m.get("similarity") or 0.0), 2),
                    "Rationale": m.get("rationale") or "",
                }
                for m in rows
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Download as CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name=f"comparison_{cmp_id}.csv",
                mime="text/csv",
            )
        else:
            st.caption("No controls in the selected buckets.")

        # ── Build Azure Policy initiative (full union) ────────────────────────
        st.markdown("---")
        st.markdown("#### 🏗️ Build Azure Policy initiative")
        st.caption(
            "Generate a Defender for Cloud initiative from the **full union** — all "
            "your internal controls plus the external-only controls — and save it as "
            "an immutable version you can revert to later."
        )

        # Seed build state from the persisted comparison doc, unless a poll is active.
        build_status = result.get("buildStatus", "none")
        build_version_id = result.get("buildVersionId")
        build_version_number = result.get("buildVersionNumber")
        build_error = result.get("buildError")

        paused_key = f"build_poll_paused_{cmp_id}"
        # Poll while our flag is set OR the persisted doc says "building" (e.g. the
        # user navigated away and back, losing the in-memory flag) — unless paused
        # after a transient poll failure.
        poll_active = (
            st.session_state.cmp_building == cmp_id
            or (build_status == "building" and not st.session_state.get(paused_key))
        )

        if poll_active:
            st.session_state.cmp_building = cmp_id
            try:
                bpoll = api.get_build_status(cmp_id)
                build_status = bpoll.get("buildStatus", "building")
                build_version_id = bpoll.get("buildVersionId")
                build_version_number = bpoll.get("buildVersionNumber")
                build_error = bpoll.get("buildError")
            except Exception as exc:  # noqa: BLE001 — transient poll failure, not a build failure
                st.session_state.cmp_building = None
                st.session_state[paused_key] = True
                st.warning(
                    f"Couldn't fetch build status: {exc}. The build may still be "
                    "running on the server."
                )
                if st.button("🔄 Resume checking", key=f"resume_{cmp_id}"):
                    st.session_state[paused_key] = False
                    st.rerun()
            else:
                if build_status == "building":
                    st.info("⏳ Building initiative… mapping controls to Azure Policy. "
                            "This can take a minute.")
                    time.sleep(2.5)
                    st.rerun()
                else:
                    # Build finished — refresh the cached doc and clear the poll flag.
                    st.session_state.cmp_building = None
                    try:
                        st.session_state.cmp_result = api.get_comparison(cmp_id)
                    except Exception:  # noqa: BLE001
                        pass

        if build_status == "completed" and build_version_id:
            st.success(
                f"✅ Initiative built as **version {build_version_number}**."
            )
            st.page_link(
                "pages/9_Version_History.py",
                label="Open Version History",
                icon="🗂",
            )
        elif build_status == "failed":
            st.error(f"❌ Initiative build failed: {build_error or 'Unknown error'}")
            if st.button("🔁 Retry build", use_container_width=True):
                try:
                    api.build_initiative(cmp_id)
                    st.session_state[paused_key] = False
                    st.session_state.cmp_building = cmp_id
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not start build: {exc}")
        elif build_status == "building":
            # Paused after a poll failure — the warning + resume button above stands.
            pass
        else:
            if st.button("🏗️ Build initiative (full union)", type="primary",
                         use_container_width=True):
                try:
                    resp = api.build_initiative(cmp_id)
                    st.session_state[paused_key] = False
                    if resp.get("buildStatus") == "completed" and resp.get("buildVersionId"):
                        st.session_state.cmp_result = api.get_comparison(cmp_id)
                    else:
                        st.session_state.cmp_building = cmp_id
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not start build: {exc}")

        st.markdown("---")
        if st.button("🆕 Start a new comparison"):
            st.session_state.cmp_id = None
            st.session_state.cmp_status = None
            st.session_state.cmp_result = None
            st.session_state.cmp_building = None
            st.rerun()

# ── Previous comparisons ──────────────────────────────────────────────────────

st.markdown("---")
with st.expander("🕓 Previous comparisons"):
    history = api.list_comparisons()
    if not history:
        st.caption("No previous comparisons yet.")
    else:
        for item in history:
            c = item.get("counts", {}) or {}
            summary = " · ".join(
                f"{_BUCKET_META[b]['label']}: {c.get(b, 0)}" for b in _BUCKETS
            )
            label = (
                f"**{item.get('externalFrameworkName') or item.get('externalFramework', '?')}** "
                f"vs *{item.get('internalFileName', '?')}* — `{item.get('status', '?')}`"
            )
            cols = st.columns([5, 3, 2])
            cols[0].markdown(label)
            cols[1].caption(summary if item.get("status") == "completed" else "")
            if cols[2].button("Open", key=f"open_{item.get('id')}"):
                st.session_state.cmp_id = item.get("id")
                st.session_state.cmp_status = item.get("status")
                st.session_state.cmp_result = None
                st.session_state.cmp_building = None
                st.rerun()

render_footer()
