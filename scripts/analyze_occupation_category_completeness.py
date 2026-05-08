#!/usr/bin/env python3
"""Deep-dive completeness review for occupational_fields and category.

Tables analysed (the ones the Streamlit dashboard actually loads):
  - dashboard_vacancy_summary        (one row per vacancy)
  - dashboard_vacancy_region_summary (one row per vacancy x region)

Slices produced (per table):
  1. Overall row-level completeness   - either field, both, neither
  2. Engagement-weighted completeness - clicks and applies share landing on populated rows
  3. By importer / sites              - which feeds populate vs not
  4. By organisation (top 30 by clicks)
  5. Distinct tokens in occupational_fields (pipe-split, top 30)
  6. Distinct values in category (top 30)
  7. Monthly trend on last_event_date - is upstream improving?
  8. Cross-table comparison           - row + click totals side by side

Note on region table click counts: dashboard_vacancy_region_summary repeats the
full click/apply count on each region row (a 3-region vacancy contributes 3
rows each carrying full clicks). Sums here are "click-impressions across
region rows", not unique clicks - that is intentional and matches how the
dashboard shows region-filtered charts. The vacancy_summary slices use
unique clicks.

Output:
  - Console summary
  - Excel: occupation_category_review_<YYYY-MM-DD>.xlsx at repo root
"""

import os
import sys
from datetime import datetime

import pandas as pd

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)

from google.oauth2.service_account import Credentials
from google.cloud import bigquery


BQ_PROJECT = "site-monitoring-421401"
BQ_DATASET = "job_data_export"

TABLES = [
    "dashboard_vacancy_summary",
    "dashboard_vacancy_region_summary",
]

# Sentinel-empty predicate matches scripts/analyze_dashboard_empty_fields.py
SENTINELS = "('', '(none)', '(not set)', 'NULL', 'null')"


def is_empty(col):
    return f"({col} IS NULL OR TRIM({col}) IN {SENTINELS})"


def is_pop(col):
    return f"NOT {is_empty(col)}"


OCC_EMPTY = is_empty("occupational_fields")
OCC_POP = is_pop("occupational_fields")
CAT_EMPTY = is_empty("category")
CAT_POP = is_pop("category")


def get_client():
    sa = os.path.join(project_dir, "service_account.json")
    if not os.path.exists(sa):
        print(f"ERROR: {sa} not found", file=sys.stderr)
        sys.exit(1)
    creds = Credentials.from_service_account_file(
        sa, scopes=["https://www.googleapis.com/auth/bigquery"]
    )
    return bigquery.Client(credentials=creds, project=BQ_PROJECT)


def fq(table):
    return f"`{BQ_PROJECT}.{BQ_DATASET}.{table}`"


def q_overall(client, table):
    sql = f"""
    SELECT
      COUNT(*) AS rows_total,
      COUNTIF({OCC_POP}) AS occ_pop,
      COUNTIF({CAT_POP}) AS cat_pop,
      COUNTIF({OCC_POP} AND {CAT_POP}) AS both_pop,
      COUNTIF({OCC_EMPTY} AND {CAT_EMPTY}) AS neither_pop
    FROM {fq(table)}
    """
    return client.query(sql).to_dataframe()


def q_weighted(client, table):
    sql = f"""
    SELECT
      SUM(clicks)                             AS clicks_total,
      SUM(IF({OCC_POP}, clicks, 0))           AS clicks_with_occ,
      SUM(IF({CAT_POP}, clicks, 0))           AS clicks_with_cat,
      SUM(IF({OCC_POP} AND {CAT_POP},
             clicks, 0))                      AS clicks_with_both,
      SUM(applies)                            AS applies_total,
      SUM(IF({OCC_POP}, applies, 0))          AS applies_with_occ,
      SUM(IF({CAT_POP}, applies, 0))          AS applies_with_cat,
      SUM(IF({OCC_POP} AND {CAT_POP},
             applies, 0))                     AS applies_with_both
    FROM {fq(table)}
    """
    return client.query(sql).to_dataframe()


def q_by_importer(client, table):
    sql = f"""
    SELECT
      COALESCE(importer_name, '(no importer)') AS importer,
      COALESCE(sites, '(no site)')             AS sites,
      COUNT(*)                                  AS row_count,
      SUM(clicks)                               AS clicks,
      SUM(applies)                              AS applies,
      COUNTIF({OCC_POP})                        AS occ_pop,
      COUNTIF({CAT_POP})                        AS cat_pop,
      ROUND(SAFE_DIVIDE(COUNTIF({OCC_POP}), COUNT(*)) * 100, 1) AS pct_occ_pop,
      ROUND(SAFE_DIVIDE(COUNTIF({CAT_POP}), COUNT(*)) * 100, 1) AS pct_cat_pop
    FROM {fq(table)}
    GROUP BY importer, sites
    ORDER BY row_count DESC
    """
    return client.query(sql).to_dataframe()


def q_by_org_top30(client, table):
    sql = f"""
    SELECT
      COALESCE(organization_name, '(no org)') AS organisation,
      COUNT(*)                                AS row_count,
      SUM(clicks)                             AS clicks,
      SUM(applies)                            AS applies,
      COUNTIF({OCC_POP})                      AS occ_pop,
      COUNTIF({CAT_POP})                      AS cat_pop,
      ROUND(SAFE_DIVIDE(COUNTIF({OCC_POP}), COUNT(*)) * 100, 1) AS pct_occ_pop,
      ROUND(SAFE_DIVIDE(COUNTIF({CAT_POP}), COUNT(*)) * 100, 1) AS pct_cat_pop
    FROM {fq(table)}
    GROUP BY organisation
    ORDER BY clicks DESC
    LIMIT 30
    """
    return client.query(sql).to_dataframe()


def q_occ_tokens(client, table):
    sql = f"""
    WITH split AS (
      SELECT TRIM(token) AS token, clicks, applies
      FROM {fq(table)},
      UNNEST(SPLIT(occupational_fields, '|')) AS token
      WHERE {OCC_POP}
    )
    SELECT
      token,
      COUNT(*)     AS row_count,
      SUM(clicks)  AS clicks,
      SUM(applies) AS applies
    FROM split
    WHERE token != ''
    GROUP BY token
    ORDER BY row_count DESC
    LIMIT 30
    """
    return client.query(sql).to_dataframe()


def q_occ_distinct_count(client, table):
    sql = f"""
    SELECT COUNT(DISTINCT TRIM(token)) AS distinct_tokens
    FROM {fq(table)},
    UNNEST(SPLIT(occupational_fields, '|')) AS token
    WHERE {OCC_POP} AND TRIM(token) != ''
    """
    return int(list(client.query(sql).result())[0]["distinct_tokens"])


def q_categories(client, table):
    sql = f"""
    SELECT
      category,
      COUNT(*)     AS row_count,
      SUM(clicks)  AS clicks,
      SUM(applies) AS applies
    FROM {fq(table)}
    WHERE {CAT_POP}
    GROUP BY category
    ORDER BY row_count DESC
    LIMIT 30
    """
    return client.query(sql).to_dataframe()


def q_cat_distinct_count(client, table):
    sql = f"""
    SELECT COUNT(DISTINCT category) AS distinct_categories
    FROM {fq(table)}
    WHERE {CAT_POP}
    """
    return int(list(client.query(sql).result())[0]["distinct_categories"])


def q_monthly_trend(client, table):
    sql = f"""
    SELECT
      FORMAT_DATE('%Y-%m', DATE(last_event_date)) AS month,
      COUNT(*)            AS row_count,
      SUM(clicks)         AS clicks,
      COUNTIF({OCC_POP})  AS occ_pop,
      COUNTIF({CAT_POP})  AS cat_pop,
      ROUND(SAFE_DIVIDE(COUNTIF({OCC_POP}), COUNT(*)) * 100, 1) AS pct_occ_pop,
      ROUND(SAFE_DIVIDE(COUNTIF({CAT_POP}), COUNT(*)) * 100, 1) AS pct_cat_pop
    FROM {fq(table)}
    WHERE last_event_date IS NOT NULL
    GROUP BY month
    ORDER BY month
    """
    return client.query(sql).to_dataframe()


def build_summary(per_table):
    """Flatten Q1 + Q2 outputs from each table into a single Summary frame."""
    rows = []
    for table, slices in per_table.items():
        ov = slices["overall"].iloc[0]
        wt = slices["weighted"].iloc[0]
        total = int(ov["rows_total"]) or 1
        clicks_total = int(wt["clicks_total"] or 0) or 1
        applies_total = int(wt["applies_total"] or 0) or 1

        rows.append({
            "Table": table,
            "Rows": int(ov["rows_total"]),
            "Clicks": int(wt["clicks_total"] or 0),
            "Applies": int(wt["applies_total"] or 0),
            "% rows w/ occupational_fields": round(int(ov["occ_pop"]) / total * 100, 2),
            "% rows w/ category":            round(int(ov["cat_pop"]) / total * 100, 2),
            "% rows w/ both":                round(int(ov["both_pop"]) / total * 100, 2),
            "% rows w/ neither":             round(int(ov["neither_pop"]) / total * 100, 2),
            "% clicks w/ occupational_fields": round(int(wt["clicks_with_occ"] or 0) / clicks_total * 100, 2),
            "% clicks w/ category":            round(int(wt["clicks_with_cat"] or 0) / clicks_total * 100, 2),
            "% applies w/ occupational_fields": round(int(wt["applies_with_occ"] or 0) / applies_total * 100, 2),
            "% applies w/ category":            round(int(wt["applies_with_cat"] or 0) / applies_total * 100, 2),
            "Distinct occ tokens": slices["occ_distinct"],
            "Distinct categories": slices["cat_distinct"],
        })
    return pd.DataFrame(rows)


def print_console(summary, per_table):
    print()
    print("=" * 88)
    print(f"  OCCUPATIONS & CATEGORIES COMPLETENESS  -  {datetime.now():%Y-%m-%d %H:%M}")
    print("=" * 88)
    for _, r in summary.iterrows():
        print()
        print(f"  {r['Table']}")
        print(f"    rows: {r['Rows']:>10,}    clicks: {r['Clicks']:>12,}    applies: {r['Applies']:>10,}")
        print(f"    occupational_fields:  rows {r['% rows w/ occupational_fields']:>5.1f}%   "
              f"clicks {r['% clicks w/ occupational_fields']:>5.1f}%   "
              f"applies {r['% applies w/ occupational_fields']:>5.1f}%   "
              f"({r['Distinct occ tokens']:,} distinct tokens)")
        print(f"    category:             rows {r['% rows w/ category']:>5.1f}%   "
              f"clicks {r['% clicks w/ category']:>5.1f}%   "
              f"applies {r['% applies w/ category']:>5.1f}%   "
              f"({r['Distinct categories']:,} distinct values)")
        print(f"    both populated:       {r['% rows w/ both']:>5.1f}% of rows")
        print(f"    neither populated:    {r['% rows w/ neither']:>5.1f}% of rows")

    print()
    print("=" * 88)
    print("  TOP IMPORTERS (vacancy_summary, by row count)")
    print("=" * 88)
    imp = per_table["dashboard_vacancy_summary"]["importer"].head(15)
    for _, r in imp.iterrows():
        print(f"    {r['importer'][:40]:<40s} "
              f"rows={int(r['row_count']):>7,}  "
              f"occ%={r['pct_occ_pop'] or 0:>5.1f}  "
              f"cat%={r['pct_cat_pop'] or 0:>5.1f}")
    print()


def write_excel(summary, per_table, output_path):
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)

        for table, slices in per_table.items():
            # Tab name prefix - 'vs' or 'rs' to keep under 31 chars
            prefix = "vs" if table == "dashboard_vacancy_summary" else "rs"

            slices["overall"].to_excel(writer, sheet_name=f"{prefix}_1_overall", index=False)
            slices["weighted"].to_excel(writer, sheet_name=f"{prefix}_2_weighted", index=False)
            slices["importer"].to_excel(writer, sheet_name=f"{prefix}_3_by_importer", index=False)
            slices["org"].to_excel(writer, sheet_name=f"{prefix}_4_by_org_top30", index=False)
            slices["occ_tokens"].to_excel(writer, sheet_name=f"{prefix}_5_occ_tokens", index=False)
            slices["categories"].to_excel(writer, sheet_name=f"{prefix}_6_categories", index=False)
            slices["monthly"].to_excel(writer, sheet_name=f"{prefix}_7_monthly_trend", index=False)

        # Width tweaks for readability on the Summary tab
        ws = writer.sheets["Summary"]
        ws.column_dimensions["A"].width = 38
        for col in "BCDEFGHIJKLM":
            ws.column_dimensions[col].width = 18


def main():
    client = get_client()
    per_table = {}

    for table in TABLES:
        print(f"  Analysing {table}...")
        per_table[table] = {
            "overall":     q_overall(client, table),
            "weighted":    q_weighted(client, table),
            "importer":    q_by_importer(client, table),
            "org":         q_by_org_top30(client, table),
            "occ_tokens":  q_occ_tokens(client, table),
            "categories":  q_categories(client, table),
            "monthly":     q_monthly_trend(client, table),
            "occ_distinct": q_occ_distinct_count(client, table),
            "cat_distinct": q_cat_distinct_count(client, table),
        }

    summary = build_summary(per_table)
    print_console(summary, per_table)

    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = os.path.join(
        project_dir, f"occupation_category_review_{date_str}.xlsx"
    )
    write_excel(summary, per_table, output_path)
    print(f"  Excel report: {output_path}")


if __name__ == "__main__":
    main()
