"""
Backend Log Viewer component — polls the backend ``/api/v1/health/logs``
endpoint and renders a scrollable, colour-coded log panel.

Usage:
    from components.backend_log_viewer import render_backend_log_viewer
    render_backend_log_viewer()   # call at the bottom of any page
"""

from __future__ import annotations

import streamlit as st

_LEVEL_COLORS = {
    "DEBUG": "gray",
    "INFO": "blue",
    "WARNING": "orange",
    "ERROR": "red",
    "CRITICAL": "red",
}

_LEVEL_ICONS = {
    "DEBUG": "🔍",
    "INFO": "ℹ️",
    "WARNING": "⚠️",
    "ERROR": "❌",
    "CRITICAL": "🔴",
}


def render_job_activity(events: list[dict], waiting_message: str) -> None:
    """Render a bounded, scrollable, job-scoped execution trace."""
    if not events:
        st.caption(waiting_message)
        return

    with st.container(height=200):
        for event in events[-12:]:
            level = event.get("level", "INFO")
            icon = _LEVEL_ICONS.get(level, "ℹ️")
            timestamp = str(event.get("ts", ""))[:19]
            message = " ".join(str(event.get("message", "")).split())[:240]
            st.caption(f"{icon} {timestamp} — {message}")


def render_pdf_backend_activity(job_id: str) -> None:
    """Fetch and render the PDF extraction's dedicated execution trace."""
    cursor_key = f"_pdf_job_log_cursor_{job_id}"
    cache_key = f"_pdf_job_log_cache_{job_id}"
    cursor = st.session_state.setdefault(cursor_key, 0)
    cached_logs = st.session_state.setdefault(cache_key, [])

    try:
        from utils.api_client import get_api_client

        data = get_api_client().get_pipeline_logs(job_id, since=cursor)
        new_logs = data.get("logs", [])
        if new_logs:
            st.session_state[cache_key] = (cached_logs + new_logs)[-50:]
            st.session_state[cursor_key] = data.get("next_cursor", cursor)
    except Exception:
        st.caption("Live extraction events are temporarily unavailable.")
        return

    render_job_activity(
        st.session_state[cache_key],
        "Waiting for the extraction service to report its first event.",
    )


def render_backend_log_viewer() -> None:
    """Render the backend application log panel if the user has toggled it on.

    The viewer polls ``GET /api/v1/health/logs?since=<cursor>`` each time the
    page reruns and stores the cursor in session state for incremental
    fetching.
    """
    if not st.session_state.get("show_backend_logs"):
        return

    # ── Fetch logs from backend ──────────────────────────────────────
    cursor_key = "_backend_log_cursor"
    cache_key = "_backend_log_cache"

    if cursor_key not in st.session_state:
        st.session_state[cursor_key] = 0
    if cache_key not in st.session_state:
        st.session_state[cache_key] = []

    try:
        from utils.api_client import get_api_client

        api = get_api_client()
        level_filter = st.session_state.get("backend_log_level", "INFO")
        data = api.get_backend_logs(
            since=st.session_state[cursor_key],
            level=level_filter,
            limit=200,
        )
        new_logs = data.get("logs", [])
        next_cursor = data.get("next_cursor", st.session_state[cursor_key])

        if new_logs:
            st.session_state[cache_key] = (st.session_state[cache_key] + new_logs)[-500:]
            st.session_state[cursor_key] = next_cursor

    except Exception as exc:
        st.caption(f"⚠️ Could not fetch backend logs: {exc}")
        return

    # ── Render ────────────────────────────────────────────────────────
    logs = st.session_state[cache_key]
    total = data.get("total_buffered", len(logs))

    with st.expander(f"📋 Backend Logs ({len(logs)} / {total} buffered)", expanded=False):
        col_clear, col_level, _ = st.columns([1, 2, 3])
        with col_clear:
            if st.button("🗑️ Clear", key="clear_backend_logs"):
                st.session_state[cache_key] = []
                st.session_state[cursor_key] = 0
                st.rerun()
        with col_level:
            st.selectbox(
                "Level filter",
                options=["DEBUG", "INFO", "WARNING", "ERROR"],
                index=1,
                key="backend_log_level",
            )

        if not logs:
            st.caption("No backend log entries yet.")
            return

        # Show newest first
        for entry in reversed(logs):
            level = entry.get("level", "INFO")
            icon = _LEVEL_ICONS.get(level, "ℹ️")
            color = _LEVEL_COLORS.get(level, "blue")
            ts = entry.get("ts", "")[:19]
            msg = entry.get("message", "")
            logger_name = entry.get("logger", "")

            line = f"{icon} `{ts}` :{color}[**{level}**] `{logger_name}` — {msg}"
            st.markdown(line)
