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


def test_persist_workflow_state_saves_session(monkeypatch):
    """Regression: persist_workflow_state must not raise NameError.

    Commit a1c247d accidentally dropped the function-local
    ``from utils.api_client import get_api_client`` import while leaving the
    ``get_api_client()`` call, so every persist call raised
    ``NameError: name 'get_api_client' is not defined``. This test injects a
    fake ``utils.api_client`` module and asserts persist resolves the client
    and forwards the workflow payload to ``save_session``.
    """
    saved: dict = {}

    class _FakeClient:
        def save_session(self, session_uuid, payload):
            saved["session_uuid"] = session_uuid
            saved["payload"] = payload

    fake_api_client = types.ModuleType("utils.api_client")
    fake_api_client.get_api_client = lambda: _FakeClient()
    monkeypatch.setitem(sys.modules, "utils.api_client", fake_api_client)

    state_init.init_session_state()
    s = state_init.st.session_state
    s["controls"] = [{"control_id": "A"}]
    s["framework_name"] = "Framework X"

    # Must not raise (was NameError before the fix).
    state_init.persist_workflow_state()

    assert saved["session_uuid"] == s["session_uuid"]
    assert saved["payload"]["controls"] == [{"control_id": "A"}]
    assert saved["payload"]["framework_name"] == "Framework X"
    # All persisted workflow keys are forwarded.
    for key in (
        "controls",
        "mappings",
        "framework_name",
        "policy_decisions",
        "generated_policy",
        "selected_platform",
        "platform_display_name",
    ):
        assert key in saved["payload"]
