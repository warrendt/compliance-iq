"""
Centralized session state initialization for the Streamlit frontend.

All default session state keys and values are defined here as a single source
of truth.  Call ``init_session_state()`` once from ``app.py``; individual pages
no longer need their own ``if 'key' not in st.session_state`` blocks.
"""

import copy
import uuid
from typing import Any, Dict, Optional

import streamlit as st


# ── Default session state schema ──────────────────────────────────────────

SESSION_DEFAULTS: Dict[str, Any] = {
    # Core workflow state
    "controls": [],
    "mappings": [],
    "framework_name": "",
    "country_or_region": "",
    "jurisdiction_profile": {},
    "sovereignty_resolutions": [],
    "controls_loaded": False,

    # Platform selection
    "selected_platform": "azure_defender",
    "platform_display_name": "Microsoft Defender for Cloud",

    # Mapping job tracking
    "job_id": None,
    "mapping_in_progress": False,
    "mapping_job_id": None,
    "mapping_error": None,
    "mapping_completed_notice": None,
    "mapping_persistence_warning": None,

    # PDF pipeline
    "pdf_extraction": None,
    "pdf_extracting": False,
    "pdf_extraction_error": None,
    "pdf_extract_task_id": None,
    "pdf_extraction_task_to_view": None,
    "pdf_extraction_restore_disabled": False,
    "pdf_clear_warning": None,
    "pdf_file_bytes": None,
    "pdf_file_name": None,
    "pdf_upload_key": 0,

    # Policy generation
    "generated_policy": None,
    "policy_generated": False,
    "session_uuid": None,  # lazily set to uuid4

    # MCSB cache
    "mcsb_controls": None,

    # Policy decisions (approve / deny per mapping, keyed by control_id)
    "policy_decisions": {},

    # Task manager registry  {job_id -> task_info}
    "task_registry": {},
    "task_notifications": [],

    # Developer tools
    "show_api_logs": False,
    "show_backend_logs": False,
    "backend_log_poll_interval": 10,
}


# Transient keys created ad-hoc by pages (uploads, restore guards) that are not
# part of SESSION_DEFAULTS but must be dropped when starting a new session.
_TRANSIENT_STATE_KEYS = (
    "uploaded_df",
    "workflow_restored_notice",
    "_workflow_restore_checked",
    "session_recovery_error",
    "session_save_error",
    "upload_source",
    "controls_upload_key",
    # Column-mapping selections owned by the upload page.
    "control_id_col",
    "control_name_col",
    "description_col",
    "domain_col",
    "column_autodetect_notice",
)


def init_session_state() -> None:
    """Populate ``st.session_state`` with any missing default keys.

    Safe to call on every page — only writes keys that do not already
    exist so existing values are never overwritten.
    """
    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # Lazy UUID — generate once per session
    if st.session_state.get("session_uuid") is None:
        st.session_state["session_uuid"] = str(uuid.uuid4())


def restore_workflow_state() -> None:
    """Restore controls after a Streamlit worker reconnect or restart."""
    if st.session_state.get("controls") or st.session_state.get("_workflow_restore_checked"):
        return

    st.session_state["_workflow_restore_checked"] = True
    try:
        from utils.api_client import get_api_client

        saved = get_api_client().load_latest_session()
    except Exception:
        return

    if not saved or not saved.get("controls"):
        return

    for key in (
        "controls",
        "mappings",
        "framework_name",
        "country_or_region",
        "jurisdiction_profile",
        "sovereignty_resolutions",
        "policy_decisions",
        "generated_policy",
        "selected_platform",
        "platform_display_name",
    ):
        if key in saved:
            st.session_state[key] = saved[key]
    st.session_state["controls_loaded"] = True
    st.session_state["workflow_restored_notice"] = (
        f"Restored {len(saved['controls'])} controls from your latest saved workflow."
    )


def _widget_state_error() -> tuple:
    """Exception type(s) Streamlit raises when a ``session_state`` key bound to
    an already-instantiated widget is reassigned.

    Resolved lazily so the hermetic ``streamlit`` stub used in unit tests (which
    has no ``errors`` submodule) still imports cleanly; falls back to the broad
    ``Exception`` base in that case.
    """
    try:
        from streamlit.errors import StreamlitAPIException

        return (StreamlitAPIException,)
    except Exception:
        return (Exception,)


def _reset_state_key(key: str, default: Any, widget_errors: tuple) -> None:
    """Reset one ``session_state`` key to ``default``.

    Assigns a fresh deep copy of the default. If ``key`` is bound to a widget
    already instantiated this run, Streamlit forbids assignment and raises, so we
    fall back to deleting the key — the widget then re-initialises from its own
    default on the next rerun (the idiomatic widget-reset pattern).
    """
    try:
        st.session_state[key] = copy.deepcopy(default)
    except widget_errors:
        st.session_state.pop(key, None)


def clear_workflow_state(delete_persisted: bool = True) -> None:
    """Reset the workflow to a clean slate for a brand-new session.

    Restores every default key to a fresh (deep-copied) copy of its default so
    no mutable state leaks across sessions, drops transient upload artifacts,
    issues a new ``session_uuid`` so persisted state is kept separate, and
    re-arms the one-shot restore guard so the fresh session is not immediately
    re-hydrated from the backend.

    A new ``session_uuid`` alone is not enough: ``restore_workflow_state`` falls
    back to ``GET /session/latest``, which returns the newest document for the
    user regardless of uuid, so the cleared workspace reappeared on the next
    page load. ``delete_persisted`` therefore also removes the server-side
    documents (best-effort — a backend failure must never block the local
    clear). Pass ``False`` for a purely local reset.

    Widget-backed keys (e.g. ``show_api_logs``) cannot be assigned once their
    widget has been instantiated in the current run, so those are deleted
    instead and re-initialise from their widget defaults on the following rerun.
    The caller is expected to ``st.rerun()`` after clearing.
    """
    if delete_persisted:
        try:
            from utils.api_client import get_api_client

            get_api_client().delete_all_sessions()
        except Exception:
            # Best-effort: the local workspace is still cleared below.
            pass

    # Cancel any active tasks (e.g. a PDF extraction) *before* resetting the
    # registry below, so each gets a real "cancelled" transition and
    # notification rather than silently vanishing. A task's backend job may
    # itself be uncancellable or already gone; that must never block the
    # local reset the user asked for.
    try:
        from utils.task_manager import cancel_task, get_active_tasks

        for task in get_active_tasks():
            cancel_task(task["job_id"], error="Cancelled by clearing the workspace")
    except Exception:
        pass

    widget_errors = _widget_state_error()
    for key, default in SESSION_DEFAULTS.items():
        _reset_state_key(key, default, widget_errors)
    for key in _TRANSIENT_STATE_KEYS:
        st.session_state.pop(key, None)
    st.session_state["session_uuid"] = str(uuid.uuid4())
    st.session_state["_workflow_restore_checked"] = True
    st.session_state["pdf_extraction_restore_disabled"] = True


def persist_workflow_state() -> None:
    """Persist essential workflow inputs as soon as they become usable.

    Best-effort: ``get_api_client`` is imported locally (as in
    :func:`restore_workflow_state`) and any backend failure is swallowed, so a
    transient save problem never surfaces as a misleading "generation failed"
    error on the calling page.
    """
    try:
        from utils.api_client import get_api_client

        get_api_client().save_session(
            st.session_state["session_uuid"],
            {
                "controls": st.session_state.get("controls", []),
                "mappings": st.session_state.get("mappings", []),
                "framework_name": st.session_state.get("framework_name", ""),
                "country_or_region": st.session_state.get("country_or_region", ""),
                "jurisdiction_profile": st.session_state.get("jurisdiction_profile", {}),
                "sovereignty_resolutions": st.session_state.get("sovereignty_resolutions", []),
                "policy_decisions": st.session_state.get("policy_decisions", {}),
                "generated_policy": st.session_state.get("generated_policy"),
                "selected_platform": st.session_state.get("selected_platform", "azure_defender"),
                "platform_display_name": st.session_state.get("platform_display_name", ""),
            },
        )
    except Exception:
        pass  # persistence is best-effort; never break the active workflow


# Keys that carry the user's active workflow (restored / cleared as a unit).
_WORKFLOW_KEYS = (
    "controls",
    "mappings",
    "framework_name",
    "country_or_region",
    "jurisdiction_profile",
    "sovereignty_resolutions",
    "policy_decisions",
    "generated_policy",
    "selected_platform",
    "platform_display_name",
)


def recover_session_state(api_client: Optional[Any] = None) -> bool:
    """Restore the latest saved workflow into ``st.session_state``.

    Attempted at most once per session. Returns ``True`` when controls were
    recovered so the caller can surface a "restored" banner, ``False`` otherwise.
    """
    if st.session_state.get("controls") or st.session_state.get("_workflow_restore_checked"):
        return False

    st.session_state["_workflow_restore_checked"] = True
    try:
        if api_client is None:
            from utils.api_client import get_api_client

            api_client = get_api_client()
        saved = api_client.load_latest_session()
    except Exception:
        return False

    if not saved or not saved.get("controls"):
        return False

    for key in _WORKFLOW_KEYS:
        if key in saved:
            st.session_state[key] = saved[key]
    st.session_state["controls_loaded"] = True
    return True
