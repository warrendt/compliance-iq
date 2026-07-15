"""Regression tests for Streamlit workflow state recovery."""

from types import SimpleNamespace

from utils import state_init


def test_restore_workflow_state_recovers_controls_from_latest_user_workflow(monkeypatch):
    streamlit = SimpleNamespace(session_state={"controls": []})
    monkeypatch.setattr(state_init, "st", streamlit)
    state_init.init_session_state()

    saved = {
        "controls": [{"control_id": "CTRL-1"}],
        "mappings": [{"control_id": "CTRL-1", "mcsb_control_id": "MCSB-1"}],
        "framework_name": "Framework",
        "generated_policy": {"initiative_name": "Framework Initiative"},
        "selected_platform": "azure_defender",
    }
    api = SimpleNamespace(load_latest_session=lambda: saved)
    monkeypatch.setattr("utils.api_client.get_api_client", lambda: api)

    state_init.restore_workflow_state()

    assert streamlit.session_state["controls"] == saved["controls"]
    assert streamlit.session_state["mappings"] == saved["mappings"]
    assert streamlit.session_state["framework_name"] == "Framework"
    assert streamlit.session_state["generated_policy"] == saved["generated_policy"]
    assert streamlit.session_state["controls_loaded"] is True
    assert "Restored 1 controls" in streamlit.session_state["workflow_restored_notice"]
