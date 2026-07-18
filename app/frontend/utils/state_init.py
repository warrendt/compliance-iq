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


def clear_workflow_state() -> None:
    """Reset the workflow to a clean slate for a brand-new session.

    Restores every default key to a fresh (deep-copied) copy of its default so
    no mutable state leaks across sessions, drops transient upload artifacts,
    issues a new ``session_uuid`` so persisted state is kept separate, and
    re-arms the one-shot restore guard so the fresh session is not immediately
    re-hydrated from the backend.
    """
    for key, default in SESSION_DEFAULTS.items():
        st.session_state[key] = copy.deepcopy(default)
    for key in _TRANSIENT_STATE_KEYS:
        st.session_state.pop(key, None)
    st.session_state["session_uuid"] = str(uuid.uuid4())
    st.session_state["_workflow_restore_checked"] = True


def persist_workflow_state() -> None:
    """Persist essential workflow inputs as soon as they become usable."""

    get_api_client().save_session(
        st.session_state["session_uuid"],
        {
            "controls": st.session_state.get("controls", []),
            "mappings": st.session_state.get("mappings", []),
            "framework_name": st.session_state.get("framework_name", ""),
            "policy_decisions": st.session_state.get("policy_decisions", {}),
            "generated_policy": st.session_state.get("generated_policy"),
            "selected_platform": st.session_state.get("selected_platform", "azure_defender"),
            "platform_display_name": st.session_state.get("platform_display_name", ""),
        },
    )


# Keys that carry the user's active workflow (restored / cleared as a unit).
_WORKFLOW_KEYS = (
    "controls",
    "mappings",
    "framework_name",
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
