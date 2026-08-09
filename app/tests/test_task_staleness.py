"""Regression tests for the abandoned-task staleness guard in task_manager.

Covers the defect where a poll_backend=False task (e.g. PDF extraction) that
never gets a further update - because the page that owns it was navigated
away from, reloaded, or closed - stayed "running" forever. That made
has_active_task_of_type() return True indefinitely, permanently blocking any
new extraction and surviving both "Clear workspace" and "Clear & Start Over"
in practice, because task_registry is reset by those but was observed to have
already reappeared by the time the next page rendered.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from utils import task_manager


def _stub(monkeypatch, session_state: dict) -> None:
    monkeypatch.setattr(task_manager, "st", SimpleNamespace(session_state=session_state))


def test_recent_frontend_managed_task_is_still_active(monkeypatch):
    state: dict = {}
    _stub(monkeypatch, state)
    task_manager.register_task("job-1", "pdf_extraction", poll_backend=False)

    assert task_manager.has_active_task_of_type("pdf_extraction") is True
    assert len(task_manager.get_active_tasks()) == 1


def test_abandoned_frontend_managed_task_expires_after_30_minutes(monkeypatch):
    state: dict = {}
    _stub(monkeypatch, state)
    task_manager.register_task("job-1", "pdf_extraction", poll_backend=False)
    # Backdate started_at past the staleness ceiling, simulating a task whose
    # owning fragment stopped running long ago.
    old = datetime.now(timezone.utc) - timedelta(seconds=task_manager._STALE_AFTER_SECONDS + 1)
    state["task_registry"]["job-1"]["started_at"] = old.isoformat()

    assert task_manager.has_active_task_of_type("pdf_extraction") is False
    assert task_manager.get_active_tasks() == []

    # Expiring is honest, not silent: the task becomes a real terminal failure
    # with an explanatory error, and gets a notification like any other.
    task = task_manager.get_task("job-1")
    assert task["status"] == "failed"
    assert "abandoned" in task["error"]
    notifications = task_manager.get_task_notifications()
    assert any(n["job_id"] == "job-1" and n["event"] == "failed" for n in notifications)


def test_stale_task_does_not_block_a_fresh_extraction(monkeypatch):
    """The exact user-facing shape of the bug: a second scan must not be
    refused because an old, abandoned task is still "in progress"."""
    state: dict = {}
    _stub(monkeypatch, state)
    task_manager.register_task("stuck-job", "pdf_extraction", poll_backend=False)
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    state["task_registry"]["stuck-job"]["started_at"] = old.isoformat()

    assert task_manager.has_active_task_of_type("pdf_extraction") is False

    task_manager.register_task("new-job", "pdf_extraction", poll_backend=False)
    assert task_manager.has_active_task_of_type("pdf_extraction") is True
    assert len(task_manager.get_active_tasks()) == 1
    assert task_manager.get_active_tasks()[0]["job_id"] == "new-job"


def test_staleness_check_ignores_backend_polled_tasks(monkeypatch):
    """poll_backend=True tasks are actively reconciled elsewhere
    (poll_active_tasks); the staleness guard exists specifically for the
    frontend-managed escape hatch and must not mask a genuinely slow
    backend-polled job as abandoned."""
    state: dict = {}
    _stub(monkeypatch, state)
    task_manager.register_task("job-1", "ai_mapping", poll_backend=True)
    old = datetime.now(timezone.utc) - timedelta(hours=3)
    state["task_registry"]["job-1"]["started_at"] = old.isoformat()

    assert task_manager.has_active_task_of_type("ai_mapping") is True
    task = task_manager.get_task("job-1")
    assert task["status"] == "running"


def test_staleness_check_tolerates_a_missing_or_malformed_started_at(monkeypatch):
    state: dict = {}
    _stub(monkeypatch, state)
    task_manager.register_task("job-1", "pdf_extraction", poll_backend=False)
    state["task_registry"]["job-1"]["started_at"] = "not-a-timestamp"

    # Must not raise; an unparsable timestamp is treated as "not stale" rather
    # than crashing the page that reads active tasks.
    assert task_manager.has_active_task_of_type("pdf_extraction") is True
