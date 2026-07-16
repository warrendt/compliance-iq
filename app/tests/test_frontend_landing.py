"""
Unit tests for the branded landing page and its auth gate.
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


# -- Pure gate decision -------------------------------------------------------

@pytest.mark.parametrize(
    "easy_auth_active, has_session, expected",
    [
        (True, False, True),    # behind Easy Auth, anonymous -> landing
        (True, True, False),    # behind Easy Auth, signed in -> app
        (False, False, False),  # local dev, anonymous -> no landing (keep app)
        (False, True, False),   # not behind Easy Auth -> never landing
    ],
)
def test_should_show_landing_matrix(easy_auth_active, has_session, expected):
    assert (
        landing.should_show_landing(
            easy_auth_active=easy_auth_active, has_session=has_session
        )
        is expected
    )


# -- Easy Auth activation detection -------------------------------------------

def test_is_easy_auth_active_explicit_override_true(monkeypatch):
    monkeypatch.setenv("EASY_AUTH_ENABLED", "true")
    monkeypatch.delenv("CONTAINER_APP_NAME", raising=False)
    monkeypatch.delenv("ENABLE_AUTH", raising=False)
    assert landing.is_easy_auth_active() is True


def test_is_easy_auth_active_explicit_override_false(monkeypatch):
    monkeypatch.setenv("EASY_AUTH_ENABLED", "false")
    monkeypatch.setenv("CONTAINER_APP_NAME", "ca-frontend")
    monkeypatch.setenv("ENABLE_AUTH", "true")
    assert landing.is_easy_auth_active() is False


def test_is_easy_auth_active_true_in_container_app_with_auth(monkeypatch):
    monkeypatch.delenv("EASY_AUTH_ENABLED", raising=False)
    monkeypatch.setenv("CONTAINER_APP_NAME", "ca-frontend")
    monkeypatch.setenv("ENABLE_AUTH", "true")
    assert landing.is_easy_auth_active() is True


def test_is_easy_auth_active_false_when_not_in_container_app(monkeypatch):
    monkeypatch.delenv("EASY_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("CONTAINER_APP_NAME", raising=False)
    monkeypatch.setenv("ENABLE_AUTH", "true")
    assert landing.is_easy_auth_active() is False


def test_is_easy_auth_active_false_when_auth_not_configured(monkeypatch):
    monkeypatch.delenv("EASY_AUTH_ENABLED", raising=False)
    monkeypatch.setenv("CONTAINER_APP_NAME", "ca-frontend")
    monkeypatch.setenv("ENABLE_AUTH", "false")
    assert landing.is_easy_auth_active() is False


# -- require_login gate --------------------------------------------------------

def test_require_login_returns_for_authenticated_user(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(landing, "st", st_stub)
    monkeypatch.setattr(landing, "is_easy_auth_active", lambda: True)
    monkeypatch.setattr(landing, "has_easy_auth_session", lambda: True)

    assert landing.require_login() is None
    assert st_stub.markdown_calls == []  # landing page not rendered


def test_require_login_is_noop_in_local_dev(monkeypatch):
    """Without Easy Auth in front (local dev) the gate must not fire."""
    st_stub = _streamlit_stub()
    monkeypatch.setattr(landing, "st", st_stub)
    monkeypatch.setattr(landing, "is_easy_auth_active", lambda: False)
    monkeypatch.setattr(landing, "has_easy_auth_session", lambda: False)

    assert landing.require_login() is None
    assert st_stub.markdown_calls == []  # app renders as before


def test_require_login_renders_and_stops_for_anonymous_user(monkeypatch):
    st_stub = _streamlit_stub()
    monkeypatch.setattr(landing, "st", st_stub)
    monkeypatch.setattr(landing, "is_easy_auth_active", lambda: True)
    monkeypatch.setattr(landing, "has_easy_auth_session", lambda: False)

    with pytest.raises(_StopRendering):
        landing.require_login()

    body = "\n".join(st_stub.markdown_calls)
    assert "Sign in with Entra ID" in body
    assert landing.PRODUCT_NAME in body


# -- Landing page rendering ----------------------------------------------------

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
    monkeypatch.setattr(
        landing.Path, "read_bytes", lambda self: (_ for _ in ()).throw(OSError())
    )

    assert landing._logo_data_uri() == ""
    landing._logo_data_uri.cache_clear()


def test_logo_data_uri_reads_committed_icon():
    """The committed hero asset resolves to a PNG data URI."""
    landing._logo_data_uri.cache_clear()
    uri = landing._logo_data_uri()
    landing._logo_data_uri.cache_clear()
    assert uri.startswith("data:image/png;base64,")
    assert landing._LOGO_PATH.name == "logo-icon.png"
