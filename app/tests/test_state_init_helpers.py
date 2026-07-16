"""Unit tests for the simple frontend session-state helpers.

These are hermetic: ``streamlit`` is stubbed with a plain object whose
``session_state`` is a dict, so the tests exercise the pure state logic without
a running Streamlit server. Run this file in isolation (it forces the stub into
``sys.modules``) — see the dedicated CI step.
"""

import sys
import types

# Force a lightweight streamlit stub so ``import streamlit as st`` in
# utils.state_init resolves without the real package. This file is run on its
# own so the stub never leaks into tests that need real streamlit.
_fake_streamlit = types.ModuleType("streamlit")
_fake_streamlit.session_state = {}
sys.modules["streamlit"] = _fake_streamlit

from utils import state_init  # noqa: E402


def setup_function(_):
    # Fresh, isolated session state per test.
    state_init.st.session_state = {}


def test_init_populates_defaults_and_generates_uuid():
    state_init.init_session_state()
    s = state_init.st.session_state
    assert s["controls"] == []
    assert s["controls_loaded"] is False
    assert s["selected_platform"] == "azure_defender"
    assert s["session_uuid"]  # lazily generated


def test_init_does_not_overwrite_existing_values():
    state_init.st.session_state["framework_name"] = "Existing"
    state_init.init_session_state()
    assert state_init.st.session_state["framework_name"] == "Existing"


def test_clear_workflow_state_resets_defaults_and_transient_keys():
    state_init.init_session_state()
    s = state_init.st.session_state
    old_uuid = s["session_uuid"]
    s.update(
        {
            "controls": [{"control_id": "A"}],
            "controls_loaded": True,
            "mappings": [{"control_id": "A"}],
            "generated_policy": {"name": "old"},
            "uploaded_df": object(),
            "workflow_restored_notice": "note",
            "_workflow_restore_checked": True,
        }
    )

    state_init.clear_workflow_state()

    assert s["controls"] == []
    assert s["controls_loaded"] is False
    assert s["mappings"] == []
    assert s["generated_policy"] is None
    assert "uploaded_df" not in s
    assert "workflow_restored_notice" not in s
    # Restore guard is re-armed so the fresh session is not auto-rehydrated.
    assert s["_workflow_restore_checked"] is True
    # A new session id keeps persisted state separate.
    assert s["session_uuid"] and s["session_uuid"] != old_uuid


def test_clear_workflow_state_uses_fresh_mutable_objects():
    state_init.init_session_state()
    s = state_init.st.session_state
    state_init.clear_workflow_state()
    s["controls"].append({"x": 1})
    s["policy_decisions"]["k"] = "v"

    state_init.clear_workflow_state()

    assert s["controls"] == []
    assert s["policy_decisions"] == {}
