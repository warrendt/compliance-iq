"""
Task Status Bar component — renders active work and a task notification bell.

Usage:
    from components.task_status_bar import render_task_status_bar
    render_task_status_bar()   # call near the top of any page
"""

from __future__ import annotations

import streamlit as st

from utils.task_manager import (
    dismiss_all_task_notifications,
    dismiss_task_notification,
    get_active_tasks,
    get_task,
    get_task_notifications,
    poll_active_tasks,
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
    "ai_mapping": "pages/2_AI_Mapping.py",
    "pdf_extraction": "pages/5_PDF_Pipeline.py",
    "pipeline_run": "pages/5_PDF_Pipeline.py",
    "policy_generation": "pages/4_Export_Policy.py",
}

_ORIGIN_LABELS = {
    "pdf_pipeline": "PDF Extraction",
    "pages/2_AI_Mapping.py": "AI Mapping",
}

_NOTIFICATION_COLUMN_WIDTHS = [5, 1.5, 0.75]


def render_task_status_bar() -> None:
    """Render active task progress and a dismissible task notification bell.

    Call this near the top of every page *after* ``render_sidebar()``.
    When there are active tasks it polls the backend for updates. Individual
    workflow pages own their refresh loop so this shared component never
    interrupts page-local progress rendering.
    """
    active_tasks = get_active_tasks()

    # ── Poll active tasks ────────────────────────────────────────────
    if active_tasks:
        try:
            from utils.api_client import get_api_client

            poll_active_tasks(get_api_client())
            # Refresh after poll
            active_tasks = get_active_tasks()
        except Exception:
            pass  # backend may be unavailable

    notifications = get_task_notifications()

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

    # ── Notification bell ─────────────────────────────────────────────
    _, bell_column = st.columns([6, 1])
    with bell_column:
        with st.popover(_notification_bell_label(len(notifications))):
            st.markdown("#### Task notifications")
            if notifications:
                for notification in notifications:
                    _render_notification(notification)
                if st.button("Dismiss all", key="dismiss_all_task_notifications"):
                    dismiss_all_task_notifications()
                    st.rerun()
            else:
                st.caption("No task notifications yet.")

    # ── Active task hint ─────────────────────────────────────────────
    # Do not sleep or rerun here. A shared-header rerun aborts the current
    # page before it can render its own progress card and detailed job events.
    backend_polled_active = [t for t in active_tasks if t.get("poll_backend", True)]
    if backend_polled_active:
        st.caption("🔄 Active tasks are updating on their workflow page.")


def _notification_bell_label(notification_count: int) -> str:
    """Return an Azure-style bell label with the retained event count."""
    return "🔔" if notification_count == 0 else f"🔔 {notification_count}"


def _render_notification(notification: dict) -> None:
    """Render one retained lifecycle event inside the notification popover."""
    task = get_task(notification["job_id"])
    event = notification["event"]
    icon = _STATUS_ICONS.get(notification["status"], "🔔")
    label = _TYPE_LABELS.get(notification["type"], notification["type"])
    description = notification["description"] or label
    source = _ORIGIN_LABELS.get(notification["page_origin"], notification["page_origin"] or "this session")

    content_column, view_column, dismiss_column = st.columns(_NOTIFICATION_COLUMN_WIDTHS)
    with content_column:
        st.markdown(f"{icon} **{description}**")
        st.caption(f"{event.capitalize()} · Started on {source} · {notification['occurred_at'][:19]}")
    with view_column:
        page = _PAGE_MAP.get(notification["type"])
        if event == "completed" and task and page:
            if st.button(
                "View",
                key=f"view_notification_{notification['id']}",
                use_container_width=True,
            ):
                _view_task(task, page)
    with dismiss_column:
        if st.button("✕", key=f"dismiss_notification_{notification['id']}"):
            dismiss_task_notification(notification["id"])
            st.rerun()


def _view_task(task: dict, page: str) -> None:
    """Open a completed task result, including PDF extraction restoration."""
    if task["type"] == "pdf_extraction":
        st.session_state["pdf_extraction_task_to_view"] = task["job_id"]
    st.switch_page(page)
    # switch_page is a no-op when View is clicked from the current PDF page.
    st.rerun()
