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


def test_recover_session_state_returns_true_and_populates(monkeypatch):
    streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(state_init, "st", streamlit)
    state_init.init_session_state()

    saved = {
        "controls": [{"control_id": "CTRL-1"}],
        "mappings": [{"control_id": "CTRL-1"}],
        "framework_name": "FW",
    }
    api = SimpleNamespace(load_latest_session=lambda: saved)

    assert state_init.recover_session_state(api) is True
    assert streamlit.session_state["controls"] == saved["controls"]
    assert streamlit.session_state["controls_loaded"] is True


def test_recover_session_state_skips_when_controls_present(monkeypatch):
    streamlit = SimpleNamespace(session_state={"controls": [{"control_id": "X"}]})
    monkeypatch.setattr(state_init, "st", streamlit)

    called = {"n": 0}

    def _load():
        called["n"] += 1
        return {"controls": [{"control_id": "Y"}]}

    api = SimpleNamespace(load_latest_session=_load)

    assert state_init.recover_session_state(api) is False
    assert called["n"] == 0  # no backend call when a workflow is already loaded


def test_recover_session_state_returns_false_when_empty(monkeypatch):
    streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(state_init, "st", streamlit)
    state_init.init_session_state()

    api = SimpleNamespace(load_latest_session=lambda: {"controls": []})

    assert state_init.recover_session_state(api) is False


def test_clear_workflow_state_resets_and_reissues_uuid(monkeypatch):
    streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(state_init, "st", streamlit)
    state_init.init_session_state()

    streamlit.session_state["controls"] = [{"control_id": "CTRL-1"}]
    streamlit.session_state["mappings"] = [{"control_id": "CTRL-1"}]
    streamlit.session_state["controls_loaded"] = True
    streamlit.session_state["_workflow_restore_checked"] = True
    original_uuid = streamlit.session_state["session_uuid"]

    state_init.clear_workflow_state()

    assert streamlit.session_state["controls"] == []
    assert streamlit.session_state["mappings"] == []
    assert streamlit.session_state["controls_loaded"] is False
    assert "_workflow_restore_checked" not in streamlit.session_state
    assert streamlit.session_state["session_uuid"] != original_uuid
