"""Headless smoke test for the new salary-benchmark-by-occupation chart.

Exercises the same code path as `views.client_report.render_client_report`
without spinning up Streamlit. Loads real BigQuery data, picks a few
representative clients, builds the figure, and writes the PNG to
`smoke_test_salary_benchmark_<client>.png` so we can eyeball it.

Run:
    venv/bin/python scripts/smoke_test_salary_benchmark.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Make project root importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from data.loader import load_all_data, load_client_hq_regions  # noqa: E402
from data.processing import (  # noqa: E402
    add_occupation_column,
    process_salary_columns,
    prepare_enriched_data,
)
from theme.colors import JGP_COLORS, JGP_PLOTLY_TEMPLATE  # noqa: E402


def build_figure(df: pd.DataFrame, client_df: pd.DataFrame, selected_client: str,
                 client_region: str | None) -> tuple[go.Figure | None, dict]:
    """Mirror of the section block in views/client_report.py.

    Returns (figure, info_dict). figure is None when there are no qualifying
    occupations.
    """
    info = {'client': selected_client, 'client_region': client_region}

    client_with_salary = client_df[client_df.get('has_salary_data', False) == True]
    info['client_with_salary_n'] = len(client_with_salary)
    if len(client_with_salary) == 0:
        info['skip_reason'] = 'no_client_salary_data'
        return None, info

    occ_counts = client_with_salary['occupation'].dropna().value_counts()
    qualifying = occ_counts[occ_counts >= 5]
    top_occupations = qualifying.head(10).index.tolist()
    info['qualifying_occupations'] = list(qualifying.index)
    info['top_occupations'] = top_occupations

    if len(top_occupations) == 0:
        info['skip_reason'] = 'no_occ_meets_min_5'
        return None, info

    df_regional_market = None
    if client_region and 'primary_uk_region' in df.columns:
        norm = client_region.strip().lower()
        df_regional_market = df[
            (df.get('has_salary_data', False) == True)
            & (df['primary_uk_region'].fillna('').str.strip().str.lower() == norm)
        ]
        if len(df_regional_market) == 0:
            df_regional_market = None
    info['has_regional_pool'] = df_regional_market is not None

    client_color = JGP_COLORS['negative']
    national_color = JGP_COLORS['amber']
    regional_color = JGP_COLORS['deep_green']

    per_occ = []
    for occ in top_occupations:
        client_occ = client_with_salary[client_with_salary['occupation'] == occ]
        client_mean = client_occ['annual_mid_salary'].mean()

        market_occ = df[(df['occupation'] == occ) & (df.get('has_salary_data', False) == True)]
        market_salaries = market_occ['annual_mid_salary'].dropna()
        national_mean = market_salaries.mean() if len(market_salaries) else np.nan

        if df_regional_market is not None:
            reg_vals = df_regional_market[df_regional_market['occupation'] == occ]['annual_mid_salary'].dropna()
            regional_mean = reg_vals.mean() if len(reg_vals) >= 3 else np.nan
            regional_n = len(reg_vals)
        else:
            regional_mean = np.nan
            regional_n = 0

        per_occ.append({
            'occupation': occ,
            'client_n': len(client_occ),
            'market_n': len(market_salaries),
            'regional_n': regional_n,
            'market_salaries': market_salaries,
            'client_mean': client_mean,
            'national_mean': national_mean,
            'regional_mean': regional_mean,
        })

    info['per_occupation'] = [
        {k: v for k, v in p.items() if k != 'market_salaries'}
        for p in per_occ
    ]

    any_regional = any(not pd.isna(p['regional_mean']) for p in per_occ)
    info['any_regional_line_drawn'] = any_regional

    n_occ = len(per_occ)
    n_cols = 2
    n_rows = (n_occ + n_cols - 1) // n_cols
    info['grid'] = f'{n_rows}x{n_cols}'

    subplot_titles = [
        f"{p['occupation']} — your n={p['client_n']}, market n={p['market_n']:,}"
        for p in per_occ
    ]

    fig = make_subplots(
        rows=n_rows, cols=n_cols,
        subplot_titles=subplot_titles,
        vertical_spacing=0.12,
        horizontal_spacing=0.10,
    )

    for i, p in enumerate(per_occ):
        row = i // n_cols + 1
        col = i % n_cols + 1
        fig.add_trace(
            go.Histogram(
                x=p['market_salaries'],
                nbinsx=25,
                marker_color=JGP_COLORS['primary'],
                opacity=0.85,
                showlegend=False,
            ),
            row=row, col=col,
        )
        if not pd.isna(p['client_mean']):
            fig.add_vline(x=p['client_mean'], line_width=2.5, line_color=client_color, row=row, col=col)
        if not pd.isna(p['national_mean']):
            fig.add_vline(x=p['national_mean'], line_width=2, line_color=national_color, row=row, col=col)
        if not pd.isna(p['regional_mean']):
            fig.add_vline(x=p['regional_mean'], line_width=2, line_color=regional_color, row=row, col=col)

    # Legend traces
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
                             line=dict(color=client_color, width=2.5), name='Your mean'), row=1, col=1)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
                             line=dict(color=national_color, width=2), name='National mean'), row=1, col=1)
    if any_regional:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
                                 line=dict(color=regional_color, width=2),
                                 name=f'Regional mean ({client_region})'), row=1, col=1)

    fig.update_layout(**JGP_PLOTLY_TEMPLATE['layout'])
    fig.update_layout(
        height=max(360, 240 * n_rows),
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.04, xanchor='left', x=0,
                    font=dict(size=12)),
        bargap=0.05,
    )
    fig.update_xaxes(tickformat=',', tickprefix='£')
    fig.update_annotations(font_size=12)

    return fig, info


def main():
    print("Loading data from BigQuery (will take a moment)...")
    vacancy_df, _, _, _ = load_all_data(days_back=365)
    print(f"  Loaded {len(vacancy_df):,} vacancy rows.")

    df = prepare_enriched_data(vacancy_df)
    df = add_occupation_column(df)
    df = process_salary_columns(df)
    print(f"  After enrichment: {len(df):,} rows, "
          f"{df['has_salary_data'].sum():,} with salary, "
          f"{df['occupation'].nunique():,} unique occupations.")

    hq_map = load_client_hq_regions()
    print(f"  Loaded HQ map: {len(hq_map):,} clients with known HQ region.")
    print()

    org_col = 'organization_name' if 'organization_name' in df.columns else 'importer_name'

    # Pick the 3 clients with the most salary-bearing rows that have ≥10 occupations meeting min-5 threshold
    salary_df = df[df['has_salary_data']]
    by_client = salary_df.groupby(org_col)['occupation'].count().sort_values(ascending=False)
    candidates = []
    for client_name, _ in by_client.items():
        cdf = salary_df[salary_df[org_col] == client_name]
        occs_meeting = (cdf['occupation'].dropna().value_counts() >= 5).sum()
        if occs_meeting >= 5:
            candidates.append((client_name, occs_meeting))
        if len(candidates) >= 4:
            break

    print("Test clients chosen:")
    for c, n in candidates:
        print(f"  - {c}: {n} occupations meet ≥5 threshold")
    print()

    out_dir = os.path.join(PROJECT_ROOT, 'tasks')
    os.makedirs(out_dir, exist_ok=True)

    for client_name, _ in candidates:
        client_df = df[df[org_col] == client_name].copy()
        client_region = hq_map.get(str(client_name).lower().strip())

        print(f"=== {client_name} ===")
        print(f"  HQ region: {client_region or '(none — central gov / multi-site)'}")

        fig, info = build_figure(df, client_df, str(client_name), client_region)

        if fig is None:
            print(f"  SKIPPED: {info.get('skip_reason')}")
            print()
            continue

        for p in info['per_occupation']:
            print(f"  - {p['occupation']:<35} client_n={p['client_n']:>3}  "
                  f"client_mean=£{p['client_mean']:>7,.0f}  "
                  f"nat_mean=£{p['national_mean']:>7,.0f}  "
                  f"reg_mean={'£%7.0f' % p['regional_mean'] if not pd.isna(p['regional_mean']) else '   --   '}  "
                  f"reg_n={p['regional_n']:>3}")

        safe_name = ''.join(ch if ch.isalnum() else '_' for ch in str(client_name))[:40]
        png_path = os.path.join(out_dir, f'smoke_salary_benchmark_{safe_name}.png')
        try:
            fig.write_image(png_path, width=1600, height=fig.layout.height or 1200, scale=2)
            print(f"  Wrote PNG: {png_path}")
        except Exception as e:
            print(f"  PNG export failed ({type(e).__name__}: {e}) — figure built OK in memory though.")
        print()

    print("Smoke test complete.")


if __name__ == '__main__':
    main()
