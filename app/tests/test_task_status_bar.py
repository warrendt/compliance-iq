"""
Unit tests for the Streamlit task status bar.
"""

from types import SimpleNamespace

from components import task_status_bar as status_bar
from utils import task_manager


class _DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _streamlit_stub(rerun_calls: list[str], popover_labels: list[str] | None = None):
    def popover(label: str):
        if popover_labels is not None:
            popover_labels.append(label)
        return _DummyContext()

    return SimpleNamespace(
        session_state={},
        info=lambda *args, **kwargs: None,
        caption=lambda *args, **kwargs: None,
        markdown=lambda *args, **kwargs: None,
        progress=lambda *args, **kwargs: None,
        button=lambda *args, **kwargs: False,
        popover=popover,
        columns=lambda spec: [_DummyContext() for _ in spec],
        rerun=lambda: rerun_calls.append("rerun"),
    )


def test_render_task_status_bar_does_not_rerun_for_frontend_managed_tasks(monkeypatch):
    rerun_calls: list[str] = []
    monkeypatch.setattr(status_bar, "st", _streamlit_stub(rerun_calls))
    monkeypatch.setattr(status_bar, "get_task_notifications", lambda: [])
    monkeypatch.setattr(
        status_bar,
        "get_active_tasks",
        lambda: [{"job_id": "pdf-1", "type": "pdf_extraction", "status": "running", "progress": 5, "poll_backend": False}],
    )
    monkeypatch.setattr(status_bar, "poll_active_tasks", lambda api_client: 1)
    monkeypatch.setattr("utils.api_client.get_api_client", lambda: object())

    status_bar.render_task_status_bar()

    assert rerun_calls == []


def test_render_task_status_bar_does_not_interrupt_backend_polled_workflow_page(monkeypatch):
    rerun_calls: list[str] = []
    monkeypatch.setattr(status_bar, "st", _streamlit_stub(rerun_calls))
    monkeypatch.setattr(status_bar, "get_task_notifications", lambda: [])
    monkeypatch.setattr(
        status_bar,
        "get_active_tasks",
        lambda: [{"job_id": "job-1", "type": "ai_mapping", "status": "running", "progress": 25, "poll_backend": True}],
    )
    monkeypatch.setattr(status_bar, "poll_active_tasks", lambda api_client: 1)
    monkeypatch.setattr("utils.api_client.get_api_client", lambda: object())

    status_bar.render_task_status_bar()

    assert rerun_calls == []


def test_viewing_completed_pdf_task_selects_its_extraction(monkeypatch):
    selected_pages: list[str] = []
    rerun_calls: list[str] = []
    streamlit = _streamlit_stub(rerun_calls)
    streamlit.switch_page = selected_pages.append
    monkeypatch.setattr(status_bar, "st", streamlit)

    status_bar._view_task(
        {
            "job_id": "pdf-1",
            "type": "pdf_extraction",
        },
        "pages/5_PDF_Pipeline.py",
    )

    assert streamlit.session_state["pdf_extraction_task_to_view"] == "pdf-1"
    assert selected_pages == ["pages/5_PDF_Pipeline.py"]
    assert rerun_calls == ["rerun"]


def test_registering_and_completing_task_records_distinct_notifications(monkeypatch):
    streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(task_manager, "st", streamlit)

    task_manager.register_task(
        "job-1",
        "pdf_extraction",
        description="Extract controls from framework.pdf",
        page_origin="pdf_pipeline",
    )
    task_manager.update_task("job-1", status="running", progress=50)
    task_manager.update_task("job-1", status="completed", progress=100)
    task_manager.update_task("job-1", status="completed", progress=100)

    notifications = task_manager.get_task_notifications()

    assert [notification["event"] for notification in notifications] == ["completed", "started"]
    assert all(notification["job_id"] == "job-1" for notification in notifications)


def test_replacing_pdf_task_id_preserves_notification_actions(monkeypatch):
    streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(task_manager, "st", streamlit)
    task_manager.register_task("temporary-id", "pdf_extraction", page_origin="pdf_pipeline")

    task_manager.replace_task_job_id("temporary-id", "backend-id")

    notification = task_manager.get_task_notifications()[0]
    assert task_manager.get_task("temporary-id") is None
    assert task_manager.get_task("backend-id")["job_id"] == "backend-id"
    assert notification["job_id"] == "backend-id"
    assert notification["id"] == "backend-id:started"


def test_dismissing_notification_keeps_task_result_available(monkeypatch):
    streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(task_manager, "st", streamlit)
    task_manager.register_task("job-1", "ai_mapping", page_origin="pages/2_AI_Mapping.py")
    notification_id = task_manager.get_task_notifications()[0]["id"]

    task_manager.dismiss_task_notification(notification_id)

    assert task_manager.get_task_notifications() == []
    assert task_manager.get_task("job-1") is not None


def test_cancelling_active_task_releases_its_type_and_retains_a_notification(monkeypatch):
    streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(task_manager, "st", streamlit)
    task_manager.register_task("pdf-1", "pdf_extraction", page_origin="pdf_pipeline")

    task_manager.cancel_task("pdf-1", error="Cancelled when the user cleared the PDF workflow")

    assert task_manager.get_task("pdf-1")["status"] == "cancelled"
    assert not task_manager.has_active_task_of_type("pdf_extraction")
    assert [event["event"] for event in task_manager.get_task_notifications()] == [
        "cancelled",
        "started",
    ]


def test_bell_label_includes_retained_notification_count():
    assert status_bar._notification_bell_label(0) == "🔔"
    assert status_bar._notification_bell_label(3) == "🔔 3"


def test_notification_layout_reserves_space_for_view_action():
    assert status_bar._NOTIFICATION_COLUMN_WIDTHS == [5, 1.5, 0.75]


def test_notification_bell_opens_popover_with_count(monkeypatch):
    """The sidebar bell surfaces the retained-notification count in its label."""
    rerun_calls: list[str] = []
    popover_labels: list[str] = []
    monkeypatch.setattr(status_bar, "st", _streamlit_stub(rerun_calls, popover_labels))
    monkeypatch.setattr(status_bar, "get_task_notifications", lambda: [])

    status_bar.render_notification_bell()

    assert popover_labels == ["🔔"]


def test_status_bar_no_longer_renders_the_floating_bell(monkeypatch):
    """Regression: the bell moved to the sidebar, so the page-level status bar
    must not open a notification popover (which previously floated top-right)."""
    rerun_calls: list[str] = []
    popover_labels: list[str] = []
    monkeypatch.setattr(status_bar, "st", _streamlit_stub(rerun_calls, popover_labels))
    monkeypatch.setattr(status_bar, "get_active_tasks", lambda: [])

    status_bar.render_task_status_bar()

    assert popover_labels == []
