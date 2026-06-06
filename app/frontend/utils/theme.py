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

import streamlit as st


# ── Fluent 2 design tokens + component styling ─────────────────────────────
FLUENT_CSS = """
<style>
    /* ───────────── Fluent 2 design tokens ───────────── */
    :root {
        /* Brand ramp (Microsoft blue) */
        --brand-primary: #0F6CBD;          /* colorBrandBackground */
        --brand-hover:   #115EA3;          /* colorBrandBackgroundHover */
        --brand-pressed: #0E4775;          /* colorBrandBackgroundPressed */
        --brand-selected:#0F548C;
        --brand-tint:    #EBF3FC;          /* colorBrandBackground2 (subtle) */
        --brand-tint-2:  #CFE4FA;
        --brand-foreground: #0F6CBD;       /* colorBrandForegroundLink */

        /* Neutral ramp (structural majority) */
        --neutral-fg-1:  #242424;          /* colorNeutralForeground1 */
        --neutral-fg-2:  #424242;          /* colorNeutralForeground2 */
        --neutral-fg-3:  #616161;          /* colorNeutralForeground3 */
        --neutral-fg-disabled: #BDBDBD;
        --neutral-bg-1:  #FFFFFF;          /* canvas */
        --neutral-bg-2:  #FAFAFA;          /* layer / nav */
        --neutral-bg-3:  #F5F5F5;          /* subtle layer */
        --neutral-bg-4:  #F0F0F0;
        --neutral-stroke-1: #D1D1D1;       /* colorNeutralStroke1 */
        --neutral-stroke-2: #E0E0E0;       /* colorNeutralStroke2 */
        --neutral-stroke-subtle: #EBEBEB;

        /* Shared / semantic status colors */
        --status-success:    #0E700E;
        --status-success-bg: #E7F5E7;
        --status-success-stroke: #9FD89F;
        --status-warning:    #BC4B09;
        --status-warning-bg: #FCF4D6;
        --status-warning-stroke: #F2D98E;
        --status-danger:     #C50F1F;
        --status-danger-bg:  #FDE7E9;
        --status-danger-stroke: #F1A9AF;
        --status-info:       #0F6CBD;
        --status-info-bg:    #EBF3FC;
        --status-info-stroke: #B4D6FA;

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
    .stApp { background-color: var(--neutral-bg-1); }

    /* Type ramp — keep corners crisp, Fluent weights */
    h1 { font-size: 1.75rem; font-weight: 600; line-height: 2.25rem;
         color: var(--neutral-fg-1); letter-spacing: -0.01em; }
    h2 { font-size: 1.375rem; font-weight: 600; line-height: 1.75rem;
         color: var(--neutral-fg-1); }
    h3 { font-size: 1.125rem; font-weight: 600; line-height: 1.5rem;
         color: var(--neutral-fg-1); }
    h4, h5, h6 { font-weight: 600; color: var(--neutral-fg-2); }
    p, li, label, .stMarkdown { color: var(--neutral-fg-2); }

    /* ───────────── Suite header (M365 top bar) ───────────── */
    header[data-testid="stHeader"] {
        background: var(--brand-primary);
        height: var(--suite-header-height);
        box-shadow: var(--elevation-2);
    }
    header[data-testid="stHeader"]::before {
        content: "\\01F6E1\\FE0F  ComplianceIQ";
        position: absolute;
        left: 1rem;
        top: 0;
        height: var(--suite-header-height);
        display: flex;
        align-items: center;
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
    """Inject the Microsoft 365 / Fluent 2 themed CSS into the current page."""
    st.markdown(FLUENT_CSS, unsafe_allow_html=True)


# Backwards-compatible alias — pages import ``inject_azure_theme``.
def inject_azure_theme():
    """Deprecated alias for :func:`inject_fluent_theme`."""
    inject_fluent_theme()


def render_sidebar():
    """Render a consistent Fluent-styled left navigation across all pages."""
    with st.sidebar:
        st.markdown("### 🛡️ ComplianceIQ")
        st.caption("Compliance · Microsoft 365 & Azure")
        st.markdown("---")

        # ── Clickable navigation ──
        st.page_link("app.py", label="🏠 Home", icon=None)
        st.page_link("pages/1_📁_Upload_Controls.py", label="📁 Upload Controls")
        st.page_link("pages/2_🤖_AI_Mapping.py", label="🤖 AI Mapping")
        st.page_link("pages/3_✏️_Review_Edit.py", label="✏️ Review & Edit")
        st.page_link("pages/4_📦_Export_Policy.py", label="📦 Export Policy")
        st.page_link("pages/5_🚀_PDF_Pipeline.py", label="🚀 PDF Extraction")
        st.page_link("pages/6_🔍_Policy_Explorer.py", label="🔍 Policy Explorer")
        st.page_link("pages/8_🔀_Diff_Compare.py", label="🎯 Gap Analysis")
        st.page_link("pages/9_🗂_Version_History.py", label="🗂 Version History")
        st.page_link("pages/7_👤_Profile.py", label="🧭 My Workspace")
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

        st.markdown("#### 📊 Progress")
        st.progress(pct / 100, text=f"{pct}% complete")

        step_icons = [
            ("Upload controls", len(controls) > 0),
            ("Run AI mapping", len(mappings) > 0),
            ("Generate policy", bool(st.session_state.get("generated_policy"))),
        ]
        for label, done in step_icons:
            st.markdown(f"{'✅' if done else '⬜'} {label}")

        st.markdown("---")

        # ── Selected platform ──
        _platform_icons = {
            "azure_defender": "🛡️",
            "microsoft_365": "📧",
            "microsoft_purview": "🔍",
        }
        _platform_display = st.session_state.get("platform_display_name", "")
        _platform_id = st.session_state.get("selected_platform", "azure_defender")
        if _platform_display:
            _icon = _platform_icons.get(_platform_id, "🎯")
            st.caption(f"{_icon} **{_platform_display}**")

        # ── Session metrics ──
        if fw:
            st.info(f"🗂️ **{fw}**")
        col1, col2 = st.columns(2)
        col1.metric("Controls", len(controls))
        col2.metric("Mappings", len(mappings))

        # ── Developer tools ──
        st.markdown("---")
        st.checkbox("📡 Show API Logs", key="show_api_logs",
                     help="Show request/response log panel at the bottom of each page")
        st.checkbox("📋 Show Backend Logs", key="show_backend_logs",
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
        st.caption("Made by **Warren DT**")

        # ── Authenticated user ──
        try:
            from utils.auth import get_current_user, logout

            user = get_current_user()
            if user:
                st.markdown("---")
                st.markdown(f"👤 **{user.display_name}**")
                st.caption(user.email)
                if st.button("Sign out", key="sidebar_signout"):
                    logout()
                    st.rerun()
        except Exception:
            pass  # auth module may not be available


def render_footer():
    """Render the page footer with branding."""
    st.markdown(
        '<div class="wdt-footer">'
        "<strong>ComplianceIQ — AI Control Mapping Agent</strong><br>"
        "Made by <strong>Warren DT</strong> &nbsp;|&nbsp; "
        "Powered by Azure OpenAI &bull; MCSB &bull; Sovereign Landing Zone"
        "</div>",
        unsafe_allow_html=True,
    )
