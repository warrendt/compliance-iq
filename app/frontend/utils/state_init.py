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
    "pdf_extract_task_id": None,
    "pdf_file_bytes": None,
    "pdf_file_name": None,
    "pdf_disable_auto_restore": False,
    "pdf_last_restored_task_id": None,
    "pdf_extract_backend_job_id": None,
    "pdf_extract_backend_status": None,
    "pdf_extract_backend_progress": 0,
    "pdf_extract_backend_stage": None,
    "pdf_backend_sync_last_check": None,
    "pdf_enable_legal_enrichment": False,

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
    "task_view_notice": None,
    "_session_recovery_checked": False,
    "_session_recovery_notice": None,

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

    # Prefer stable session id from URL so session can survive Streamlit reconnects.
    sid_from_url = None
    try:
        sid_from_url = st.query_params.get("sid")
    except Exception:
        sid_from_url = None

    if st.session_state.get("session_uuid") is None:
        if sid_from_url:
            st.session_state["session_uuid"] = str(sid_from_url)
        else:
            st.session_state["session_uuid"] = str(uuid.uuid4())

    # Keep URL in sync with session id for reconnect resilience.
    try:
        if st.query_params.get("sid") != st.session_state["session_uuid"]:
            st.query_params["sid"] = st.session_state["session_uuid"]
    except Exception:
        pass

    # Auto-recover saved session state once per browser session when local state is empty.
    if (
        not st.session_state.get("_session_recovery_checked")
        and not st.session_state.get("controls")
        and not st.session_state.get("mappings")
    ):
        st.session_state["_session_recovery_checked"] = True
        try:
            from utils.api_client import get_api_client

            api_client = get_api_client()
            saved = api_client.load_session(st.session_state["session_uuid"])
            if saved and (saved.get("controls") or saved.get("mappings")):
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
                st.session_state["_session_recovery_notice"] = (
                    f"Recovered saved session with {len(saved.get('controls', []))} controls and "
                    f"{len(saved.get('mappings', []))} mappings."
                )
            if saved and saved.get("pdf_extraction") and not st.session_state.get("pdf_extraction"):
                st.session_state["pdf_extraction"] = saved.get("pdf_extraction")
                st.session_state["pdf_file_name"] = saved.get("pdf_extraction_file_name")
                st.session_state["pdf_extracting"] = False

            if saved:
                st.session_state["pdf_extract_backend_job_id"] = saved.get("pdf_extraction_job_id")
                st.session_state["pdf_extract_backend_status"] = saved.get("pdf_extraction_job_status")
                st.session_state["pdf_extract_backend_progress"] = int(saved.get("pdf_extraction_job_progress") or 0)
                st.session_state["pdf_extract_backend_stage"] = saved.get("pdf_extraction_job_stage")
        except Exception:
            pass
