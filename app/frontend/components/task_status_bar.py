"""
Task Status Bar component — renders an always-visible compact bar showing
active background tasks and allows expanding into a full task list.

Usage:
    from components.task_status_bar import render_task_status_bar
    render_task_status_bar()   # call near the top of any page
"""

from __future__ import annotations

import streamlit as st

from utils.task_manager import (
    get_active_tasks,
    get_all_tasks,
    poll_active_tasks,
    remove_task,
)


_TYPE_LABELS = {
    "ai_mapping": "🤖 AI Mapping",
    "pdf_extraction": "📄 PDF Extraction",
    "pipeline_run": "🚀 Pipeline",
    "policy_generation": "📦 Policy Generation",
}

_STATUS_ICONS = {
    "pending": "⏳",
    "running": "🔄",
    "completed": "✅",
    "failed": "❌",
    "cancelled": "⏹️",
}

_PAGE_MAP = {
    "ai_mapping": "pages/2_🤖_AI_Mapping.py",
    "pdf_extraction": "pages/5_🚀_PDF_Pipeline.py",
    "pipeline_run": "pages/5_🚀_PDF_Pipeline.py",
    "policy_generation": "pages/4_📦_Export_Policy.py",
}


def render_task_status_bar() -> None:
    """Render a compact task status indicator and an expandable task list.

    Call this near the top of every page *after* ``render_sidebar()``.
    When there are active tasks it polls the backend for updates and
    schedules a rerun after a short interval.
    """
    all_tasks = get_all_tasks()
    active_tasks = get_active_tasks()

    if not all_tasks:
        return  # nothing to show

    # ── Poll active tasks ────────────────────────────────────────────
    if active_tasks:
        try:
            from utils.api_client import get_api_client

            poll_active_tasks(get_api_client())
            # Refresh after poll
            active_tasks = get_active_tasks()
        except Exception:
            pass  # backend may be unavailable

    # ── Compact banner ────────────────────────────────────────────────
    active_count = len(active_tasks)
    if active_count > 0:
        # Build a one-line summary of active tasks
        summaries = []
        for t in active_tasks:
            label = _TYPE_LABELS.get(t["type"], t["type"])
            pct = t.get("progress", 0)
            summaries.append(f"{label} {pct}%")
        banner_text = f"⏳ **{active_count} active task{'s' if active_count != 1 else ''}:** {' · '.join(summaries)}"
        st.info(banner_text)

    # ── Expandable task list ──────────────────────────────────────────
    completed_count = sum(1 for t in all_tasks if t["status"] == "completed")
    failed_count = sum(1 for t in all_tasks if t["status"] == "failed")
    header = f"📋 Tasks ({active_count} active, {completed_count} done, {failed_count} failed)"

    with st.expander(header, expanded=False):
        if not all_tasks:
            st.caption("No tasks recorded yet.")
            return

        for task in all_tasks:
            _render_task_row(task)

        # Bulk clear completed / failed
        col_clear, _ = st.columns([1, 3])
        with col_clear:
            if st.button("🗑️ Clear finished tasks", key="clear_finished_tasks"):
                for t in list(all_tasks):
                    if t["status"] in ("completed", "failed", "cancelled"):
                        remove_task(t["job_id"])
                st.rerun()

    # ── Hint the user to refresh while tasks are active ──────────────
    if active_count > 0:
        st.caption("🔄 Active tasks detected — the page will update on next interaction or navigation.")


def _render_task_row(task: dict) -> None:
    """Render a single task entry inside the expander."""
    icon = _STATUS_ICONS.get(task["status"], "❓")
    label = _TYPE_LABELS.get(task["type"], task["type"])
    pct = task.get("progress", 0)
    stage = task.get("stage", "")
    desc = task.get("description", "")

    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

    with col1:
        title = f"{icon} **{label}**"
        if desc:
            title += f" — {desc}"
        st.markdown(title)

    with col2:
        if task["status"] in ("pending", "running"):
            st.progress(pct / 100, text=f"{pct}%")
        elif task["status"] == "completed":
            st.caption("✅ Done")
        elif task["status"] == "failed":
            err = task.get("error", "Unknown error")
            st.caption(f"❌ {err[:60]}")
        else:
            st.caption(task["status"])

    with col3:
        if stage and task["status"] == "running":
            st.caption(f"Stage: {stage}")
        started = task.get("started_at", "")
        if started:
            st.caption(f"Started: {started[:19]}")

    with col4:
        page = _PAGE_MAP.get(task["type"])
        if task["status"] == "completed" and page:
            if st.button("View", key=f"view_{task['job_id']}"):
                st.switch_page(page)
        elif task["status"] in ("completed", "failed", "cancelled"):
            if st.button("✕", key=f"rm_{task['job_id']}"):
                remove_task(task["job_id"])
                st.rerun()
