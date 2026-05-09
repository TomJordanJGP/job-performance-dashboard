"""Reusable HTML component builders for JGP branded dashboard.

Logos are inlined as SVG so the dashboard is self-contained on Streamlit Cloud
(no static-file route or external CDN dependency). Colours flow from the CSS
classes defined in `theme/css.py` — components stay structural, no inline hex
literals here.
"""

from functools import lru_cache
from pathlib import Path

from theme.colors import JGP_LOGOS

# Resolve asset paths relative to repo root, regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=8)
def _read_logo(token: str) -> str:
    """Read a JGP logo SVG by token name (cached)."""
    rel = JGP_LOGOS[token]
    return (_REPO_ROOT / rel).read_text()


def kpi_card(label, value, delta=None, delta_direction="neutral", quartiles=None, helper=None):
    """Build a branded KPI card as HTML string.

    Args:
        label: KPI label text (e.g., "Total vacancies").
        value: Formatted value string (e.g., "33,975").
        delta: Optional delta text (e.g., "+5.2%").
        delta_direction: "positive", "negative", or "neutral".
        quartiles: Optional dict with 'top_25', 'middle_50', 'bottom_25'.
        helper: Optional helper line below the value (e.g. methodology note).
    """
    delta_html = ""
    if delta:
        delta_class = {"positive": "positive", "negative": "negative"}.get(delta_direction, "neutral")
        arrow = "&#9650;" if delta_direction == "positive" else "&#9660;" if delta_direction == "negative" else ""
        delta_html = f'<div class="kpi-delta {delta_class}">{arrow} {delta}</div>'

    quartile_html = ""
    if quartiles:
        quartile_html = (
            '<div class="kpi-quartiles">'
            '<div class="q-cell">'
            '<div class="q-low q-label">Low 25%</div>'
            f'<div class="q-low">{quartiles["bottom_25"]}</div>'
            '</div>'
            '<div class="q-cell">'
            '<div class="q-mid q-label">Mid 50%</div>'
            f'<div class="q-mid">{quartiles["middle_50"]}</div>'
            '</div>'
            '<div class="q-cell">'
            '<div class="q-top q-label">Top 25%</div>'
            f'<div class="q-top">{quartiles["top_25"]}</div>'
            '</div>'
            '</div>'
        )

    helper_html = f'<div class="kpi-helper">{helper}</div>' if helper else ""

    return (
        '<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{delta_html}'
        f'{quartile_html}'
        f'{helper_html}'
        '</div>'
    )


def page_header(title, subtitle=None):
    """Build a branded page header as HTML string."""
    subtitle_html = f'<p class="subtitle">{subtitle}</p>' if subtitle else ""
    return f'''
    <div class="page-header">
        <h1>{title}</h1>
        {subtitle_html}
    </div>
    '''


def filter_tags(filters_dict):
    """Build a row of filter tag pills showing active filters.

    Args:
        filters_dict: Dictionary of applied filters from session state.
    """
    if not filters_dict:
        return ""

    tags = []

    if filters_dict.get('date_range') and len(filters_dict['date_range']) == 2:
        start, end = filters_dict['date_range']
        tags.append(f'<span class="filter-tag"><i class="bi bi-calendar3"></i>{start.strftime("%d %b %Y")} - {end.strftime("%d %b %Y")}</span>')

    if filters_dict.get('importer'):
        for imp in filters_dict['importer'][:3]:
            tags.append(f'<span class="filter-tag"><i class="bi bi-box-arrow-in-right"></i>{imp}</span>')
        if len(filters_dict['importer']) > 3:
            tags.append(f'<span class="filter-tag">+{len(filters_dict["importer"]) - 3} more</span>')

    if filters_dict.get('company'):
        for comp in filters_dict['company'][:3]:
            tags.append(f'<span class="filter-tag"><i class="bi bi-building"></i>{comp}</span>')
        if len(filters_dict['company']) > 3:
            tags.append(f'<span class="filter-tag">+{len(filters_dict["company"]) - 3} more</span>')

    if filters_dict.get('region'):
        for reg in filters_dict['region'][:3]:
            tags.append(f'<span class="filter-tag"><i class="bi bi-geo-alt"></i>{reg}</span>')
        if len(filters_dict['region']) > 3:
            tags.append(f'<span class="filter-tag">+{len(filters_dict["region"]) - 3} more</span>')

    if filters_dict.get('occupation'):
        for occ in filters_dict['occupation'][:2]:
            tags.append(f'<span class="filter-tag"><i class="bi bi-briefcase"></i>{occ}</span>')
        if len(filters_dict['occupation']) > 2:
            tags.append(f'<span class="filter-tag">+{len(filters_dict["occupation"]) - 2} more</span>')

    if filters_dict.get('job_title') and filters_dict['job_title'].strip():
        tags.append(f'<span class="filter-tag"><i class="bi bi-search"></i>"{filters_dict["job_title"]}"</span>')

    if filters_dict.get('upgrades'):
        for upg in filters_dict['upgrades'][:2]:
            tags.append(f'<span class="filter-tag"><i class="bi bi-arrow-up-circle"></i>{upg}</span>')
        if len(filters_dict['upgrades']) > 2:
            tags.append(f'<span class="filter-tag">+{len(filters_dict["upgrades"]) - 2} more</span>')

    if not tags:
        return ""

    return f'<div class="filter-tags">{"".join(tags)}</div>'


def section_header(title, icon=None):
    """Build a branded section header with optional Bootstrap icon."""
    icon_html = f'<i class="bi bi-{icon}"></i>' if icon else ""
    return f'<div class="section-header">{icon_html}{title}</div>'


def branded_divider():
    """Build a branded gradient divider."""
    return '<div class="branded-divider"></div>'


def notice_box(text, icon="info-circle"):
    """Build a branded notice/info box."""
    return f'<div class="notice-box"><i class="bi bi-{icon}"></i>{text}</div>'


def empty_state(message, icon="inbox"):
    """Build a branded empty state message."""
    return f'''
    <div class="empty-state">
        <i class="bi bi-{icon}"></i>
        <p>{message}</p>
    </div>
    '''


def sidebar_logo(subtitle: str = "Job Performance Dashboard") -> str:
    """Render the official JGP logo (white variant) for the dark sidebar."""
    svg = _read_logo('white')
    return f'''
    <div class="jgp-logo-container">
        <div class="jgp-logo-wrap">{svg}</div>
        <p class="jgp-logo-subtitle">{subtitle}</p>
    </div>
    '''


def main_logo(title: str = "Job Performance Dashboard") -> str:
    """Render the official JGP logo (full colour) above the main tabs."""
    svg = _read_logo('full_colour')
    return f'''
    <div class="main-logo">
        <div class="main-logo-wrap">{svg}</div>
        <span class="main-logo-title">{title}</span>
    </div>
    '''


def sidebar_section_header(label: str) -> str:
    """Render a sidebar section label (e.g. 'Filters') as branded HTML."""
    return f'<div class="jgp-sidebar-section">{label}</div>'


# ---------------------------------------------------------------------------
# Client Report — builders for the 9-section redesign.
# Pure HTML strings, no Streamlit calls. Streamlit widgets (buttons,
# download_button, expander) are rendered by the caller adjacent to these.
# ---------------------------------------------------------------------------


def section_eyebrow(num, title):
    """Build the '01 — Headline numbers' eyebrow + h2 pair."""
    return (
        f'<div class="client-eyebrow"><span class="num">{num}</span></div>'
        f'<h2 class="client-h2">{title}</h2>'
    )


def section_anchor(anchor_id):
    """Invisible anchor target for in-page TOC links."""
    return f'<span class="client-anchor" id="{anchor_id}"></span>'


def client_hero(name, period, lede, vacancies, am_name=None):
    """Render the hero band: light-purple, eyebrow + h1 + lede + meta row."""
    am_html = ''
    if am_name and str(am_name).strip():
        am_html = f'<div><dt>Account manager</dt><dd>{am_name}</dd></div>'
    return f'''
    <div class="client-hero">
        <div class="hero-eyebrow">Client advertising report</div>
        <h1>{name}</h1>
        <p class="hero-lede">{lede}</p>
        <dl class="client-hero-meta">
            <div><dt>Client</dt><dd>{name}</dd></div>
            <div><dt>Reporting period</dt><dd>{period}</dd></div>
            <div><dt>Vacancies in scope</dt><dd>{vacancies:,}</dd></div>
            {am_html}
        </dl>
    </div>
    '''


def summary_bar(client, period, am_name=None):
    """Render the collapsed-settings summary bar. Caller adds an Edit button below."""
    am = ''
    if am_name and str(am_name).strip():
        am = f'<span><strong>AM:</strong> {am_name}</span>'
    return f'''
    <div class="client-summary-bar">
        <div class="summary-meta">
            <span><strong>Client:</strong> {client}</span>
            <span><strong>Period:</strong> {period}</span>
            {am}
        </div>
    </div>
    '''


def kpi_card_dark(label, value, helper=None):
    """Deep-blue filled KPI card — used for the emphasis tile in section 01."""
    helper_html = f'<div class="kpi-helper">{helper}</div>' if helper else ''
    return (
        '<div class="kpi-card dark">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{helper_html}'
        '</div>'
    )


def commentary_panel(text, eyebrow="Commentary"):
    """Beige callout placed under each section's chart with a brief explainer."""
    return (
        '<div class="commentary-panel">'
        f'<div class="commentary-eyebrow">{eyebrow}</div>'
        f'<div>{text}</div>'
        '</div>'
    )


def status_grid(stats):
    """Render a 2x2 status grid. `stats` is a list of dicts with keys label/value/help."""
    cells = []
    for s in stats:
        help_html = f'<div class="status-help">{s["help"]}</div>' if s.get('help') else ''
        cells.append(
            '<div class="status-cell">'
            f'<div class="status-label">{s["label"]}</div>'
            f'<div class="status-value">{s["value"]}</div>'
            f'{help_html}'
            '</div>'
        )
    return f'<div class="status-grid">{"".join(cells)}</div>'


def client_toc(items):
    """Sticky in-page TOC. `items` is a list of (number, anchor_id, label) triples."""
    li_html = ''.join(
        f'<li><a class="client-toc-link" href="#{anchor}">'
        f'<span class="client-toc-num">{num}</span>{label}</a></li>'
        for num, anchor, label in items
    )
    return (
        '<div class="client-toc">'
        '<div class="client-toc-title">In this report</div>'
        f'<ol>{li_html}</ol>'
        '</div>'
    )


def export_cta_panel(heading, lede):
    """Deep-blue export panel. Caller renders the actual download button right after."""
    return f'''
    <div class="export-cta">
        <div class="export-text">
            <h2>{heading}</h2>
            <p>{lede}</p>
        </div>
        <div class="export-logo"></div>
    </div>
    '''
