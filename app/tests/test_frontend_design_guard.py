"""Deterministic design-system guard tests.

These replace a brittle Playwright screenshot-regression suite: pixel baselines
depend on font rendering and require committing binary blobs to a public repo,
so instead we assert the invariants the design system relies on. They are pure
static checks over source files — fast, hermetic, and CI-safe.
"""

from __future__ import annotations

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
PAGES = FRONTEND / "pages"
THEME = FRONTEND / "utils" / "theme.py"

# Brand tokens that every screen inherits via the shared theme.
BRAND_NAVY = "#0B2545"
BRAND_PRIMARY = "#2563EB"

# Emoji / pictographic ranges we forbid in filenames and nav chrome.
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\uFE0F\u2B00-\u2BFF]"
)


def _page_files() -> list[Path]:
    return sorted(p for p in PAGES.glob("*.py") if p.name != "__init__.py")


def test_page_filenames_are_emoji_free():
    """Page files must not carry emoji — routing slugs and nginx run emoji-free."""
    offenders = [p.name for p in _page_files() if _EMOJI.search(p.name)]
    assert not offenders, f"Emoji found in page filenames: {offenders}"


def test_page_filenames_are_ascii():
    offenders = [p.name for p in _page_files() if not p.name.isascii()]
    assert not offenders, f"Non-ASCII page filenames: {offenders}"


def test_no_literal_reference_to_emoji_page_paths():
    """No source or test file may reference an old emoji page path."""
    root = FRONTEND.parent  # app/
    pattern = re.compile(r'pages[\\/ "\']*[0-9]_[^A-Za-z0-9_]')
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            offenders.append(f"{path.relative_to(root)}: {match.group()!r}")
    assert not offenders, "Emoji page-path references remain:\n" + "\n".join(offenders)


def test_theme_declares_brand_tokens():
    text = THEME.read_text(encoding="utf-8")
    assert BRAND_NAVY in text, "Brand navy token missing from theme"
    assert BRAND_PRIMARY in text, "Brand primary (intelligence blue) token missing from theme"


def test_sidebar_nav_labels_are_emoji_free():
    """The custom sidebar nav (st.page_link) must not embed emoji in labels."""
    text = THEME.read_text(encoding="utf-8")
    label_pattern = re.compile(r'st\.page_link\([^)]*label=["\']([^"\']+)["\']')
    offenders = [
        label for label in label_pattern.findall(text) if _EMOJI.search(label)
    ]
    assert not offenders, f"Emoji in sidebar nav labels: {offenders}"


def test_no_st_image_with_use_container_width():
    """`st.image(use_container_width=...)` crashes on the pinned Streamlit 1.37.0
    (the arg was added to st.image later). Logos must render via HTML data URIs,
    not st.image. Guard against reintroducing the incompatible call."""
    root = FRONTEND
    pattern = re.compile(r"st\.image\((?:[^()]*|\([^()]*\))*use_container_width", re.DOTALL)
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(path.relative_to(root)))
    assert not offenders, (
        "st.image(..., use_container_width=...) is unsupported on Streamlit 1.37.0: "
        + ", ".join(offenders)
    )
