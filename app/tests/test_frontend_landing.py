"""
Unit tests for the branded landing page and auth gate.
"""

from types import SimpleNamespace

import pytest

import utils.landing as landing


class _StopRendering(Exception):
    """Sentinel raised by the stubbed ``st.stop`` to halt rendering."""


def _streamlit_stub():
    markdown_calls: list[str] = []

    def _stop():
        raise _StopRendering()

    stub = SimpleNamespace(
        markdown=lambda body, **kwargs: markdown_calls.append(body),
        stop=_stop,
        markdown_calls=markdown_calls,
    )
    return stub


def test_require_login_returns_for_authenticated_user(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(landing, "st", st_stub)
    monkeypatch.setattr(landing, "is_authenticated", lambda: True)

    assert landing.require_login() is None
    assert st_stub.markdown_calls == []  # landing page not rendered


def test_require_login_renders_and_stops_for_anonymous_user(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(landing, "st", st_stub)
    monkeypatch.setattr(landing, "is_authenticated", lambda: False)

    with pytest.raises(_StopRendering):
        landing.require_login()

    body = "\n".join(st_stub.markdown_calls)
    assert "Sign in with Entra ID" in body
    assert landing.PRODUCT_NAME in body


def test_landing_page_links_to_entra_login(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(landing, "st", st_stub)
    monkeypatch.setattr(landing, "get_login_url", lambda path="/": "/.auth/login/aad?x")

    landing.render_landing_page()

    body = "\n".join(st_stub.markdown_calls)
    assert 'href="/.auth/login/aad?x"' in body
    assert 'target="_top"' in body  # break out of any iframe wrapper


def test_landing_page_embeds_logo_when_present(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(landing, "st", st_stub)
    landing._logo_data_uri.cache_clear()
    monkeypatch.setattr(landing, "_logo_data_uri", lambda: "data:image/png;base64,AAA")

    landing.render_landing_page()

    body = "\n".join(st_stub.markdown_calls)
    assert 'src="data:image/png;base64,AAA"' in body


def test_logo_data_uri_missing_file_returns_empty(monkeypatch):
    landing._logo_data_uri.cache_clear()
    monkeypatch.setattr(landing.Path, "read_bytes", lambda self: (_ for _ in ()).throw(OSError()))

    assert landing._logo_data_uri() == ""
    landing._logo_data_uri.cache_clear()
