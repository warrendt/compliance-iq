"""
Shared Microsoft 365 / Fluent 2 theme & branding for all Streamlit pages.

The styling targets the Microsoft 365 / Defender / Purview shell: a slim
brand-filled suite header, a light neutral left navigation tree with a
selected-state accent bar, and a content canvas built on Fluent 2 design
tokens (color, type ramp, 4-8px corner radii, subtle elevation).

Tokens mirror the Fluent 2 design system. Keep the brand/neutral/semantic
values in sync with the ``[theme]`` block in ``.streamlit/config.toml``.

The public helpers keep their historical names (``inject_azure_theme``,
``render_sidebar``, ``render_footer``) so existing page imports keep working;
``inject_fluent_theme`` is provided as a forward-looking alias.
"""

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

# ── Brand assets ───────────────────────────────────────────────────────────
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_LOGO_ICON_PATH = _ASSETS_DIR / "logo-icon.png"
_LOGO_FULL_PATH = _ASSETS_DIR / "logo.png"


@lru_cache(maxsize=2)
def _logo_data_uri(icon: bool = True) -> str:
    """Return a brand logo as a base64 PNG data URI, or ``""`` if missing."""
    path = _LOGO_ICON_PATH if icon else _LOGO_FULL_PATH
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except OSError:
        return ""


# ── ComplianceIQ brand design tokens + component styling ───────────────────
FLUENT_CSS = """
<style>
    /* ───────────── ComplianceIQ brand design tokens ───────────── */
    :root {
        /* ComplianceIQ shell navy (governance / structure / strong text) */
        --brand-navy:    #0B2545;          /* organising shell colour */
        --brand-navy-2:  #12315A;          /* navy hover / raised navy */
        --brand-navy-3:  #163459;          /* navy accent */

        /* Intelligence blue ramp (action / AI / selected state) */
        --brand-primary: #2563EB;          /* primary action / AI mapping */
        --brand-hover:   #1D4FD7;          /* action hover */
        --brand-pressed: #1A44BB;          /* action pressed */
        --brand-selected:#1D4FD7;
        --brand-tint:    #EAF3FF;          /* light-blue selected surface */
        --brand-tint-2:  #D6E6FF;
        --brand-foreground: #2563EB;       /* link colour */

        /* Neutral ramp (structural majority) */
        --neutral-fg-1:  #0B2545;          /* strong text = brand navy */
        --neutral-fg-2:  #33404F;          /* body text */
        --neutral-fg-3:  #52606D;          /* muted / supporting text */
        --neutral-fg-disabled: #A9B4C0;
        --neutral-bg-1:  #FFFFFF;          /* card / panel surface */
        --neutral-bg-2:  #F1F5FA;          /* layer / nav */
        --neutral-bg-3:  #F8FAFC;          /* app canvas / subtle layer */
        --neutral-bg-4:  #EAF0F7;
        --neutral-stroke-1: #C6D2E1;       /* input / strong divider */
        --neutral-stroke-2: #D9E2EC;       /* card / divider outline */
        --neutral-stroke-subtle: #E6EDF4;

        /* App canvas (page background behind white cards) */
        --app-canvas:    #F8FAFC;

        /* Shared / semantic status colors */
        --status-success:    #15803D;      /* verified / high confidence */
        --status-success-bg: #E7F6ED;
        --status-success-stroke: #A7DFBE;
        --status-warning:    #B45309;      /* needs review */
        --status-warning-bg: #FDF1E3;
        --status-warning-stroke: #F2D0A0;
        --status-danger:     #B42318;      /* control gap / blocking error */
        --status-danger-bg:  #FDECEA;
        --status-danger-stroke: #F3B4AE;
        --status-info:       #2563EB;      /* azure policy / info */
        --status-info-bg:    #EAF3FF;
        --status-info-stroke: #B9D3FB;

        /* Shape — corner radii (small, Fluent uses 4-8px) */
        --radius-sm: 3px;
        --radius-md: 4px;
        --radius-lg: 6px;
        --radius-xl: 8px;
        --radius-pill: 999px;          /* pill shape (Fluent circular) */

        /* Elevation — subtle shadows for cards / flyouts / dialogs */
        --elevation-2: 0 1px 2px rgba(0,0,0,0.12), 0 0 1px rgba(0,0,0,0.10);
        --elevation-4: 0 2px 4px rgba(0,0,0,0.14), 0 0 2px rgba(0,0,0,0.12);
        --elevation-8: 0 4px 8px rgba(0,0,0,0.14), 0 0 2px rgba(0,0,0,0.12);
        --elevation-16: 0 8px 16px rgba(0,0,0,0.14), 0 0 2px rgba(0,0,0,0.12);

        /* Typography — Segoe UI Variable ramp */
        --font-family: "Segoe UI Variable", "Segoe UI", -apple-system,
                       BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;

        /* Suite header */
        --suite-header-height: 48px;
    }

    /* ───────────── Base typography ───────────── */
    html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {
        font-family: var(--font-family);
        color: var(--neutral-fg-1);
    }
    .stApp { background-color: var(--app-canvas); }

    /* Type ramp — keep corners crisp, Fluent weights */
    h1 { font-size: 1.75rem; font-weight: 600; line-height: 2.25rem;
         color: var(--neutral-fg-1); letter-spacing: -0.01em; }
    h2 { font-size: 1.375rem; font-weight: 600; line-height: 1.75rem;
         color: var(--neutral-fg-1); }
    h3 { font-size: 1.125rem; font-weight: 600; line-height: 1.5rem;
         color: var(--neutral-fg-1); }
    h4, h5, h6 { font-weight: 600; color: var(--neutral-fg-2); }
    p, li, label, .stMarkdown { color: var(--neutral-fg-2); }

    /* ───────────── Suite header (ComplianceIQ brand bar) ───────────── */
    header[data-testid="stHeader"] {
        background: var(--brand-navy);
        height: var(--suite-header-height);
        box-shadow: var(--elevation-2);
    }
    header[data-testid="stHeader"]::before {
        content: "ComplianceIQ";
        position: absolute;
        left: 1rem;
        top: 0;
        height: var(--suite-header-height);
        display: flex;
        align-items: center;
        padding-left: 28px;
        background-image: url("__LOGO_ICON_URI__");
        background-repeat: no-repeat;
        background-position: left center;
        background-size: 20px 20px;
        color: #FFFFFF;
        font-family: var(--font-family);
        font-size: 0.95rem;
        font-weight: 600;
        letter-spacing: 0.01em;
        pointer-events: none;
        z-index: 1;
    }
    /* Make the header toolbar icons legible on the brand fill */
    header[data-testid="stHeader"] [data-testid="stToolbar"] button,
    header[data-testid="stHeader"] [data-testid="stToolbar"] svg {
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
    }
    /* Nudge content below the slim suite header */
    [data-testid="stAppViewContainer"] > .main .block-container {
        padding-top: 3.25rem;
        max-width: 1400px;
    }

    /* ───────────── Page header (content canvas largeTitle) ───────────── */
    .main-header {
        font-size: 1.9rem;
        font-weight: 600;
        line-height: 2.4rem;
        color: var(--neutral-fg-1);
        text-align: left;
        letter-spacing: -0.01em;
        margin: 0 0 0.15rem 0;
    }
    .sub-header {
        font-size: 0.95rem;
        text-align: left;
        color: var(--neutral-fg-3);
        margin-bottom: 1.25rem;
    }

    /* ───────────── Left navigation (Fluent vertical nav tree) ───────────── */
    [data-testid="stSidebar"] {
        background: var(--neutral-bg-2);
        border-right: 1px solid var(--neutral-stroke-2);
    }
    [data-testid="stSidebar"] * {
        color: var(--neutral-fg-2);
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4 {
        color: var(--neutral-fg-1) !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: var(--neutral-stroke-subtle);
        margin: 0.6rem 0;
    }
    /* Nav items (st.page_link) — Fluent list rows with selected accent bar */
    [data-testid="stSidebar"] [data-testid="stPageLink"] a,
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
        border-radius: var(--radius-md);
        padding: 0.3rem 0.6rem;
        border-left: 3px solid transparent;
        color: var(--neutral-fg-2) !important;
        transition: background-color 0.1s ease-in, border-color 0.1s ease-in;
    }
    [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
        background-color: var(--neutral-bg-4);
    }
    /* Selected nav item — left accent bar + brand tint fill */
    [data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
    [data-testid="stSidebar"] a[aria-current="page"] {
        background-color: var(--brand-tint) !important;
        border-left: 3px solid var(--brand-primary);
        color: var(--brand-foreground) !important;
        font-weight: 600;
    }
    /* Sidebar metric values use brand accent */
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: var(--brand-primary) !important;
        font-weight: 600;
    }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        color: var(--neutral-fg-3) !important;
    }

    /* ───────────── Buttons (Fluent 2 · canvas/workspace feel) ─────────────
       Tuned to feel like a modern workspace surface (Figma / Linear / Loop /
       Whiteboard): softer corners, a touch more padding, gentle elevation
       on hover, an accessible focus-visible ring, and a tactile press
       micro-interaction. Brand tokens and Streamlit `kind` semantics
       (primary / secondary) are preserved. */
    .stButton > button,
    .stDownloadButton > button,
    .stLinkButton > a,
    [data-testid="stFormSubmitButton"] button {
        border-radius: var(--radius-lg);                /* 6px — workspace softness */
        font-family: var(--font-family);
        font-weight: 600;
        font-size: 0.875rem;
        line-height: 1.25rem;
        padding: 0.45rem 1rem;                          /* tactile target */
        min-height: 34px;
        letter-spacing: 0.005em;
        box-shadow: var(--elevation-2);                 /* subtle lift off canvas */
        transition: background-color 0.12s ease,
                    border-color 0.12s ease,
                    box-shadow 0.12s ease,
                    transform 0.06s ease;
        will-change: transform, box-shadow;
    }
    /* Accessible focus ring (Fluent focus stroke) — keyboard only */
    .stButton > button:focus-visible,
    .stDownloadButton > button:focus-visible,
    .stLinkButton > a:focus-visible,
    [data-testid="stFormSubmitButton"] button:focus-visible {
        outline: none;
        box-shadow: 0 0 0 2px var(--neutral-bg-1),
                    0 0 0 4px var(--brand-primary),
                    var(--elevation-4);
    }

    /* Subtle / secondary button (outline) — default Streamlit kind */
    .stButton > button[kind="secondary"],
    .stDownloadButton > button,
    .stLinkButton > a {
        background-color: var(--neutral-bg-1);
        color: var(--neutral-fg-1);
        border: 1px solid var(--neutral-stroke-1);
    }
    .stButton > button[kind="secondary"]:hover,
    .stDownloadButton > button:hover,
    .stLinkButton > a:hover {
        background-color: var(--neutral-bg-2);
        border-color: var(--neutral-fg-3);
        color: var(--neutral-fg-1);
        box-shadow: var(--elevation-4);
        transform: translateY(-1px);                    /* gentle hover lift */
    }
    .stButton > button[kind="secondary"]:active,
    .stDownloadButton > button:active,
    .stLinkButton > a:active {
        background-color: var(--neutral-bg-3);
        box-shadow: var(--elevation-2);
        transform: translateY(0);                       /* press settle */
    }

    /* Primary / brand button (filled) */
    .stButton > button[kind="primary"],
    [data-testid="stFormSubmitButton"] button {
        background-color: var(--brand-primary);
        border: 1px solid var(--brand-primary);
        color: #FFFFFF;
    }
    .stButton > button[kind="primary"] *,
    .stButton > button[kind="primary"] p,
    [data-testid="stFormSubmitButton"] button *,
    [data-testid="stFormSubmitButton"] button p {
        color: #FFFFFF !important;
    }
    .stButton > button[kind="primary"]:hover,
    [data-testid="stFormSubmitButton"] button:hover {
        background-color: var(--brand-hover);
        border-color: var(--brand-hover);
        box-shadow: var(--elevation-8);
        transform: translateY(-1px);
    }
    .stButton > button[kind="primary"]:active,
    [data-testid="stFormSubmitButton"] button:active {
        background-color: var(--brand-pressed);
        border-color: var(--brand-pressed);
        box-shadow: var(--elevation-2);
        transform: translateY(0);
    }

    /* Disabled — flatten and dim, no lift */
    .stButton > button:disabled,
    .stDownloadButton > button:disabled,
    [data-testid="stFormSubmitButton"] button:disabled {
        background-color: var(--neutral-bg-3) !important;
        color: var(--neutral-fg-disabled) !important;
        border-color: var(--neutral-stroke-2) !important;
        box-shadow: none !important;
        transform: none !important;
        cursor: not-allowed;
    }

    /* ───────────── Inputs / SearchBox / Combobox ───────────── */
    [data-baseweb="input"], [data-baseweb="select"], [data-baseweb="textarea"] {
        border-radius: var(--radius-md) !important;
    }
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        border-radius: var(--radius-md) !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus,
    .stTextArea textarea:focus {
        border-color: var(--brand-primary) !important;
        box-shadow: 0 0 0 1px var(--brand-primary) !important;
    }

    /* ───────────── Tabs (Fluent TabList) ───────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.25rem;
        border-bottom: 1px solid var(--neutral-stroke-2);
    }
    .stTabs [data-baseweb="tab"] {
        font-family: var(--font-family);
        font-weight: 600;
        color: var(--neutral-fg-3);
        border-radius: var(--radius-md) var(--radius-md) 0 0;
    }
    .stTabs [aria-selected="true"] {
        color: var(--brand-primary) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        background-color: var(--brand-primary);
    }

    /* ───────────── Cards / expanders / containers (elevation) ───────────── */
    [data-testid="stExpander"] {
        border: 1px solid var(--neutral-stroke-2);
        border-radius: var(--radius-lg);
        box-shadow: var(--elevation-2);
        background: var(--neutral-bg-1);
    }
    [data-testid="stExpander"] summary { font-weight: 600; }
    [data-testid="stMetric"] {
        background: var(--neutral-bg-1);
        border: 1px solid var(--neutral-stroke-2);
        border-radius: var(--radius-lg);
        padding: 0.75rem 1rem;
        box-shadow: var(--elevation-2);
    }
    /* Bordered containers behave like Fluent cards */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: var(--radius-lg);
    }

    /* ───────────── MessageBar (alerts: info/success/warning/error) ─────── */
    [data-testid="stAlert"] {
        border-radius: var(--radius-md);
        border-left-width: 4px;
        border-left-style: solid;
        box-shadow: none;
    }
    [data-testid="stAlert"][data-baseweb="notification"] { padding: 0.75rem 1rem; }

    /* ───────────── DataGrid / DetailsList (tables) ───────────── */
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        border: 1px solid var(--neutral-stroke-2);
        border-radius: var(--radius-lg);
        overflow: hidden;
    }
    [data-testid="stTable"] thead tr th {
        background: var(--neutral-bg-3);
        color: var(--neutral-fg-2);
        font-weight: 600;
        border-bottom: 1px solid var(--neutral-stroke-1);
    }
    [data-testid="stTable"] tbody tr:hover {
        background: var(--brand-tint);
    }

    /* ───────────── Progress bar (brand) ───────────── */
    .stProgress > div > div > div > div {
        background-color: var(--brand-primary);
    }

    /* ───────────── Badges / pills ───────────── */
    .fluent-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.1rem 0.55rem;
        border-radius: var(--radius-pill);   /* pill shape */
        font-size: 0.75rem;
        font-weight: 600;
        line-height: 1.1rem;
        border: 1px solid transparent;
    }
    .fluent-badge.success { color: var(--status-success);
        background: var(--status-success-bg); border-color: var(--status-success-stroke); }
    .fluent-badge.warning { color: var(--status-warning);
        background: var(--status-warning-bg); border-color: var(--status-warning-stroke); }
    .fluent-badge.danger  { color: var(--status-danger);
        background: var(--status-danger-bg);  border-color: var(--status-danger-stroke); }
    .fluent-badge.info    { color: var(--status-info);
        background: var(--status-info-bg);    border-color: var(--status-info-stroke); }
    .fluent-badge.neutral { color: var(--neutral-fg-2);
        background: var(--neutral-bg-3);      border-color: var(--neutral-stroke-2); }
    /* Optional leading status dot inside a badge */
    .fluent-badge .dot {
        width: 6px; height: 6px; border-radius: 50%;
        background: currentColor; display: inline-block;
    }

    /* ───────────── Shared components (ComplianceIQ primitives) ───────────── */
    /* Page header: eyebrow → title → description */
    .ciq-page-header { margin: 0 0 1.25rem 0; }
    .ciq-eyebrow {
        display: inline-block;
        font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em;
        text-transform: uppercase; color: var(--brand-primary);
        margin-bottom: 0.35rem;
    }
    .ciq-page-title {
        font-size: 1.9rem; font-weight: 600; line-height: 2.4rem;
        color: var(--neutral-fg-1); letter-spacing: -0.01em; margin: 0 0 0.2rem 0;
    }
    .ciq-page-desc {
        font-size: 0.95rem; color: var(--neutral-fg-3);
        margin: 0; max-width: 68ch;
    }

    /* Section heading */
    .ciq-section-heading {
        font-size: 1.05rem; font-weight: 600; color: var(--neutral-fg-1);
        margin: 1.5rem 0 0.6rem 0; padding-bottom: 0.35rem;
        border-bottom: 1px solid var(--neutral-stroke-2);
    }

    /* Lifecycle stepper: Govern → Map → Enforce → Report */
    .ciq-stepper {
        display: flex; align-items: center; flex-wrap: wrap;
        gap: 0.4rem; margin: 0 0 1.25rem 0;
    }
    .ciq-step {
        display: inline-flex; align-items: center; gap: 0.4rem;
        padding: 0.3rem 0.7rem; border-radius: var(--radius-pill);
        font-size: 0.8rem; font-weight: 600;
        background: var(--neutral-bg-3); color: var(--neutral-fg-3);
        border: 1px solid var(--neutral-stroke-2);
    }
    .ciq-step .num {
        display: inline-flex; align-items: center; justify-content: center;
        width: 18px; height: 18px; border-radius: 50%;
        font-size: 0.7rem; background: var(--neutral-stroke-2);
        color: var(--neutral-fg-2);
    }
    .ciq-step.active {
        background: var(--brand-tint); color: var(--brand-primary);
        border-color: var(--status-info-stroke);
    }
    .ciq-step.active .num { background: var(--brand-primary); color: #FFFFFF; }
    .ciq-step.done {
        background: #EAF0F7; color: var(--brand-navy);
        border-color: var(--neutral-stroke-2);
    }
    .ciq-step.done .num { background: var(--brand-navy); color: #FFFFFF; }
    .ciq-step-sep { color: var(--neutral-fg-disabled); font-size: 0.9rem; }

    /* Metric / KPI card */
    .ciq-metric-card {
        background: var(--neutral-bg-1); border: 1px solid var(--neutral-stroke-2);
        border-radius: var(--radius-lg); padding: 1rem 1.1rem;
        box-shadow: var(--elevation-2); height: 100%;
    }
    .ciq-metric-label {
        font-size: 0.78rem; font-weight: 600; letter-spacing: 0.02em;
        text-transform: uppercase; color: var(--neutral-fg-3); margin: 0;
    }
    .ciq-metric-value {
        font-size: 2rem; font-weight: 600; line-height: 2.3rem;
        color: var(--neutral-fg-1); margin: 0.2rem 0;
    }
    .ciq-metric-sub { font-size: 0.82rem; color: var(--neutral-fg-3); margin: 0; }

    /* Selection card (framework / platform choices) */
    .ciq-select-card {
        background: var(--neutral-bg-1); border: 1px solid var(--neutral-stroke-2);
        border-radius: var(--radius-lg); padding: 1rem 1.1rem;
        box-shadow: var(--elevation-2); height: 100%;
    }
    .ciq-select-card.selected {
        border-color: var(--brand-primary); background: var(--brand-tint);
        box-shadow: 0 0 0 1px var(--brand-primary), var(--elevation-4);
    }
    .ciq-select-title {
        font-size: 1rem; font-weight: 600; color: var(--neutral-fg-1);
        margin: 0 0 0.25rem 0;
    }
    .ciq-select-desc { font-size: 0.85rem; color: var(--neutral-fg-3); margin: 0; }

    /* Empty state */
    .ciq-empty {
        text-align: center; padding: 2.5rem 1.5rem;
        border: 1px dashed var(--neutral-stroke-1); border-radius: var(--radius-lg);
        background: var(--neutral-bg-3); color: var(--neutral-fg-3);
    }
    .ciq-empty h4 { color: var(--neutral-fg-1); margin: 0 0 0.4rem 0; }
    .ciq-empty p { margin: 0; font-size: 0.9rem; }

    /* ───────────── Links ───────────── */
    a { color: var(--brand-foreground); }

    /* ───────────── Footer ───────────── */
    .wdt-footer {
        text-align: center;
        padding: 2rem 0 1rem;
        color: var(--neutral-fg-3);
        font-size: 0.8rem;
        border-top: 1px solid var(--neutral-stroke-subtle);
        margin-top: 1.5rem;
    }
    .wdt-footer a {
        color: var(--brand-foreground);
        text-decoration: none;
    }
    .wdt-footer a:hover { text-decoration: underline; }
</style>
"""


def inject_fluent_theme():
    """Inject the ComplianceIQ brand-themed CSS into the current page."""
    css = FLUENT_CSS.replace("__LOGO_ICON_URI__", _logo_data_uri(icon=True))
    st.markdown(css, unsafe_allow_html=True)


# Backwards-compatible alias — pages import ``inject_azure_theme``.
def inject_azure_theme():
    """Deprecated alias for :func:`inject_fluent_theme`."""
    inject_fluent_theme()


def render_sidebar():
    """Render a consistent Fluent-styled left navigation across all pages."""
    with st.sidebar:
        _logo = _LOGO_FULL_PATH if _LOGO_FULL_PATH.exists() else _LOGO_ICON_PATH
        if _logo.exists():
            st.image(str(_logo), use_container_width=True)
        else:
            st.markdown("### ComplianceIQ")
        st.caption("Compliance · Microsoft 365 & Azure")
        st.markdown("---")

        # ── Clickable navigation ──
        st.page_link("app.py", label="Home", icon=None)
        st.page_link("pages/1_Upload_Controls.py", label="Upload Controls")
        st.page_link("pages/2_AI_Mapping.py", label="AI Mapping")
        st.page_link("pages/3_Review_Edit.py", label="Review & Edit")
        st.page_link("pages/4_Export_Policy.py", label="Export Policy")
        st.page_link("pages/5_PDF_Pipeline.py", label="PDF Extraction")
        st.page_link("pages/6_Policy_Explorer.py", label="Policy Explorer")
        st.page_link("pages/8_Diff_Compare.py", label="Gap Analysis")
        st.page_link("pages/9_Version_History.py", label="Version History")
        st.page_link("pages/7_Profile.py", label="My Workspace")
        st.markdown("---")

        # ── Progress tracker ──
        controls = st.session_state.get("controls", [])
        mappings = st.session_state.get("mappings", [])
        fw = st.session_state.get("framework_name", "")

        steps_done = sum([
            len(controls) > 0,
            len(mappings) > 0,
            bool(st.session_state.get("generated_policy")),
        ])
        total_steps = 3
        pct = int(steps_done / total_steps * 100)

        st.markdown("#### Progress")
        st.progress(pct / 100, text=f"{pct}% complete")

        step_icons = [
            ("Upload controls", len(controls) > 0),
            ("Run AI mapping", len(mappings) > 0),
            ("Generate policy", bool(st.session_state.get("generated_policy"))),
        ]
        for label, done in step_icons:
            st.markdown(f"- {label} — **{'Done' if done else 'To do'}**")

        st.markdown("---")

        # ── Selected platform ──
        _platform_display = st.session_state.get("platform_display_name", "")
        if _platform_display:
            st.caption(f"**{_platform_display}**")

        # ── Session metrics ──
        if fw:
            st.info(f"**{fw}**")
        col1, col2 = st.columns(2)
        col1.metric("Controls", len(controls))
        col2.metric("Mappings", len(mappings))

        # ── Developer tools ──
        st.markdown("---")
        st.checkbox("Show API Logs", key="show_api_logs",
                     help="Show request/response log panel at the bottom of each page")
        st.checkbox("Show Backend Logs", key="show_backend_logs",
                     help="Show live application logs from the backend container")
        if st.session_state.get("show_backend_logs"):
            st.selectbox(
                "Poll interval (seconds)",
                options=[5, 10, 30, 60],
                index=1,
                key="backend_log_poll_interval",
                help="How often to refresh backend logs",
            )

        st.markdown("---")

        # ── Authenticated user ──
        try:
            from utils.auth import get_current_user, get_logout_url, logout

            user = get_current_user()
            if user:
                st.markdown("---")
                st.markdown(f"**{user.display_name}**")
                st.caption(user.email)
                if "easy_auth_user" in st.session_state:
                    st.link_button(
                        "Sign out",
                        get_logout_url(),
                        use_container_width=True,
                    )
                elif st.button("Sign out", key="sidebar_signout"):
                    logout()
                    st.rerun()
        except Exception:
            pass  # auth module may not be available


def render_footer():
    """Render the product footer with support / privacy / Azure links."""
    st.markdown(
        '<div class="wdt-footer">'
        "<strong>ComplianceIQ</strong> — AI control mapping for Microsoft 365 &amp; Azure"
        "<br>"
        '<a href="/">Product</a> &nbsp;&bull;&nbsp; '
        '<a href="mailto:support@complianceiq.app">Support</a> &nbsp;&bull;&nbsp; '
        '<a href="/">Privacy</a> &nbsp;&bull;&nbsp; '
        '<a href="https://learn.microsoft.com/azure/governance/policy/">Azure Policy</a>'
        "</div>",
        unsafe_allow_html=True,
    )
