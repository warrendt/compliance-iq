"""
Centralized session state initialization for the Streamlit frontend.

All default session state keys and values are defined here as a single source
of truth.  Call ``init_session_state()`` once from ``app.py``; individual pages
no longer need their own ``if 'key' not in st.session_state`` blocks.
"""

import uuid
from typing import Any, Dict

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

    # PDF pipeline
    "pdf_extraction": None,
    "pdf_extracting": False,
    "pdf_file_bytes": None,
    "pdf_file_name": None,

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

    # Developer tools
    "show_api_logs": False,
    "show_backend_logs": False,
    "backend_log_poll_interval": 10,
}


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
