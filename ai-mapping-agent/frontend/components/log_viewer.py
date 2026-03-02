"""
API Log Viewer component — renders a scrollable panel of recent API calls.

Usage:
    from components.log_viewer import render_log_viewer
    render_log_viewer()   # call at the bottom of any page
"""

import streamlit as st


def render_log_viewer() -> None:
    """Render the API log panel if the user has toggled it on."""
    if not st.session_state.get("show_api_logs"):
        return

    logs = st.session_state.get("api_logs")
    if not logs:
        st.caption("No API calls recorded yet.")
        return

    with st.expander(f"📡 API Logs ({len(logs)} calls)", expanded=False):
        col_clear, _ = st.columns([1, 5])
        with col_clear:
            if st.button("🗑️ Clear", key="clear_api_logs"):
                logs.clear()
                st.rerun()

        for entry in reversed(logs):
            status = entry["status"]
            if status < 300:
                color = "green"
                icon = "✅"
            elif status < 500:
                color = "orange"
                icon = "⚠️"
            else:
                color = "red"
                icon = "❌"

            ts_short = entry["ts"][-9:]  # HH:MM:SSZ
            method = entry["method"]
            # Strip base URL, show path only
            url = entry["url"]
            path = url.split("/api/", 1)[-1] if "/api/" in url else url
            elapsed = entry["elapsed_ms"]

            summary = f"{icon} `{ts_short}` **{method}** /api/{path} → :{color}[{status}] ({elapsed:.0f} ms)"
            with st.expander(summary, expanded=False):
                if entry.get("request_body"):
                    st.markdown("**Request body** (truncated)")
                    st.code(entry["request_body"][:1024], language="json")
                if entry.get("response_body"):
                    st.markdown("**Response body** (truncated)")
                    st.code(entry["response_body"][:1024], language="json")
                if entry.get("error"):
                    st.error(entry["error"])
