"""
Unit tests for the shared ComplianceIQ UI component primitives
(``app/frontend/utils/components.py``).

These assert the pure HTML builders and status/confidence decision logic so the
design system can be refactored with confidence and without a running Streamlit.
"""

import pytest

import utils.components as c


# ── status_variant ───────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "kind,expected",
    [
        ("success", "success"),
        ("warning", "warning"),
        ("danger", "danger"),
        ("info", "info"),
        ("neutral", "neutral"),
        ("High Confidence", "success"),
        ("verified", "success"),
        ("needs review", "warning"),
        ("Control Gap", "danger"),
        ("action required", "danger"),
        ("Azure Policy", "info"),
        ("defender recommendation", "info"),
        ("something unknown", "neutral"),
        ("", "neutral"),
    ],
)
def test_status_variant(kind, expected):
    assert c.status_variant(kind) == expected


# ── confidence_status ─────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "score,variant,label",
    [
        (0.95, "success", "High confidence"),
        (0.85, "success", "High confidence"),
        (0.7, "warning", "Needs review"),
        (0.6, "warning", "Needs review"),
        (0.4, "danger", "Low confidence"),
        (0.0, "danger", "Low confidence"),
        (92, "success", "High confidence"),   # percentage input
        (65, "warning", "Needs review"),
        (30, "danger", "Low confidence"),
    ],
)
def test_confidence_status(score, variant, label):
    assert c.confidence_status(score) == (variant, label)


def test_confidence_status_clamps_out_of_range():
    # 150 is treated as a percentage (→1.0) and clamps to high confidence.
    assert c.confidence_status(150)[0] == "success"
    assert c.confidence_status(-0.5)[0] == "danger"


# ── status_badge_html ─────────────────────────────────────────────────────────
def test_status_badge_html_uses_variant_class_and_escapes():
    out = c.status_badge_html("high confidence", "High confidence")
    assert 'class="fluent-badge success"' in out
    assert "High confidence" in out


def test_status_badge_html_escapes_label():
    out = c.status_badge_html("danger", "<script>x</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_status_badge_html_optional_dot():
    assert '<span class="dot">' in c.status_badge_html("info", "x", dot=True)
    assert '<span class="dot">' not in c.status_badge_html("info", "x")


# ── page_header_html ──────────────────────────────────────────────────────────
def test_page_header_html_full():
    out = c.page_header_html("Title", eyebrow="GOVERN", description="Desc")
    assert 'class="ciq-eyebrow"' in out and "GOVERN" in out
    assert 'class="ciq-page-title"' in out and "Title" in out
    assert 'class="ciq-page-desc"' in out and "Desc" in out


def test_page_header_html_title_only_omits_optional():
    out = c.page_header_html("Only title")
    assert "ciq-eyebrow" not in out
    assert "ciq-page-desc" not in out


# ── workflow_stepper_html ─────────────────────────────────────────────────────
def test_workflow_stepper_marks_done_active_and_upcoming():
    out = c.workflow_stepper_html("Enforce")
    # Govern + Map are done, Enforce active, Report neither
    assert out.count("ciq-step done") == 2
    assert "ciq-step active" in out
    for stage in c.LIFECYCLE_STAGES:
        assert stage in out


def test_workflow_stepper_unknown_stage_has_no_active():
    out = c.workflow_stepper_html("Nonexistent")
    assert "active" not in out
    assert "done" not in out


# ── metric / selection / empty ────────────────────────────────────────────────
def test_metric_card_html():
    out = c.metric_card_html("Controls", 61, sub="12 mapped")
    assert "Controls" in out and "61" in out and "12 mapped" in out


def test_selection_card_selected_flag():
    assert "selected" in c.selection_card_html("Azure", selected=True)
    assert "ciq-select-card selected" not in c.selection_card_html("Azure")


def test_selection_card_badges():
    out = c.selection_card_html("Azure", badges=["Recommended", "MCSB"])
    assert "Recommended" in out and "MCSB" in out


def test_empty_state_html():
    out = c.empty_state_html("No controls", "Upload a file to begin")
    assert "No controls" in out and "Upload a file to begin" in out
