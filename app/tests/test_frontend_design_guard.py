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


def test_sidebar_uses_compact_brand_lockup_not_gradient_tile():
    """The sidebar top must render a compact icon+wordmark lockup, not the full
    raster logo.png (a rounded app-icon on a gradient canvas) blown up to 220px.
    Guard against reintroducing the "floating icon in a gradient box" look."""
    text = THEME.read_text(encoding="utf-8")
    assert "ciq-brand" in text, "Sidebar brand lockup markup (.ciq-brand) missing"
    assert "ComplianceIQ" in text
    assert "max-width:220px" not in text, (
        "Sidebar still renders the full logo.png gradient tile at 220px"
    )


def test_start_script_supervises_streamlit():
    """start.sh must relaunch Streamlit if it exits so a crash self-heals
    instead of leaving nginx serving a permanent 502 Connection error."""
    start = FRONTEND / "start.sh"
    text = start.read_text(encoding="utf-8")
    assert "while true" in text, "start.sh does not supervise/restart Streamlit"
    assert "streamlit run app.py" in text


def test_notification_bell_sits_inline_with_the_brand_heading():
    """The bell must share a vertically-centered row with the brand lockup so it
    aligns with the heading on the right of the sidebar, not float on its own line."""
    text = THEME.read_text(encoding="utf-8")
    assert 'vertical_alignment="center"' in text, (
        "brand/bell row must use st.columns(..., vertical_alignment='center')"
    )
    brand_idx = text.index('class="ciq-brand"')
    bell_idx = text.index("render_notification_bell()")
    columns_idx = text.rindex("st.columns", 0, brand_idx)
    assert columns_idx < brand_idx < bell_idx, (
        "notification bell should render in the same columns row as the brand lockup"
    )


def test_pdf_extraction_nav_sits_directly_below_upload_controls():
    """Nav order guard: PDF Extraction belongs immediately under Upload Controls."""
    text = THEME.read_text(encoding="utf-8")
    upload_idx = text.index('label="Upload Controls"')
    pdf_idx = text.index('label="PDF Extraction"')
    mapping_idx = text.index('label="AI Mapping"')
    assert upload_idx < pdf_idx < mapping_idx, (
        "PDF Extraction must be listed directly below Upload Controls and above AI Mapping"
    )
