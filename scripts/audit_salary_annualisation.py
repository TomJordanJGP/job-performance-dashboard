#!/usr/bin/env python3
"""One-off audit of salary annualisation logic.

Pulls every row from `dashboard_vacancy_summary`, applies the dashboard's
`process_salary_columns()` from `data/processing.py`, attaches a
suspicion score per row, and writes a multi-sheet Excel:

  - all_vacancies  : every row with raw + annualised + flags
  - ranked_suspect : rows with any flag triggered, sorted by suspicion score
  - by_importer    : per-importer anomaly counts and rates

Run:
    venv/bin/python scripts/audit_salary_annualisation.py

Output: salary_audit_<YYYY-MM-DD>.xlsx in the project root.

Suspicion checks (computed on raw BigQuery values to surface scrape/parse errors):
  - min_gt_max_flag      : raw min_salary > raw max_salary
  - ratio_max_min        : raw max_salary / raw min_salary (NaN if either is missing/<=0)
  - ratio_flag           : ratio_max_min > 4 (real salary ranges cluster at 1.0-1.5x)
  - importer_zscore      : z-score of annual_mid_salary within the
                           (importer_name, effective_unit) cohort,
                           computed only when cohort size >= 10
  - zscore_flag          : |importer_zscore| > 2.5
  - suspicion_score      : count of flags triggered (0-3)
"""

import os
import sys
from datetime import date

import numpy as np
import pandas as pd

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

from google.oauth2.service_account import Credentials
from google.cloud import bigquery

from data.processing import process_salary_columns


PROJECT_ID = 'site-monitoring-421401'
DATASET_ID = 'job_data_export'
TABLE_ID = 'dashboard_vacancy_summary'

RATIO_THRESHOLD = 4.0
ZSCORE_THRESHOLD = 2.5
COHORT_MIN_SIZE = 10


def get_client():
    sa_path = os.path.join(project_dir, 'service_account.json')
    if not os.path.exists(sa_path):
        print(f"ERROR: service_account.json not found at {sa_path}")
        sys.exit(1)
    creds = Credentials.from_service_account_file(sa_path, scopes=[
        'https://www.googleapis.com/auth/bigquery',
        'https://www.googleapis.com/auth/drive.readonly',
    ])
    return bigquery.Client(credentials=creds, project=PROJECT_ID)


def derive_effective_unit(row):
    unit = row.get('salary_unit')
    if pd.notna(unit) and str(unit).strip():
        return str(unit).strip().lower()
    ref = row.get('min_salary') if pd.notna(row.get('min_salary')) else row.get('max_salary')
    if pd.notna(ref):
        if ref < 25:
            return 'hour'
        elif ref < 500:
            return 'day'
    return 'year'


def compute_ratio(row):
    mn, mx = row['min_salary'], row['max_salary']
    if pd.isna(mn) or pd.isna(mx) or mn <= 0 or mx <= 0:
        return np.nan
    return mx / mn


def attach_suspicion_columns(df):
    df = df.copy()

    # Flag 1: min > max in raw values
    both_present = df['min_salary'].notna() & df['max_salary'].notna()
    df['min_gt_max_flag'] = False
    df.loc[both_present & (df['min_salary'] > df['max_salary']), 'min_gt_max_flag'] = True

    # Flag 2: max/min ratio > threshold
    df['ratio_max_min'] = df.apply(compute_ratio, axis=1)
    df['ratio_flag'] = df['ratio_max_min'] > RATIO_THRESHOLD
    df.loc[df['ratio_max_min'].isna(), 'ratio_flag'] = False

    # Flag 3: z-score within (importer_name, effective_unit) cohort
    df['importer_zscore'] = np.nan
    has_data = df['has_salary_data']
    cohort_keys = df.loc[has_data, ['importer_name', 'effective_unit']].fillna('(unknown)')
    df.loc[has_data, '_cohort'] = cohort_keys.agg(' | '.join, axis=1)

    cohort_stats = df[has_data].groupby('_cohort')['annual_mid_salary'].agg(['mean', 'std', 'count'])
    big_enough = cohort_stats[cohort_stats['count'] >= COHORT_MIN_SIZE]

    for cohort, stats in big_enough.iterrows():
        if pd.isna(stats['std']) or stats['std'] == 0:
            continue
        mask = df['_cohort'] == cohort
        df.loc[mask, 'importer_zscore'] = (
            (df.loc[mask, 'annual_mid_salary'] - stats['mean']) / stats['std']
        )

    df['zscore_flag'] = df['importer_zscore'].abs() > ZSCORE_THRESHOLD
    df.loc[df['importer_zscore'].isna(), 'zscore_flag'] = False

    df = df.drop(columns=['_cohort'])

    # Composite score
    df['suspicion_score'] = (
        df['min_gt_max_flag'].astype(int)
        + df['ratio_flag'].astype(int)
        + df['zscore_flag'].astype(int)
    )

    return df


def build_importer_summary(df):
    """One row per importer: counts and anomaly rates."""
    grp = df.groupby(['importer_ID', 'importer_name'], dropna=False)
    summary = grp.agg(
        vacancy_count=('entity_id_str', 'size'),
        with_salary_count=('has_salary_data', 'sum'),
        min_gt_max_count=('min_gt_max_flag', 'sum'),
        ratio_flag_count=('ratio_flag', 'sum'),
        zscore_flag_count=('zscore_flag', 'sum'),
        any_flag_count=('suspicion_score', lambda s: (s > 0).sum()),
        median_annual_mid=('annual_mid_salary', 'median'),
        mean_ratio=('ratio_max_min', 'mean'),
    ).reset_index()

    summary['pct_with_salary'] = (summary['with_salary_count'] / summary['vacancy_count'] * 100).round(1)
    summary['pct_any_flag_of_priced'] = np.where(
        summary['with_salary_count'] > 0,
        (summary['any_flag_count'] / summary['with_salary_count'] * 100).round(1),
        np.nan,
    )

    summary = summary[[
        'importer_ID', 'importer_name', 'vacancy_count',
        'with_salary_count', 'pct_with_salary',
        'min_gt_max_count', 'ratio_flag_count', 'zscore_flag_count',
        'any_flag_count', 'pct_any_flag_of_priced',
        'median_annual_mid', 'mean_ratio',
    ]]

    return summary.sort_values(
        ['pct_any_flag_of_priced', 'any_flag_count'],
        ascending=[False, False],
        na_position='last',
    )


def main():
    client = get_client()

    print(f"Pulling rows from {PROJECT_ID}.{DATASET_ID}.{TABLE_ID}...")
    sql = f"""
        SELECT
          entity_id_str,
          external_id,
          importer_ID,
          importer_name,
          organization_name,
          min_salary,
          max_salary,
          salary_exact,
          salary_free_text,
          currency_code,
          salary_unit
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
    """
    raw = client.query(sql).to_dataframe()
    total_rows = len(raw)
    print(f"  {total_rows:,} rows fetched.")

    # Run dashboard's salary processing on a slim copy (it expects specific columns)
    salary_input = raw[['min_salary', 'max_salary', 'salary_exact',
                        'salary_free_text', 'currency_code', 'salary_unit']].copy()
    processed = process_salary_columns(salary_input)

    out = pd.DataFrame({
        'entity_id_str': raw['entity_id_str'].values,
        'external_id': raw['external_id'].values,
        'importer_ID': raw['importer_ID'].values,
        'importer_name': raw['importer_name'].values,
        'organization_name': raw['organization_name'].values,
        'min_salary': raw['min_salary'].values,
        'max_salary': raw['max_salary'].values,
        'salary_exact': raw['salary_exact'].values,
        'salary_free_text': raw['salary_free_text'].values,
        'currency_code': raw['currency_code'].values,
        'salary_unit': raw['salary_unit'].values,
        'effective_unit': processed.apply(derive_effective_unit, axis=1).values,
        'salary_source': processed['salary_source'].values,
        'annual_min_salary': processed['annual_min_salary'].values,
        'annual_max_salary': processed['annual_max_salary'].values,
        'annual_mid_salary': processed['annual_mid_salary'].values,
        'has_salary_data': processed['has_salary_data'].values,
    })

    out = attach_suspicion_columns(out)

    has_salary = int(out['has_salary_data'].sum())
    pct = (has_salary / total_rows * 100) if total_rows else 0.0
    print(f"\nSalary coverage: {has_salary:,} / {total_rows:,} ({pct:.1f}%)")
    print("\nBreakdown by salary_source:")
    print(out['salary_source'].value_counts(dropna=False).to_string())

    print("\nSuspicion flags (priced rows only):")
    priced = out[out['has_salary_data']]
    print(f"  min > max         : {int(priced['min_gt_max_flag'].sum()):,}")
    print(f"  ratio > {RATIO_THRESHOLD:.0f}x         : {int(priced['ratio_flag'].sum()):,}")
    print(f"  |z| > {ZSCORE_THRESHOLD} (in cohort): {int(priced['zscore_flag'].sum()):,}")
    print(f"  any flag          : {int((priced['suspicion_score'] > 0).sum()):,}")

    importer_summary = build_importer_summary(out)
    ranked = (
        out[(out['suspicion_score'] > 0) & out['has_salary_data']]
        .sort_values(
            ['suspicion_score', 'min_gt_max_flag', 'ratio_max_min', 'importer_zscore'],
            ascending=[False, False, False, False],
            na_position='last',
        )
    )

    out_path = os.path.join(project_dir, f"salary_audit_{date.today().isoformat()}.xlsx")
    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        out.to_excel(writer, sheet_name='all_vacancies', index=False)
        ranked.to_excel(writer, sheet_name='ranked_suspect', index=False)
        importer_summary.to_excel(writer, sheet_name='by_importer', index=False)

    print(f"\nWrote {out_path}")
    print(f"  all_vacancies  : {len(out):,} rows")
    print(f"  ranked_suspect : {len(ranked):,} rows")
    print(f"  by_importer    : {len(importer_summary):,} rows")


if __name__ == '__main__':
    main()
