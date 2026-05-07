"""JGP branded CSS for Streamlit dashboard.

All colours flow from theme.colors.JGP_COLORS — no literal hex codes are
written here. Logo SVG sizing rules and a brand-kit-compliant focus ring
(focus_outer + focus_inner) are included so the dashboard meets WCAG 2.2 AA
keyboard-access requirements.
"""

import streamlit as st

from theme.colors import JGP_COLORS, HOVER_PRIMARY


def _build_css() -> str:
    """Compose the full CSS payload, interpolating brand tokens."""
    c = JGP_COLORS
    border_dim = c['border']
    return f"""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<style>
    /* ==========================================
       FONTS — DM Sans (brand) with weights 400/500/600/700
       ========================================== */
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');

    html, body, [class*="css"] {{
        font-family: 'DM Sans', sans-serif !important;
    }}

    /* ==========================================
       FOCUS RING (WCAG 2.2 AA) — brand-kit focus pair
       ========================================== */
    *:focus-visible {{
        outline: 3px solid {c['focus_inner']};
        outline-offset: 0;
        box-shadow: 0 0 0 6px {c['focus_outer']};
        border-radius: 4px;
    }}

    /* ==========================================
       SIDEBAR
       ========================================== */
    [data-testid="stSidebar"] {{
        background-color: {c['deep_blue']};
        padding-top: 0;
    }}

    [data-testid="stSidebar"] [data-testid="stMarkdown"],
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMultiSelect label,
    [data-testid="stSidebar"] .stDateInput label,
    [data-testid="stSidebar"] .stTextInput label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] .stSlider label {{
        color: {c['white']} !important;
    }}

    [data-testid="stSidebar"] hr {{
        border-color: rgba(255,255,255,0.15);
    }}

    [data-testid="stSidebar"] .stDateInput input,
    [data-testid="stSidebar"] .stTextInput input {{
        background-color: {c['white']};
        color: {c['deep_blue']};
        border-color: {border_dim};
        border-radius: 6px;
    }}

    [data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"] {{
        background-color: {c['white']};
        border-color: {border_dim};
        border-radius: 6px;
    }}

    [data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"] span {{
        color: {c['deep_blue']} !important;
    }}

    /* Sidebar primary button */
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
        background-color: {c['primary']};
        border: none;
        color: {c['white']};
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        transition: background-color 200ms ease;
    }}

    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {{
        background-color: {HOVER_PRIMARY};
    }}

    /* Sidebar refresh / secondary button */
    [data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {{
        background-color: transparent;
        border: 1px solid {c['supporting']};
        color: {c['accent']};
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        border-radius: 6px;
        transition: all 200ms ease;
    }}

    [data-testid="stSidebar"] .stButton > button:not([kind="primary"]):hover {{
        background-color: rgba(229, 255, 110, 0.1);
        border-color: {c['accent']};
    }}

    /* ==========================================
       LOGO (sidebar)
       ========================================== */
    .jgp-logo-container {{
        background-color: {c['deep_blue']};
        padding: 20px 16px 12px 16px;
        margin: -1rem -1rem 0.25rem -1rem;
        border-bottom: 2px solid {c['primary']};
    }}

    .jgp-logo-wrap {{
        display: block;
        margin-bottom: 6px;
    }}

    .jgp-logo-wrap svg {{
        height: 32px;
        width: auto;
        max-width: 100%;
    }}

    .jgp-logo-subtitle {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 400;
        font-size: 12px;
        color: {c['supporting']};
        margin: 4px 0 0 0;
    }}

    /* Sidebar section labels (e.g. "Filters") — replaces inline-styled markdown */
    .jgp-sidebar-section {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 14px;
        color: {c['supporting']};
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }}

    /* ==========================================
       TABS
       ========================================== */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0;
        background-color: {c['surface_warm']};
        border-radius: 8px;
        padding: 4px;
    }}

    .stTabs [data-baseweb="tab"] {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        font-size: 14px;
        color: {c['primary']};
        border-radius: 6px;
        padding: 8px 20px;
        transition: all 200ms ease;
    }}

    .stTabs [data-baseweb="tab"]:hover {{
        background-color: {c['light_purple']};
    }}

    .stTabs [aria-selected="true"] {{
        background-color: {c['primary']} !important;
        color: {c['white']} !important;
        font-weight: 700;
    }}

    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] {{
        display: none;
    }}

    /* ==========================================
       KPI CARDS
       ========================================== */
    .kpi-card {{
        background: linear-gradient(135deg, {c['surface_warm']} 0%, {c['light_purple']} 100%);
        border-left: 4px solid {c['primary']};
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 8px;
    }}

    .kpi-label {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        font-size: 12px;
        color: {c['primary']};
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }}

    .kpi-value {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 28px;
        color: {c['deep_blue']};
        line-height: 1.2;
    }}

    .kpi-delta {{
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        margin-top: 4px;
    }}

    .kpi-delta.positive {{ color: {c['positive']}; }}
    .kpi-delta.negative {{ color: {c['negative']}; }}
    .kpi-delta.neutral  {{ color: {c['neutral']}; }}

    .kpi-quartiles {{
        display: flex;
        flex-direction: row;
        gap: 0;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid {border_dim};
        font-family: 'DM Sans', sans-serif;
        font-size: 11px;
    }}

    .kpi-quartiles .q-cell {{
        flex: 1;
        text-align: center;
    }}

    .kpi-quartiles .q-cell + .q-cell {{
        border-left: 1px solid {border_dim};
    }}

    .kpi-quartiles .q-low   {{ color: {c['negative']}; }}
    .kpi-quartiles .q-mid   {{ color: {c['primary']}; }}
    .kpi-quartiles .q-top   {{ color: {c['positive']}; }}
    .kpi-quartiles .q-label {{ font-weight: 500; }}

    /* ==========================================
       MAIN LOGO (above tabs)
       ========================================== */
    .main-logo {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 2px solid {c['light_purple']};
    }}

    .main-logo-wrap svg {{
        height: 36px;
        width: auto;
        max-width: 100%;
        display: block;
    }}

    .main-logo-title {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 24px;
        color: {c['deep_blue']};
    }}

    /* ==========================================
       PAGE HEADERS
       ========================================== */
    .page-header {{
        margin-bottom: 16px;
    }}

    .page-header h1 {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 28px;
        color: {c['deep_blue']};
        margin: 0 0 4px 0;
    }}

    .page-header .subtitle {{
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        color: {c['text_secondary']};
        margin: 0;
    }}

    /* ==========================================
       FILTER TAGS
       ========================================== */
    .filter-tags {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 16px;
    }}

    .filter-tag {{
        display: inline-flex;
        align-items: center;
        background-color: {c['light_purple']};
        color: {c['primary']};
        font-family: 'DM Sans', sans-serif;
        font-size: 12px;
        font-weight: 500;
        padding: 4px 10px;
        border-radius: 20px;
        white-space: nowrap;
    }}

    .filter-tag i {{
        margin-right: 4px;
        font-size: 11px;
    }}

    /* ==========================================
       SECTION HEADERS
       ========================================== */
    .section-header {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 18px;
        color: {c['deep_blue']};
        margin: 24px 0 12px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    .section-header i {{
        color: {c['primary']};
        font-size: 18px;
    }}

    /* ==========================================
       BRANDED DIVIDER
       ========================================== */
    .branded-divider {{
        height: 2px;
        background: linear-gradient(to right, {c['primary']}, {c['light_purple']}, transparent);
        border: none;
        margin: 24px 0;
    }}

    /* ==========================================
       NOTICE BOX
       ========================================== */
    .notice-box {{
        background-color: {c['surface_warm']};
        border-left: 4px solid {c['accent']};
        border-radius: 6px;
        padding: 12px 16px;
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        color: {c['deep_blue']};
        margin-bottom: 16px;
    }}

    .notice-box i {{
        color: {c['deep_green']};
        margin-right: 6px;
    }}

    /* ==========================================
       EMPTY STATE
       ========================================== */
    .empty-state {{
        text-align: center;
        padding: 40px 20px;
        color: {c['text_muted']};
        font-family: 'DM Sans', sans-serif;
    }}

    .empty-state i {{
        font-size: 48px;
        display: block;
        margin-bottom: 12px;
        color: {c['light_purple']};
    }}

    .empty-state p {{
        font-size: 14px;
        margin: 0;
    }}

    /* ==========================================
       DOWNLOAD BUTTON
       ========================================== */
    .stDownloadButton > button {{
        background-color: transparent;
        border: 1px solid {c['primary']};
        color: {c['primary']};
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        border-radius: 6px;
        transition: all 200ms ease;
    }}

    .stDownloadButton > button:hover {{
        background-color: {c['primary']};
        color: {c['white']};
    }}

    /* ==========================================
       GENERAL OVERRIDES
       ========================================== */

    /* Primary button */
    .stButton > button[kind="primary"] {{
        background-color: {c['primary']};
        border: none;
        color: {c['white']};
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        border-radius: 6px;
        transition: background-color 200ms ease;
    }}

    .stButton > button[kind="primary"]:hover {{
        background-color: {HOVER_PRIMARY};
    }}

    /* Streamlit metric (default st.metric) */
    [data-testid="stMetric"] {{
        background: linear-gradient(135deg, {c['surface_warm']} 0%, {c['light_purple']} 100%);
        border-left: 4px solid {c['primary']};
        border-radius: 8px;
        padding: 12px 16px;
    }}

    [data-testid="stMetric"] label {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        font-size: 12px;
        color: {c['primary']} !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    [data-testid="stMetric"] [data-testid="stMetricValue"] {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        color: {c['deep_blue']};
    }}

    /* Expander styling */
    .streamlit-expanderHeader {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        color: {c['primary']};
    }}

    /* Selectbox label */
    .stSelectbox label {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        color: {c['deep_blue']};
    }}

    /* Loading spinner */
    .stSpinner > div {{
        border-top-color: {c['primary']} !important;
    }}

    /* Hide Streamlit default chrome */
    #MainMenu {{ visibility: hidden; }}
    footer    {{ visibility: hidden; }}

    /* Dataframe header */
    .stDataFrame thead th {{
        background-color: {c['primary']} !important;
        color: {c['white']} !important;
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
    }}
</style>
"""


FULL_CSS = _build_css()


def inject_css():
    """Inject JGP branded CSS into Streamlit page."""
    st.markdown(FULL_CSS, unsafe_allow_html=True)
