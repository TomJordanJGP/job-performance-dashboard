"""JGP branded CSS for Streamlit dashboard.

All colours flow from theme.colors.JGP_COLORS — no literal hex codes are
written here. Logo SVG sizing rules and a brand-kit-compliant focus ring
(focus_outer + focus_inner) are included so the dashboard meets WCAG 2.2 AA
keyboard-access requirements.
"""

import streamlit as st

from theme.colors import JGP_COLORS


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
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');

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

    /* Sidebar primary button — brand-kit pill: bold green on deep blue */
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
        background-color: {c['accent']};
        border: none;
        color: {c['deep_blue']};
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 15px;
        min-height: 44px;
        padding: 12px 22px;
        border-radius: 999px;
        transition: background-color 200ms ease;
    }}

    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {{
        background-color: {c['light_green']};
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

    /* Sidebar section labels (e.g. "Filters") — sentence case per brand kit */
    .jgp-sidebar-section {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 14px;
        color: {c['supporting']};
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
        font-weight: 600;
        font-size: 13px;
        color: {c['primary']};
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

    /* Primary button — brand-kit pill: bold green bg, deep blue text, 999 px radius */
    .stButton > button[kind="primary"] {{
        background-color: {c['accent']};
        border: none;
        color: {c['deep_blue']};
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 15px;
        min-height: 44px;
        padding: 12px 22px;
        border-radius: 999px;
        transition: background-color 200ms ease;
    }}

    .stButton > button[kind="primary"]:hover {{
        background-color: {c['light_green']};
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
        font-weight: 600;
        font-size: 13px;
        color: {c['primary']} !important;
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

    /* ==========================================
       CLIENT REPORT — settings → hero → 9-section layout
       Scoped via .client-* classes so other tabs are unaffected.
       ========================================== */

    /* Settings summary bar (collapsed state) */
    .client-summary-bar {{
        background: {c['surface_warm']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        flex-wrap: wrap;
    }}

    .client-summary-bar .summary-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 24px;
        font-family: 'DM Sans', sans-serif;
        color: {c['text_secondary']};
        font-size: 14px;
    }}

    .client-summary-bar .summary-meta strong {{
        color: {c['deep_blue']};
        font-weight: 600;
        margin-right: 4px;
    }}

    /* Hero band */
    .client-hero {{
        background: {c['light_purple']};
        border-radius: 8px;
        padding: 32px 36px;
        margin: 8px 0 24px 0;
    }}

    .client-hero .hero-eyebrow {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 600;
        font-size: 13px;
        color: {c['primary']};
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    .client-hero .hero-eyebrow::before {{
        content: '';
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: {c['primary']};
        display: inline-block;
    }}

    .client-hero h1 {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 40px;
        line-height: 1.1;
        color: {c['deep_blue']};
        margin: 0 0 12px 0;
    }}

    .client-hero .hero-lede {{
        font-family: 'DM Sans', sans-serif;
        font-size: 16px;
        line-height: 1.55;
        color: {c['text_secondary']};
        margin: 0 0 24px 0;
        max-width: 720px;
    }}

    .client-hero-meta {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 24px;
        border-top: 1px solid {c['border']};
        padding-top: 20px;
        margin: 0;
    }}

    .client-hero-meta dt {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 600;
        font-size: 13px;
        color: {c['primary']};
        margin-bottom: 4px;
    }}

    .client-hero-meta dd {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        font-size: 16px;
        color: {c['deep_blue']};
        margin: 0;
    }}

    /* Sticky in-page TOC */
    .client-toc {{
        position: sticky;
        top: 88px;
        background: {c['white']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 16px;
        font-family: 'DM Sans', sans-serif;
    }}

    .client-toc-title {{
        font-weight: 700;
        font-size: 13px;
        color: {c['primary']};
        margin-bottom: 12px;
    }}

    .client-toc ol {{
        list-style: none;
        padding: 0;
        margin: 0;
    }}

    .client-toc li {{ margin: 0; padding: 0; }}

    .client-toc-link {{
        display: block;
        padding: 8px 12px;
        font-size: 14px;
        color: {c['text_secondary']};
        text-decoration: none;
        border-radius: 6px;
        transition: background 150ms ease, color 150ms ease;
    }}

    .client-toc-link:hover {{
        background: {c['surface_warm']};
        color: {c['deep_blue']};
    }}

    .client-toc-num {{
        display: inline-block;
        width: 28px;
        color: {c['primary']};
        font-weight: 600;
    }}

    /* Section eyebrow + heading */
    .client-eyebrow {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 600;
        font-size: 13px;
        color: {c['primary']};
        margin: 0 0 8px 0;
    }}

    .client-eyebrow .num {{ margin-right: 6px; }}

    .client-h2 {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 26px;
        line-height: 1.2;
        color: {c['deep_blue']};
        margin: 0 0 16px 0;
    }}

    /* Anchor target — invisible, contributes 48 px section spacing via margin */
    .client-anchor {{
        display: block;
        height: 0;
        overflow: hidden;
        visibility: hidden;
        margin-top: 48px;
    }}

    /* Dark KPI card variant — one of the four headline cards is filled */
    .kpi-card.dark {{
        background: {c['deep_blue']};
        border-left: 4px solid {c['accent']};
    }}

    .kpi-card.dark .kpi-label {{ color: {c['accent']}; }}
    .kpi-card.dark .kpi-value {{ color: {c['white']}; }}
    .kpi-card.dark .kpi-helper {{ color: {c['light_purple']}; }}

    .kpi-helper {{
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        color: {c['text_muted']};
        margin-top: 4px;
    }}

    /* 2 x 2 status grid — section 02 */
    .status-grid {{
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin-top: 12px;
    }}

    .status-cell {{
        background: {c['white']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 16px 18px;
    }}

    .status-cell .status-label {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 600;
        font-size: 13px;
        color: {c['primary']};
        margin-bottom: 4px;
    }}

    .status-cell .status-value {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 24px;
        color: {c['deep_blue']};
        line-height: 1.2;
    }}

    .status-cell .status-help {{
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        color: {c['text_muted']};
        margin-top: 4px;
    }}

    /* Commentary panel — beige */
    .commentary-panel {{
        background: {c['beige']};
        border-radius: 8px;
        padding: 16px 20px;
        margin: 12px 0;
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        line-height: 1.55;
        color: {c['deep_blue']};
    }}

    .commentary-panel .commentary-eyebrow {{
        font-weight: 600;
        font-size: 13px;
        color: {c['primary']};
        margin-bottom: 6px;
    }}

    /* Cost-per-apply ranking lists — section 06 */
    .cpa-ranking {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        margin-bottom: 12px;
    }}

    .cpa-list {{
        background: {c['white']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 16px 20px;
    }}

    .cpa-list h4 {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 14px;
        color: {c['deep_blue']};
        margin: 0 0 12px 0;
    }}

    .cpa-list ol {{
        list-style: none;
        padding: 0;
        margin: 0;
        counter-reset: cpa-rank;
    }}

    .cpa-list li {{
        counter-increment: cpa-rank;
        display: grid;
        grid-template-columns: 24px 1fr auto;
        gap: 12px;
        padding: 8px 0;
        border-bottom: 1px solid {c['light_purple']};
        align-items: center;
        font-size: 14px;
        font-family: 'DM Sans', sans-serif;
    }}

    .cpa-list li:last-child {{ border-bottom: none; }}

    .cpa-list li::before {{
        content: counter(cpa-rank);
        font-weight: 700;
        color: {c['primary']};
        font-size: 14px;
    }}

    .cpa-list .cpa-label {{ color: {c['deep_blue']}; }}

    .cpa-list .cpa-value {{
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        color: {c['deep_blue']};
    }}

    /* Channel performance table — section 08 */
    .channel-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        color: {c['deep_blue']};
    }}

    .channel-table th {{
        text-align: left;
        padding: 12px 16px;
        background: {c['surface_warm']};
        color: {c['primary']};
        font-weight: 600;
        font-size: 13px;
        border-bottom: 1px solid {c['border']};
    }}

    .channel-table td {{
        padding: 12px 16px;
        border-bottom: 1px solid {c['border']};
        vertical-align: middle;
    }}

    .channel-table tbody tr:hover td {{
        background: {c['surface_warm']};
    }}

    .channel-bar {{
        display: inline-block;
        height: 10px;
        background: {c['primary']};
        border-radius: 5px;
        vertical-align: middle;
        margin-right: 8px;
        min-width: 4px;
    }}

    .channel-bar.applies {{ background: {c['deep_green']}; }}

    .channel-num {{
        font-variant-numeric: tabular-nums;
        color: {c['deep_blue']};
        font-weight: 500;
    }}

    .channel-pct {{
        font-variant-numeric: tabular-nums;
        color: {c['primary']};
        font-weight: 600;
    }}

    /* Export CTA panel — section 09 */
    .export-cta {{
        background: {c['deep_blue']};
        border-radius: 8px;
        padding: 32px 36px;
        margin: 32px 0 16px 0;
        color: {c['white']};
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 24px;
        align-items: center;
    }}

    .export-cta .export-text h2 {{
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 22px;
        color: {c['white']};
        margin: 0 0 8px 0;
    }}

    .export-cta .export-text p {{
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        color: {c['light_purple']};
        margin: 0;
        max-width: 480px;
    }}

    .export-cta .export-logo {{
        display: flex;
        align-items: center;
        gap: 12px;
        color: {c['light_purple']};
        font-size: 12px;
    }}

    .export-cta .export-logo svg {{
        height: 28px;
        width: auto;
    }}
</style>
"""


FULL_CSS = _build_css()


def inject_css():
    """Inject JGP branded CSS into Streamlit page."""
    st.markdown(FULL_CSS, unsafe_allow_html=True)
