"""JGP brand color constants and Plotly chart template."""

# Brand colors
JGP_COLORS = {
    'primary': '#643791',        # Brand Purple
    'accent': '#e5ff6e',         # Bold Green
    'supporting': '#9c67d3',     # Supporting Purple
    'light_purple': '#e8e0f2',   # Light Purple
    'deep_blue': '#240f45',      # Deep Blue
    'deep_green': '#2e4500',     # Deep Green
    'beige': '#f0f3e1',          # Beige
    'pink': '#ffc4c4',           # Pink
    'light_blue': '#defae8',     # Light Blue
    'light_green': '#d6dbb2',    # Light Green
    'blue': '#bad9e5',           # Blue
    'white': '#ffffff',
    'black': '#000000',
    'positive': '#2e4500',       # Deep Green for positive deltas
    'negative': '#c0392b',       # Red for negative deltas
    'neutral': '#9c67d3',        # Supporting Purple for neutral
}

# Plotly chart template with JGP branding
JGP_PLOTLY_TEMPLATE = dict(
    layout=dict(
        font=dict(family="DM Sans, sans-serif", color=JGP_COLORS['deep_blue'], size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[
            JGP_COLORS['primary'],
            JGP_COLORS['deep_green'],
            JGP_COLORS['supporting'],
            '#e5a000',  # Warm amber for contrast
            JGP_COLORS['light_purple'],
            JGP_COLORS['deep_blue'],
        ],
        hoverlabel=dict(
            bgcolor=JGP_COLORS['deep_blue'],
            font_color=JGP_COLORS['white'],
            font_family="DM Sans, sans-serif",
        ),
        xaxis=dict(gridcolor=JGP_COLORS['light_purple'], gridwidth=1),
        yaxis=dict(gridcolor=JGP_COLORS['light_purple'], gridwidth=1),
        legend=dict(
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor=JGP_COLORS['light_purple'],
            borderwidth=1,
            font=dict(size=12),
        ),
        margin=dict(t=40, b=40, l=40, r=20),
    )
)

# Heatmap color scale (light purple to deep purple)
JGP_HEATMAP_COLORSCALE = [
    [0.0, JGP_COLORS['beige']],
    [0.25, JGP_COLORS['light_purple']],
    [0.5, JGP_COLORS['supporting']],
    [0.75, JGP_COLORS['primary']],
    [1.0, JGP_COLORS['deep_blue']],
]
