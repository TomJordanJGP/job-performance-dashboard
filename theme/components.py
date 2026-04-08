"""Reusable HTML component builders for JGP branded dashboard."""


def kpi_card(label, value, delta=None, delta_direction="neutral", quartiles=None):
    """Build a branded KPI card as HTML string.

    Args:
        label: KPI label text (e.g., "Total Vacancies")
        value: Formatted value string (e.g., "33,975")
        delta: Optional delta text (e.g., "+5.2%")
        delta_direction: "positive", "negative", or "neutral"
        quartiles: Optional dict with 'top_25', 'middle_50', 'bottom_25' values to show as small text
    """
    delta_html = ""
    if delta:
        delta_class = {"positive": "positive", "negative": "negative"}.get(delta_direction, "neutral")
        arrow = "&#9650;" if delta_direction == "positive" else "&#9660;" if delta_direction == "negative" else ""
        delta_html = f'<div class="kpi-delta {delta_class}">{arrow} {delta}</div>'

    quartile_html = ""
    if quartiles:
        quartile_html = (
            '<div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(100,55,145,0.15);'
            'font-family:DM Sans,sans-serif;font-size:11px;display:flex;gap:0;">'
            '<div style="flex:1;text-align:center;">'
            '<div style="color:#c0392b;font-weight:500;">Low 25%</div>'
            f'<div style="color:#c0392b;">{quartiles["bottom_25"]}</div>'
            '</div>'
            '<div style="flex:1;text-align:center;border-left:1px solid rgba(100,55,145,0.15);border-right:1px solid rgba(100,55,145,0.15);">'
            '<div style="color:#643791;font-weight:500;">Mid 50%</div>'
            f'<div style="color:#643791;">{quartiles["middle_50"]}</div>'
            '</div>'
            '<div style="flex:1;text-align:center;">'
            '<div style="color:#2e4500;font-weight:500;">Top 25%</div>'
            f'<div style="color:#2e4500;">{quartiles["top_25"]}</div>'
            '</div>'
            '</div>'
        )

    return (
        '<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{delta_html}'
        f'{quartile_html}'
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
        filters_dict: Dictionary of applied filters from session state
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


def sidebar_logo():
    """Build the JGP logo for the sidebar."""
    return '''
    <div class="jgp-logo-container">
        <div>
            <span class="jgp-logo-icon">Go</span>
            <span class="jgp-logo-text">Jobs Go Public</span>
        </div>
        <p class="jgp-logo-subtitle">Job Performance Dashboard</p>
    </div>
    '''


def main_logo():
    """Build the JGP logo for the main content area (above tabs)."""
    return '''
    <div class="main-logo">
        <span class="main-logo-icon">Go</span>
        <span class="main-logo-title">Job Performance Dashboard</span>
    </div>
    '''
