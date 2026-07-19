"""Tests for the shared recommended-policy renderer.

The renderer must show a real description when one exists, but suppress the
Azure "stub" description (which just repeats the name, e.g. ``CMA_0259 - ...``)
in favour of a short category hint so the card doesn't read like a bare ID.
"""
import sys
import types

import pytest


class _FakeSessionState(dict):
    """Supports both ``key in state`` and attribute-free dict access."""


class _FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = _FakeSessionState()
        self.markdown_calls: list[str] = []
        self.caption_calls: list[str] = []
        self.code_calls: list[str] = []

    def markdown(self, text, **_):
        self.markdown_calls.append(text)

    def caption(self, text, **_):
        self.caption_calls.append(text)

    def code(self, text, **_):
        self.code_calls.append(text)


class _FakeApiClient:
    def __init__(self, policies):
        self._policies = policies
        self.calls = 0

    def get_policy_details(self, policy_ids):
        self.calls += 1
        return {"policies": self._policies}


@pytest.fixture
def fake_st(monkeypatch):
    st = _FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    # Import (or reimport) the component against the stubbed streamlit.
    sys.modules.pop("components.policy_display", None)
    from components.policy_display import render_policy_list  # noqa: WPS433
    return st, render_policy_list


def test_stub_description_is_replaced_with_category_hint(fake_st):
    st, render_policy_list = fake_st
    guid = "e750ca06-1824-464a-2cf3-d0fa754d1cb4"
    client = _FakeApiClient({
        guid: {
            "policy_id": guid,
            "display_name": "Establish a secure software development program",
            "description": "CMA_0259 - Establish a secure software development program",
            "description_is_stub": True,
            "category": "Regulatory Compliance",
            "learn_url": f"https://portal.azure.com/#view/x/{guid}",
        }
    })

    render_policy_list(client, [guid])

    joined_captions = " ".join(st.caption_calls)
    # The redundant stub line must NOT be shown...
    assert "CMA_0259 - Establish a secure software development program" not in joined_captions
    # ...but the human-friendly name (with docs link) and a category hint are.
    assert any("Establish a secure software development program" in m for m in st.markdown_calls)
    assert "manual attestation control" in joined_captions
    # GUID is still shown (muted).
    assert any(guid in c for c in st.caption_calls)


def test_rich_description_is_shown(fake_st):
    st, render_policy_list = fake_st
    guid = "0000aaaa-1111-2222-3333-444455556666"
    client = _FakeApiClient({
        guid: {
            "policy_id": guid,
            "display_name": "Audit VMs without disaster recovery configured",
            "description": "Audit virtual machines which do not have disaster recovery configured.",
            "description_is_stub": False,
            "category": "Compute",
            "learn_url": f"https://portal.azure.com/#view/x/{guid}",
        }
    })

    render_policy_list(client, [guid])

    joined_captions = " ".join(st.caption_calls)
    assert "Audit virtual machines which do not have disaster recovery configured." in joined_captions
    assert "manual attestation control" not in joined_captions


def test_unknown_guid_falls_back_to_code(fake_st):
    st, render_policy_list = fake_st
    guid = "dead0000-0000-0000-0000-000000000000"
    client = _FakeApiClient({})  # no details returned

    render_policy_list(client, [guid])

    assert guid in st.code_calls


def test_details_fetched_once_and_cached(fake_st):
    st, render_policy_list = fake_st
    guid = "0000aaaa-1111-2222-3333-444455556666"
    client = _FakeApiClient({
        guid: {"display_name": "X", "description": "d", "description_is_stub": False}
    })

    render_policy_list(client, [guid])
    render_policy_list(client, [guid])

    assert client.calls == 1  # second render served from session_state cache
