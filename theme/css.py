"""JGP branded CSS for Streamlit dashboard."""

import streamlit as st

# All CSS assembled as a single string for injection
FULL_CSS = """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<style>
    /* ==========================================
       FONTS
       ========================================== */
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,700;1,9..40,400&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif !important;
    }

    /* ==========================================
       SIDEBAR
       ========================================== */
    [data-testid="stSidebar"] {
        background-color: #240f45;
        padding-top: 0;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdown"],
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMultiSelect label,
    [data-testid="stSidebar"] .stDateInput label,
    [data-testid="stSidebar"] .stTextInput label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] .stSlider label {
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.15);
    }

    /* Sidebar inputs */
    [data-testid="stSidebar"] .stDateInput input,
    [data-testid="stSidebar"] .stTextInput input {
        background-color: #3a1a6e;
        color: #ffffff;
        border-color: #9c67d3;
        border-radius: 6px;
    }

    [data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"] {
        background-color: #3a1a6e;
        border-color: #9c67d3;
        border-radius: 6px;
    }

    [data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"] span {
        color: #ffffff !important;
    }

    /* Sidebar button */
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background-color: #643791;
        border: none;
        color: #ffffff;
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        transition: background-color 200ms ease;
    }

    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background-color: #7b4aab;
    }

    /* Refresh button (secondary) */
    [data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {
        background-color: transparent;
        border: 1px solid #9c67d3;
        color: #e5ff6e;
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        border-radius: 6px;
        transition: all 200ms ease;
    }

    [data-testid="stSidebar"] .stButton > button:not([kind="primary"]):hover {
        background-color: rgba(229, 255, 110, 0.1);
        border-color: #e5ff6e;
    }

    /* ==========================================
       LOGO
       ========================================== */
    .jgp-logo-container {
        background-color: #240f45;
        padding: 20px 16px 12px 16px;
        margin: -1rem -1rem 0.25rem -1rem;
        border-bottom: 2px solid #643791;
    }

    .jgp-logo-text {
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 20px;
        color: #ffffff;
        margin: 0;
        letter-spacing: -0.3px;
    }

    .jgp-logo-subtitle {
        font-family: 'DM Sans', sans-serif;
        font-weight: 400;
        font-size: 12px;
        color: #9c67d3;
        margin: 2px 0 0 0;
    }

    .jgp-logo-icon {
        display: inline-block;
        background-color: #643791;
        color: #ffffff;
        font-weight: 700;
        font-size: 14px;
        padding: 3px 8px;
        border-radius: 4px;
        margin-right: 8px;
        font-family: 'DM Sans', sans-serif;
    }

    /* ==========================================
       TABS
       ========================================== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background-color: #f8f6fb;
        border-radius: 8px;
        padding: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        font-size: 14px;
        color: #643791;
        border-radius: 6px;
        padding: 8px 20px;
        transition: all 200ms ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e8e0f2;
    }

    .stTabs [aria-selected="true"] {
        background-color: #643791 !important;
        color: #ffffff !important;
        font-weight: 700;
    }

    /* Hide default Streamlit tab indicator line */
    .stTabs [data-baseweb="tab-highlight"] {
        display: none;
    }

    .stTabs [data-baseweb="tab-border"] {
        display: none;
    }

    /* ==========================================
       KPI CARDS
       ========================================== */
    .kpi-card {
        background: linear-gradient(135deg, #f8f6fb 0%, #e8e0f2 100%);
        border-left: 4px solid #643791;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 8px;
    }

    .kpi-label {
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        font-size: 12px;
        color: #643791;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }

    .kpi-value {
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 28px;
        color: #240f45;
        line-height: 1.2;
    }

    .kpi-delta {
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        margin-top: 4px;
    }

    .kpi-delta.positive { color: #2e4500; }
    .kpi-delta.negative { color: #c0392b; }
    .kpi-delta.neutral  { color: #9c67d3; }

    .kpi-quartiles {
        display: flex;
        flex-direction: column;
        gap: 2px;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid rgba(100, 55, 145, 0.15);
    }

    .kpi-quartiles span {
        font-family: 'DM Sans', sans-serif;
        font-size: 11px;
        font-weight: 400;
    }

    .kpi-quartiles .q-top { color: #2e4500; }
    .kpi-quartiles .q-mid { color: #643791; }
    .kpi-quartiles .q-low { color: #c0392b; }

    /* ==========================================
       MAIN LOGO (above tabs)
       ========================================== */
    .main-logo {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 2px solid #e8e0f2;
    }

    .main-logo-icon {
        display: inline-block;
        background-color: #643791;
        color: #ffffff;
        font-weight: 700;
        font-size: 16px;
        padding: 4px 10px;
        border-radius: 4px;
        font-family: 'DM Sans', sans-serif;
    }

    .main-logo-title {
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 24px;
        color: #240f45;
    }

    /* ==========================================
       PAGE HEADERS
       ========================================== */
    .page-header {
        margin-bottom: 16px;
    }

    .page-header h1 {
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 28px;
        color: #240f45;
        margin: 0 0 4px 0;
    }

    .page-header .subtitle {
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        color: #9c67d3;
        margin: 0;
    }

    /* ==========================================
       FILTER TAGS
       ========================================== */
    .filter-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 16px;
    }

    .filter-tag {
        display: inline-flex;
        align-items: center;
        background-color: #e8e0f2;
        color: #643791;
        font-family: 'DM Sans', sans-serif;
        font-size: 12px;
        font-weight: 500;
        padding: 4px 10px;
        border-radius: 20px;
        white-space: nowrap;
    }

    .filter-tag i {
        margin-right: 4px;
        font-size: 11px;
    }

    /* ==========================================
       SECTION HEADERS
       ========================================== */
    .section-header {
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 18px;
        color: #240f45;
        margin: 24px 0 12px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .section-header i {
        color: #643791;
        font-size: 18px;
    }

    /* ==========================================
       BRANDED DIVIDER
       ========================================== */
    .branded-divider {
        height: 2px;
        background: linear-gradient(to right, #643791, #e8e0f2, transparent);
        border: none;
        margin: 24px 0;
    }

    /* ==========================================
       NOTICE BOX
       ========================================== */
    .notice-box {
        background-color: #f0f3e1;
        border-left: 4px solid #e5ff6e;
        border-radius: 6px;
        padding: 12px 16px;
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        color: #240f45;
        margin-bottom: 16px;
    }

    .notice-box i {
        color: #2e4500;
        margin-right: 6px;
    }

    /* ==========================================
       EMPTY STATE
       ========================================== */
    .empty-state {
        text-align: center;
        padding: 40px 20px;
        color: #9c67d3;
        font-family: 'DM Sans', sans-serif;
    }

    .empty-state i {
        font-size: 48px;
        display: block;
        margin-bottom: 12px;
        color: #e8e0f2;
    }

    .empty-state p {
        font-size: 14px;
        margin: 0;
    }

    /* ==========================================
       DOWNLOAD BUTTON
       ========================================== */
    .stDownloadButton > button {
        background-color: transparent;
        border: 1px solid #643791;
        color: #643791;
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        border-radius: 6px;
        transition: all 200ms ease;
    }

    .stDownloadButton > button:hover {
        background-color: #643791;
        color: #ffffff;
    }

    /* ==========================================
       GENERAL OVERRIDES
       ========================================== */

    /* Primary button */
    .stButton > button[kind="primary"] {
        background-color: #643791;
        border: none;
        color: #ffffff;
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        border-radius: 6px;
        transition: background-color 200ms ease;
    }

    .stButton > button[kind="primary"]:hover {
        background-color: #7b4aab;
    }

    /* Metric cards (Streamlit default) - style override */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #f8f6fb 0%, #e8e0f2 100%);
        border-left: 4px solid #643791;
        border-radius: 8px;
        padding: 12px 16px;
    }

    [data-testid="stMetric"] label {
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        font-size: 12px;
        color: #643791 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        color: #240f45;
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        color: #643791;
    }

    /* Selectbox */
    .stSelectbox label {
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        color: #240f45;
    }

    /* Data loading spinner */
    .stSpinner > div {
        border-top-color: #643791 !important;
    }

    /* Hide Streamlit footer and hamburger menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Dataframe header */
    .stDataFrame thead th {
        background-color: #643791 !important;
        color: #ffffff !important;
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
    }
</style>
"""


def inject_css():
    """Inject JGP branded CSS into Streamlit page."""
    st.markdown(FULL_CSS, unsafe_allow_html=True)
