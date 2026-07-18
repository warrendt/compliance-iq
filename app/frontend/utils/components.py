"""
ComplianceIQ shared UI component primitives.

Pure HTML builders (``*_html``) contain all rendering logic and are unit-testable
without a running Streamlit server. Thin ``render_*`` wrappers emit them via
``st.markdown``. Keeping the two layers separate means status/confidence
decisions and markup can be asserted directly in tests.

Design system: navy ``#0B2545`` (governance/structure) + intelligence blue
``#2563EB`` (action/AI/selected). Status is communicated by labelled chips —
never emoji or ad-hoc per-page colours.
"""

from __future__ import annotations

import html
from typing import Iterable, Optional, Sequence, Tuple

import streamlit as st

# ── Status vocabulary ───────────────────────────────────────────────────────
# Maps a semantic status kind to a ``.fluent-badge`` CSS variant.
_BADGE_VARIANTS = {"success", "warning", "danger", "info", "neutral"}

# Canonical semantic labels → badge variant. Keys are lower-cased.
_STATUS_ALIASES = {
    "high confidence": "success",
    "verified": "success",
    "approved": "success",
    "complete": "success",
    "completed": "success",
    "compliant": "success",
    "mapped": "success",
    "needs review": "warning",
    "medium confidence": "warning",
    "caution": "warning",
    "pending": "warning",
    "in review": "warning",
    "control gap": "danger",
    "action required": "danger",
    "low confidence": "danger",
    "unmapped": "danger",
    "failed": "danger",
    "error": "danger",
    "azure policy": "info",
    "defender recommendation": "info",
    "in progress": "info",
    "info": "info",
}

# Lifecycle stages surfaced in the shell / page steppers.
LIFECYCLE_STAGES: Tuple[str, ...] = ("Govern", "Map", "Enforce", "Report")


def status_variant(kind: str) -> str:
    """Resolve a status kind or semantic label to a badge CSS variant."""
    key = (kind or "").strip().lower()
    if key in _BADGE_VARIANTS:
        return key
    return _STATUS_ALIASES.get(key, "neutral")


def confidence_status(score: float) -> Tuple[str, str]:
    """Map a 0–1 (or 0–100) confidence score to ``(variant, label)``.

    Thresholds: ≥0.85 high confidence, ≥0.6 needs review, else control gap.
    """
    value = float(score)
    if value > 1.0:  # accept percentage inputs
        value = value / 100.0
    value = max(0.0, min(1.0, value))
    if value >= 0.85:
        return "success", "High confidence"
    if value >= 0.6:
        return "warning", "Needs review"
    return "danger", "Low confidence"


# ── Pure HTML builders ──────────────────────────────────────────────────────
def status_badge_html(kind: str, label: str, dot: bool = False) -> str:
    """Return a labelled status chip as HTML."""
    variant = status_variant(kind)
    safe_label = html.escape(str(label))
    dot_html = '<span class="dot"></span>' if dot else ""
    return f'<span class="fluent-badge {variant}">{dot_html}{safe_label}</span>'


def page_header_html(
    title: str,
    eyebrow: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """Return the standard page header (eyebrow → title → description)."""
    parts = ['<div class="ciq-page-header">']
    if eyebrow:
        parts.append(f'<span class="ciq-eyebrow">{html.escape(eyebrow)}</span>')
    parts.append(f'<div class="ciq-page-title">{html.escape(title)}</div>')
    if description:
        parts.append(f'<p class="ciq-page-desc">{html.escape(description)}</p>')
    parts.append("</div>")
    return "".join(parts)


def workflow_stepper_html(active_stage: str,
                          stages: Sequence[str] = LIFECYCLE_STAGES) -> str:
    """Return the Govern → Map → Enforce → Report stepper as HTML.

    Stages before ``active_stage`` render as done, the active stage is
    highlighted, and later stages are muted.
    """
    normalized = [s for s in stages]
    try:
        active_idx = [s.lower() for s in normalized].index(str(active_stage).lower())
    except ValueError:
        active_idx = -1

    chips = []
    for i, stage in enumerate(normalized):
        if active_idx >= 0 and i < active_idx:
            state = "done"
        elif i == active_idx:
            state = "active"
        else:
            state = ""
        chips.append(
            f'<span class="ciq-step {state}">'
            f'<span class="num">{i + 1}</span>{html.escape(stage)}</span>'
        )
    joined = '<span class="ciq-step-sep">›</span>'.join(chips)
    return f'<div class="ciq-stepper">{joined}</div>'


def metric_card_html(label: str, value, sub: Optional[str] = None) -> str:
    """Return a KPI/metric card as HTML."""
    sub_html = f'<p class="ciq-metric-sub">{html.escape(sub)}</p>' if sub else ""
    return (
        '<div class="ciq-metric-card">'
        f'<p class="ciq-metric-label">{html.escape(str(label))}</p>'
        f'<p class="ciq-metric-value">{html.escape(str(value))}</p>'
        f"{sub_html}</div>"
    )


def selection_card_html(title: str, description: str = "",
                        selected: bool = False,
                        badges: Optional[Iterable[str]] = None) -> str:
    """Return a framework/platform selection card as HTML."""
    sel = " selected" if selected else ""
    desc_html = (
        f'<p class="ciq-select-desc">{html.escape(description)}</p>'
        if description else ""
    )
    badge_html = ""
    if badges:
        badge_html = " ".join(status_badge_html("neutral", b) for b in badges)
        badge_html = f'<div style="margin-top:0.5rem">{badge_html}</div>'
    return (
        f'<div class="ciq-select-card{sel}">'
        f'<p class="ciq-select-title">{html.escape(title)}</p>'
        f"{desc_html}{badge_html}</div>"
    )


def empty_state_html(title: str, message: str = "") -> str:
    """Return an empty-state panel as HTML."""
    msg = f"<p>{html.escape(message)}</p>" if message else ""
    return f'<div class="ciq-empty"><h4>{html.escape(title)}</h4>{msg}</div>'


def section_heading_html(text: str) -> str:
    """Return a section heading as HTML."""
    return f'<div class="ciq-section-heading">{html.escape(text)}</div>'


# ── Streamlit render wrappers ───────────────────────────────────────────────
def render_status_badge(kind: str, label: str, dot: bool = False) -> None:
    st.markdown(status_badge_html(kind, label, dot=dot), unsafe_allow_html=True)


def render_confidence_badge(score: float) -> None:
    variant, label = confidence_status(score)
    st.markdown(status_badge_html(variant, label), unsafe_allow_html=True)


def render_page_header(title: str, eyebrow: Optional[str] = None,
                       description: Optional[str] = None) -> None:
    st.markdown(page_header_html(title, eyebrow, description),
                unsafe_allow_html=True)


def render_workflow_stepper(active_stage: str,
                            stages: Sequence[str] = LIFECYCLE_STAGES) -> None:
    st.markdown(workflow_stepper_html(active_stage, stages),
                unsafe_allow_html=True)


def render_metric_card(label: str, value, sub: Optional[str] = None) -> None:
    st.markdown(metric_card_html(label, value, sub), unsafe_allow_html=True)


def render_selection_card(title: str, description: str = "",
                          selected: bool = False,
                          badges: Optional[Iterable[str]] = None) -> None:
    st.markdown(selection_card_html(title, description, selected, badges),
                unsafe_allow_html=True)


def render_section_heading(text: str) -> None:
    st.markdown(section_heading_html(text), unsafe_allow_html=True)


def render_empty_state(title: str, message: str = "") -> None:
    st.markdown(empty_state_html(title, message), unsafe_allow_html=True)
