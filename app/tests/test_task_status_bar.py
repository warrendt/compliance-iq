"""
Unit tests for the Streamlit task status bar.
"""

from types import SimpleNamespace

from components import task_status_bar as status_bar


class _DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _streamlit_stub(rerun_calls: list[str]):
    return SimpleNamespace(
        session_state={},
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        caption=lambda *args, **kwargs: None,
        markdown=lambda *args, **kwargs: None,
        progress=lambda *args, **kwargs: None,
        button=lambda *args, **kwargs: False,
        expander=lambda *args, **kwargs: _DummyContext(),
        columns=lambda spec: [_DummyContext() for _ in spec],
        rerun=lambda: rerun_calls.append("rerun"),
    )


def test_render_task_status_bar_does_not_rerun_for_frontend_managed_tasks(monkeypatch):
    rerun_calls: list[str] = []
    monkeypatch.setattr(status_bar, "st", _streamlit_stub(rerun_calls))
    monkeypatch.setattr(status_bar, "_render_task_row", lambda task: None)
    monkeypatch.setattr(
        status_bar,
        "get_all_tasks",
        lambda: [{"job_id": "pdf-1", "type": "pdf_extraction", "status": "running", "progress": 5, "poll_backend": False}],
    )
    monkeypatch.setattr(
        status_bar,
        "get_active_tasks",
        lambda: [{"job_id": "pdf-1", "type": "pdf_extraction", "status": "running", "progress": 5, "poll_backend": False}],
    )
    monkeypatch.setattr(status_bar, "poll_active_tasks", lambda api_client: 1)
    monkeypatch.setattr(status_bar.time, "sleep", lambda seconds: None)

    monkeypatch.setattr("utils.api_client.get_api_client", lambda: object())

    status_bar.render_task_status_bar()

    assert rerun_calls == []


def test_render_task_status_bar_reruns_for_backend_polled_tasks(monkeypatch):
    rerun_calls: list[str] = []
    monkeypatch.setattr(status_bar, "st", _streamlit_stub(rerun_calls))
    monkeypatch.setattr(status_bar, "_render_task_row", lambda task: None)
    monkeypatch.setattr(
        status_bar,
        "get_all_tasks",
        lambda: [{"job_id": "job-1", "type": "ai_mapping", "status": "running", "progress": 25, "poll_backend": True}],
    )
    monkeypatch.setattr(
        status_bar,
        "get_active_tasks",
        lambda: [{"job_id": "job-1", "type": "ai_mapping", "status": "running", "progress": 25, "poll_backend": True}],
    )
    monkeypatch.setattr(status_bar, "poll_active_tasks", lambda api_client: 1)
    monkeypatch.setattr(status_bar.time, "sleep", lambda seconds: None)

    monkeypatch.setattr("utils.api_client.get_api_client", lambda: object())

    status_bar.render_task_status_bar()

    assert rerun_calls == ["rerun"]


def test_view_completed_mapping_hydrates_before_navigation(monkeypatch):
    events = []
    task = {
        "job_id": "job-1",
        "type": "ai_mapping",
        "status": "completed",
        "progress": 100,
        "result": {"mappings": [{"external_control_id": "A"}]},
    }
    st_stub = _streamlit_stub([])
    st_stub.button = lambda label, **kwargs: label == "View"
    st_stub.switch_page = lambda page: events.append(("switch", page))
    monkeypatch.setattr(status_bar, "st", st_stub)
    monkeypatch.setattr(
        status_bar,
        "apply_mapping_result",
        lambda result: events.append(("hydrate", result)),
    )

    status_bar._render_task_row(task)

    assert events == [
        ("hydrate", task["result"]),
        ("switch", "pages/2_🤖_AI_Mapping.py"),
    ]
