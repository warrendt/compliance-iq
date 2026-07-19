"""Regression tests for the on-brand success effect that replaced st.balloons().

Two guarantees:
1. No page still calls ``st.balloons()`` (the AI/"copilot"-flavoured confetti we
   deliberately removed).
2. ``success_effect_html`` builds an accessible, brand-green checkmark-ring
   overlay, and ``render_success_effect`` emits it and fires a toast.
"""
from __future__ import annotations

import re
import sys
import types
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
PAGES = FRONTEND / "pages"


def test_no_balloons_in_pages() -> None:
    offenders = [
        p.name
        for p in PAGES.glob("*.py")
        if re.search(r"st\.balloons\s*\(", p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"st.balloons() still present in: {offenders}"


def _load_components():
    """Import utils.components with a stubbed streamlit, capturing toast calls."""
    if str(FRONTEND) not in sys.path:
        sys.path.insert(0, str(FRONTEND))

    calls: dict[str, list] = {"markdown": [], "toast": []}
    stub = types.ModuleType("streamlit")
    stub.markdown = lambda *a, **k: calls["markdown"].append((a, k))  # type: ignore[attr-defined]
    stub.toast = lambda *a, **k: calls["toast"].append((a, k))  # type: ignore[attr-defined]
    sys.modules["streamlit"] = stub

    # Ensure a fresh import against the stub.
    for mod in ("utils.components", "components"):
        sys.modules.pop(mod, None)
    import utils.components as components  # noqa: WPS433 (local import by design)

    return components, calls


def test_success_effect_html_shape() -> None:
    components, _ = _load_components()
    markup = components.success_effect_html("Loaded 42 controls", token="abc123")

    # Uses the brand success token (green), not a rainbow/AI palette.
    assert "var(--status-success" in markup
    # Draws a ring + a checkmark path (the "draw-in tick" animation).
    assert "ciq-success-fx__ring" in markup
    assert "ciq-success-fx__check" in markup
    assert "@keyframes ciq-fx-check" in markup
    # Non-blocking overlay.
    assert "pointer-events:none" in markup
    # Accessible + reduced-motion safe.
    assert 'role="status"' in markup
    assert "prefers-reduced-motion" in markup
    # Token threads through so reruns replay the animation.
    assert 'data-fx="abc123"' in markup


def test_success_effect_html_escapes_message() -> None:
    components, _ = _load_components()
    markup = components.success_effect_html('<script>"x"', token="t")
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup


def test_render_success_effect_emits_markup_and_toast() -> None:
    components, calls = _load_components()
    components.render_success_effect("Initiative generated")

    assert len(calls["markdown"]) == 1
    (args, kwargs) = calls["markdown"][0]
    assert "ciq-success-fx" in args[0]
    assert kwargs.get("unsafe_allow_html") is True

    assert len(calls["toast"]) == 1
    (targs, tkwargs) = calls["toast"][0]
    assert targs[0] == "Initiative generated"
    assert tkwargs.get("icon") == "✅"


def test_render_success_effect_no_toast_when_disabled() -> None:
    components, calls = _load_components()
    components.render_success_effect("hidden", toast=False)
    assert calls["toast"] == []
    assert len(calls["markdown"]) == 1


@pytest.fixture(autouse=True)
def _cleanup_streamlit_stub():
    yield
    sys.modules.pop("streamlit", None)
    sys.modules.pop("utils.components", None)
