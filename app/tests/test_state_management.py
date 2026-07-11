"""Regression tests for workflow state persistence and result hydration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth.azure_ad_auth import User
from app.api.routes import session as session_routes
from utils import auth, state_init, task_manager


class _SessionAPI:
    def __init__(self, current=None, latest=None):
        self.current = current
        self.latest = latest
        self.saved = []

    def load_session(self, session_id):
        return self.current

    def load_latest_session(self):
        return self.latest

    def save_session(self, session_id, payload):
        self.saved.append((session_id, payload))
        return {"status": "saved"}


class _FailingSessionAPI(_SessionAPI):
    def load_latest_session(self):
        raise RuntimeError("backend unavailable")


def test_mutable_defaults_are_not_shared_between_sessions():
    first = {}
    second = {}

    state_init.init_session_state(first)
    state_init.init_session_state(second)
    first["controls"].append({"control_id": "A"})
    first["policy_decisions"]["A"] = "approved"

    assert second["controls"] == []
    assert second["policy_decisions"] == {}


def test_recovery_uses_latest_session_and_keeps_its_id():
    target = {}
    state_init.init_session_state(target)
    api = _SessionAPI(
        latest={
            "session_id": "saved-session",
            "controls": [{"control_id": "A"}],
            "mappings": [],
            "framework_name": "Recovered",
            "mapping_job_id": "job-1",
            "mapping_in_progress": True,
        }
    )

    assert state_init.recover_session_state(api, target) is True
    assert target["session_uuid"] == "saved-session"
    assert target["controls_loaded"] is True
    assert target["mapping_job_id"] == "job-1"
    assert target["mapping_in_progress"] is True
    assert state_init.recover_session_state(api, target) is False


def test_recovery_keeps_active_remapping_job_with_existing_mappings():
    target = {}
    state_init.init_session_state(target)
    api = _SessionAPI(
        latest={
            "session_id": "saved-session",
            "controls": [{"control_id": "A"}],
            "mappings": [{"control_id": "A", "mcsb_control_id": "IM-1"}],
            "mapping_job_id": "replacement-job",
            "mapping_in_progress": True,
        }
    )

    assert state_init.recover_session_state(api, target) is True
    assert target["mapping_job_id"] == "replacement-job"
    assert target["mapping_in_progress"] is True


def test_recovery_recreates_active_mapping_task_on_any_page(monkeypatch):
    target = {}
    state_init.init_session_state(target)
    st_stub = SimpleNamespace(session_state=target)
    monkeypatch.setattr(state_init, "st", st_stub)
    monkeypatch.setattr(task_manager, "st", st_stub)
    monkeypatch.setattr(
        auth,
        "get_current_user",
        lambda: auth.AuthUser("Alice", "alice@example.com", oid="alice-oid"),
    )
    api = _SessionAPI(
        latest={
            "session_id": "saved-session",
            "controls": [{"control_id": "A"}],
            "mappings": [],
            "framework_name": "Recovered",
            "mapping_job_id": "job-1",
            "mapping_in_progress": True,
        }
    )

    assert state_init.recover_session_state(api) is True
    assert task_manager.get_task("job-1")["status"] == "running"


def test_recovery_failure_is_surfaced_without_discarding_local_state():
    target = {}
    state_init.init_session_state(target)
    target["controls"] = [{"control_id": "local"}]

    assert state_init.recover_session_state(_FailingSessionAPI(), target) is False
    assert target["controls"] == [{"control_id": "local"}]
    assert target["session_recovery_error"] == "backend unavailable"


def test_clearing_workflow_removes_transient_file_state():
    target = {}
    state_init.init_session_state(target)
    target.update(
        {
            "uploaded_df": object(),
            "pdf_extraction": {"controls": []},
            "pdf_file_bytes": b"pdf",
            "task_registry": {"job": {"status": "running"}},
        }
    )

    state_init.clear_workflow_state(target)

    assert "uploaded_df" not in target
    assert target["pdf_extraction"] is None
    assert target["pdf_file_bytes"] is None
    assert target["task_registry"] == {}


def test_authenticated_user_change_clears_previous_users_workflow():
    target = {}
    state_init.init_session_state(target)
    target.update(
        {
            "_state_user_id": "alice-oid",
            "_session_recovery_checked": True,
            "controls": [{"control_id": "alice-control"}],
            "mappings": [{"control_id": "alice-control"}],
        }
    )

    changed = state_init.sync_user_state(
        SimpleNamespace(oid="bob-oid", email="bob@example.com"),
        target,
    )

    assert changed is True
    assert target["_state_user_id"] == "bob-oid"
    assert target["_session_recovery_checked"] is False
    assert target["controls"] == []
    assert target["mappings"] == []


def test_sign_out_clears_authenticated_users_workflow():
    target = {}
    state_init.init_session_state(target)
    target.update(
        {
            "_state_user_id": "alice-oid",
            "_session_recovery_checked": True,
            "controls": [{"control_id": "alice-control"}],
        }
    )

    changed = state_init.sync_user_state(None, target)

    assert changed is True
    assert "_state_user_id" not in target
    assert target["_session_recovery_checked"] is False
    assert target["controls"] == []


def test_loading_new_controls_resets_dependent_workflow_state():
    target = {}
    state_init.init_session_state(target)
    old_session_id = target["session_uuid"]
    target.update(
        {
            "mappings": [{"control_id": "old"}],
            "mapping_job_id": "old-job",
            "mapping_in_progress": True,
            "policy_decisions": {"old": "approved"},
            "generated_policy": {"name": "old"},
            "task_registry": {"old-job": {"status": "running"}},
        }
    )

    state_init.load_controls_state(
        [{"control_id": "new"}],
        "New framework",
        source="pdf",
        target=target,
    )

    assert target["session_uuid"] != old_session_id
    assert target["controls"] == [{"control_id": "new"}]
    assert target["mappings"] == []
    assert target["mapping_job_id"] is None
    assert target["mapping_in_progress"] is False
    assert target["policy_decisions"] == {}
    assert target["generated_policy"] is None
    assert target["task_registry"] == {}
    assert target["upload_source"] == "pdf"


def test_completed_mapping_hydrates_and_persists_from_task_poll(monkeypatch):
    target = {}
    state_init.init_session_state(target)
    target.update(
        {
            "controls": [
                {
                    "control_id": "A",
                    "control_name": "Access",
                    "description": "Require MFA",
                    "domain": "Identity",
                }
            ],
            "mapping_job_id": "job-1",
            "mapping_in_progress": True,
        }
    )
    st_stub = SimpleNamespace(session_state=target)
    monkeypatch.setattr(state_init, "st", st_stub)
    monkeypatch.setattr(task_manager, "st", st_stub)
    task_manager.register_task("job-1", "ai_mapping")
    api = _SessionAPI()

    task_manager._apply_mapping_status(
        "job-1",
        {
            "status": "completed",
            "mapped_controls": 1,
            "result": {
                "mappings": [
                    {
                        "external_control_id": "A",
                        "external_control_name": "Access",
                        "mcsb_control_id": "IM-6",
                        "mcsb_control_name": "Strong authentication",
                        "mcsb_domain": "Identity",
                        "confidence_score": 0.95,
                        "reasoning": "Both require MFA.",
                        "mapping_type": "exact",
                    }
                ]
            },
        },
        api,
    )

    assert target["mapping_in_progress"] is False
    assert target["mapping_job_id"] is None
    assert target["mappings"][0]["description"] == "Require MFA"
    assert target["mappings"][0]["mcsb_control_id"] == "IM-6"
    assert api.saved[0][1]["mappings"] == target["mappings"]
    assert task_manager.get_task("job-1")["status"] == "completed"


@pytest.mark.asyncio
async def test_latest_session_is_scoped_to_current_user():
    document = {
        "session_id": "saved-session",
        "userId": "alice@example.com",
        "controls": [{"control_id": "A"}],
        "mappings": [],
        "saved_at": "2026-07-10T10:00:00Z",
    }
    with patch.object(session_routes, "cosmos_client") as cosmos:
        cosmos.database = MagicMock()
        cosmos.ensure_container = AsyncMock()
        cosmos.query_documents = AsyncMock(return_value=[document])

        result = await session_routes.load_latest_session(
            User(oid="alice", email="alice@example.com", name="Alice")
        )

    assert result["session_id"] == "saved-session"
    assert result["controls"] == [{"control_id": "A"}]
    _, kwargs = cosmos.query_documents.call_args
    assert kwargs["parameters"] == [
        {"name": "@userId", "value": "alice@example.com"}
    ]
