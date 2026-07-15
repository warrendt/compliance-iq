"""Regression tests for durable backend workflow recovery."""

from app.api.routes.session import _latest_session


def test_latest_session_selects_newest_saved_workflow():
    documents = [
        {"id": "older", "saved_at": "2026-07-13T10:00:00Z"},
        {"id": "newer", "saved_at": "2026-07-13T10:01:00Z"},
    ]

    assert _latest_session(documents)["id"] == "newer"
    assert _latest_session([]) is None
