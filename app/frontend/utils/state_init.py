"""
Centralized session state initialization for the Streamlit frontend.

All default session state keys and values are defined here as a single source
of truth.  Call ``init_session_state()`` once from ``app.py``; individual pages
no longer need their own ``if 'key' not in st.session_state`` blocks.
"""

import copy
import uuid
from typing import Any, Dict, Mapping, MutableMapping, Optional

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
    "session_save_error": None,
    "session_recovery_error": None,

    # PDF pipeline
    "pdf_extraction": None,
    "pdf_extracting": False,
    "pdf_extract_task_id": None,
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

PERSISTED_STATE_KEYS = (
    "controls",
    "mappings",
    "framework_name",
    "policy_decisions",
    "generated_policy",
    "selected_platform",
    "platform_display_name",
    "mapping_job_id",
    "mapping_in_progress",
)

WORKFLOW_RESET_KEYS = (
    *PERSISTED_STATE_KEYS,
    "controls_loaded",
    "mapping_error",
    "session_save_error",
    "session_recovery_error",
    "pdf_extraction",
    "pdf_extracting",
    "pdf_extract_task_id",
    "pdf_file_bytes",
    "pdf_file_name",
    "policy_generated",
    "task_registry",
)


def _state(target: Optional[MutableMapping[str, Any]] = None) -> MutableMapping[str, Any]:
    return target if target is not None else st.session_state


def init_session_state(target: Optional[MutableMapping[str, Any]] = None) -> None:
    """Populate ``st.session_state`` with any missing default keys.

    Safe to call on every page — only writes keys that do not already
    exist so existing values are never overwritten.
    """
    session = _state(target)
    for key, default in SESSION_DEFAULTS.items():
        if key not in session:
            session[key] = copy.deepcopy(default)

    # Lazy UUID — generate once per session
    if session.get("session_uuid") is None:
        session["session_uuid"] = str(uuid.uuid4())


def session_snapshot(
    target: Optional[MutableMapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return the workflow state persisted by the backend."""
    session = _state(target)
    return {
        key: copy.deepcopy(session.get(key, SESSION_DEFAULTS.get(key)))
        for key in PERSISTED_STATE_KEYS
    }


def restore_session_state(
    saved: Mapping[str, Any],
    target: Optional[MutableMapping[str, Any]] = None,
) -> None:
    """Hydrate a saved backend session into Streamlit state."""
    session = _state(target)
    for key in PERSISTED_STATE_KEYS:
        if key in saved:
            session[key] = copy.deepcopy(saved[key])

    if saved.get("session_id"):
        session["session_uuid"] = saved["session_id"]

    session["controls_loaded"] = bool(session.get("controls"))
    session["mapping_in_progress"] = bool(
        session.get("mapping_in_progress") and session.get("mapping_job_id")
    )
    if session.get("mappings") and not session["mapping_in_progress"]:
        session["mapping_in_progress"] = False
        session["mapping_job_id"] = None
    session["session_save_error"] = None


def recover_session_state(
    api_client: Any,
    target: Optional[MutableMapping[str, Any]] = None,
) -> bool:
    """Restore the latest saved session once per Streamlit browser session."""
    session = _state(target)
    if target is None:
        from utils.auth import get_current_user

        sync_user_state(get_current_user(), session)

    if session.get("_session_recovery_checked"):
        return False

    session["_session_recovery_checked"] = True
    try:
        saved = api_client.load_latest_session()
    except Exception as exc:
        session["session_recovery_error"] = str(exc)
        return False
    session["session_recovery_error"] = None
    if not saved or not (saved.get("controls") or saved.get("mappings")):
        return False

    restore_session_state(saved, session)
    if target is None and session.get("mapping_in_progress"):
        job_id = session.get("mapping_job_id")
        if job_id:
            from utils.task_manager import get_task, register_task

            if get_task(job_id) is None:
                register_task(
                    job_id,
                    "ai_mapping",
                    description=session.get("framework_name", ""),
                    page_origin="pages/2_🤖_AI_Mapping.py",
                    total=len(session.get("controls", [])),
                )
    return True


def sync_user_state(
    user: Any,
    target: Optional[MutableMapping[str, Any]] = None,
) -> bool:
    """Reset browser workflow state when the authenticated principal changes."""
    session = _state(target)
    identity = (user.oid or user.email.lower()) if user else None
    previous_identity = session.get("_state_user_id")
    changed = bool(previous_identity and identity != previous_identity)
    if changed:
        clear_workflow_state(session)
        session["_session_recovery_checked"] = False
    if identity:
        session["_state_user_id"] = identity
    else:
        session.pop("_state_user_id", None)
    return changed


def clear_workflow_state(
    target: Optional[MutableMapping[str, Any]] = None,
) -> None:
    """Start a new local workflow without mutating shared defaults."""
    session = _state(target)
    for key in WORKFLOW_RESET_KEYS:
        session[key] = copy.deepcopy(SESSION_DEFAULTS[key])
    session["session_uuid"] = str(uuid.uuid4())
    session["_session_recovery_checked"] = True
    for key in (
        "uploaded_df",
        "upload_source",
        "control_id_col",
        "control_name_col",
        "description_col",
        "domain_col",
    ):
        session.pop(key, None)


def load_controls_state(
    controls: list[Mapping[str, Any]],
    framework_name: str,
    *,
    source: Optional[str] = None,
    target: Optional[MutableMapping[str, Any]] = None,
) -> None:
    """Start a clean workflow for newly loaded controls."""
    session = _state(target)
    session["session_uuid"] = str(uuid.uuid4())
    session["controls"] = copy.deepcopy(controls)
    session["framework_name"] = framework_name
    session["controls_loaded"] = bool(controls)
    session["mappings"] = []
    session["mapping_in_progress"] = False
    session["mapping_job_id"] = None
    session["mapping_error"] = None
    session["policy_decisions"] = {}
    session["generated_policy"] = None
    session["policy_generated"] = False
    session["task_registry"] = {}
    session["_session_recovery_checked"] = True
    if source is not None:
        session["upload_source"] = source


def normalize_mapping_result(
    result: Mapping[str, Any],
    controls: list[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    """Convert a backend MappingBatch into the frontend mapping shape."""
    controls_by_id = {
        control.get("control_id"): control
        for control in controls
        if control.get("control_id")
    }
    normalized = []
    for raw in result.get("mappings", []):
        control_id = raw.get("external_control_id", raw.get("control_id", "N/A"))
        source = controls_by_id.get(control_id, {})
        normalized.append(
            {
                "control_id": control_id,
                "control_name": raw.get(
                    "external_control_name",
                    raw.get("control_name", source.get("control_name", "N/A")),
                ),
                "description": raw.get("description", source.get("description", "")),
                "domain": raw.get("domain", source.get("domain")),
                "mcsb_control_id": raw.get("mcsb_control_id", "N/A"),
                "mcsb_control_name": raw.get("mcsb_control_name", "N/A"),
                "mcsb_domain": raw.get("mcsb_domain", "N/A"),
                "confidence_score": raw.get("confidence_score", 0.0),
                "reasoning": raw.get("reasoning", ""),
                "azure_policy_ids": raw.get("azure_policy_ids", []),
                "mapping_type": raw.get("mapping_type", "unknown"),
                "sovereignty": raw.get("sovereignty"),
            }
        )
    return normalized


def apply_mapping_result(
    result: Mapping[str, Any],
    target: Optional[MutableMapping[str, Any]] = None,
) -> list[Dict[str, Any]]:
    """Apply a completed mapping result and clear stale in-progress flags."""
    session = _state(target)
    mappings = normalize_mapping_result(result, session.get("controls", []))
    session["mappings"] = mappings
    session["mapping_in_progress"] = False
    session["mapping_job_id"] = None
    session["mapping_error"] = None
    return mappings


def persist_session_state(
    api_client: Any,
    target: Optional[MutableMapping[str, Any]] = None,
) -> bool:
    """Persist workflow state while surfacing, rather than swallowing, failures."""
    session = _state(target)
    try:
        api_client.save_session(session["session_uuid"], session_snapshot(session))
    except Exception as exc:
        session["session_save_error"] = str(exc)
        return False
    session["session_save_error"] = None
    return True
