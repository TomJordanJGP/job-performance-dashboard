#!/usr/bin/env python3
"""Analyze empty-field rates across the three tables the dashboard loads.

Tables covered (matches data/loader.py):
  - dashboard_vacancy_summary
  - dashboard_daily_totals
  - dashboard_vacancy_region_summary

For every column:
  - NULL count
  - Empty-string / sentinel-empty count (strings only)
  - Effective-empty = NULL + sentinel-empty
  - % populated

Prints a per-table table + an overall cell-level total.
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

# Human-readable root cause per (table, field). Covers the interesting gaps;
# fields not listed fall back to a generic "Well populated" label.
REASONS = {
    # dashboard_vacancy_summary
    ("dashboard_vacancy_summary", "upgrades"): "Only set for premium/upgraded listings — most vacancies aren't upgraded, expected sparse",
    ("dashboard_vacancy_summary", "salary_exact"): "Alternative to min/max salary — most vacancies use the range form, expected sparse",
    ("dashboard_vacancy_summary", "salary_free_text"): "Alternative to structured salary — only set when free-text was provided",
    ("dashboard_vacancy_summary", "contract_type"): "Source-feed gap — ~88% empty at job_metadata level; not reliably populated by feeds",
    ("dashboard_vacancy_summary", "category"): "Source-feed gap — ~88% empty at job_metadata level; free-text field, not a taxonomy",
    ("dashboard_vacancy_summary", "salary_unit"): "Only populated when structured salary (min/max) is present",
    ("dashboard_vacancy_summary", "currency_code"): "Only populated when structured salary (min/max) is present",
    ("dashboard_vacancy_summary", "min_salary"): "Not all vacancies disclose salary",
    ("dashboard_vacancy_summary", "max_salary"): "Not all vacancies disclose salary",
    ("dashboard_vacancy_summary", "importer_ID"): "GA4-only vacancies with no matching job_metadata row",
    ("dashboard_vacancy_summary", "sites"): "GA4-only vacancies with no matching job_metadata row",
    ("dashboard_vacancy_summary", "occupational_fields"): "Mostly the 'Unknown/Other' importer (~95% empty for that source)",
    ("dashboard_vacancy_summary", "employment_type"): "Source-feed gap — not consistently populated upstream",
    ("dashboard_vacancy_summary", "uk_regions"): "Central-government multi-site orgs (MoD, MoJ, UKHSA, ONS) have no single HQ region — acceptable gap per lessons.md",
    ("dashboard_vacancy_summary", "primary_uk_region"): "Central-government multi-site orgs have no single HQ region — acceptable gap per lessons.md",
    ("dashboard_vacancy_summary", "end_date"): "Small number of vacancies without an expiry date set",
    ("dashboard_vacancy_summary", "organization_name"): "Rare data-quality gap (<0.1%)",
    ("dashboard_vacancy_summary", "start_date"): "Near-complete — isolated data-quality gaps",
    ("dashboard_vacancy_summary", "workflow_state"): "Near-complete — isolated data-quality gaps",
    ("dashboard_vacancy_summary", "entity_id_str"): "Single legacy/broken row",

    # dashboard_daily_totals
    ("dashboard_daily_totals", "avg_position_jgp"): "No GSC data before backfill start date — early days in the time series",
    ("dashboard_daily_totals", "avg_position_lg"): "No GSC data before backfill start date — early days in the time series",

    # dashboard_vacancy_region_summary
    ("dashboard_vacancy_region_summary", "upgrades"): "Only set for premium/upgraded listings — expected sparse",
    ("dashboard_vacancy_region_summary", "salary_exact"): "Alternative to min/max salary — expected sparse",
    ("dashboard_vacancy_region_summary", "salary_free_text"): "Alternative to structured salary",
    ("dashboard_vacancy_region_summary", "contract_type"): "Source-feed gap — ~88% empty upstream",
    ("dashboard_vacancy_region_summary", "category"): "Source-feed gap — ~88% empty upstream",
    ("dashboard_vacancy_region_summary", "raw_location"): "Vacancies without a parseable location string — location exploded from HQ-region fallback only",
    ("dashboard_vacancy_region_summary", "town_city"): "Vacancies without a parseable location string — location exploded from HQ-region fallback only",
    ("dashboard_vacancy_region_summary", "salary_unit"): "Only populated when structured salary is present",
    ("dashboard_vacancy_region_summary", "currency_code"): "Only populated when structured salary is present",
    ("dashboard_vacancy_region_summary", "min_salary"): "Not all vacancies disclose salary",
    ("dashboard_vacancy_region_summary", "max_salary"): "Not all vacancies disclose salary",
    ("dashboard_vacancy_region_summary", "importer_ID"): "GA4-only vacancies with no matching job_metadata row",
    ("dashboard_vacancy_region_summary", "sites"): "GA4-only vacancies with no matching job_metadata row",
    ("dashboard_vacancy_region_summary", "occupational_fields"): "Mostly the 'Unknown/Other' importer (~95% empty for that source)",
    ("dashboard_vacancy_region_summary", "external_id"): "Not all vacancies carry an external_id (GA4-only rows)",
    ("dashboard_vacancy_region_summary", "employment_type"): "Source-feed gap — not consistently populated upstream",
    ("dashboard_vacancy_region_summary", "end_date"): "Small number of vacancies without an expiry date set",
    ("dashboard_vacancy_region_summary", "organization_name"): "Rare data-quality gap (<0.1%)",
    ("dashboard_vacancy_region_summary", "start_date"): "Near-complete — isolated data-quality gaps",
    ("dashboard_vacancy_region_summary", "workflow_state"): "Near-complete — isolated data-quality gaps",
    ("dashboard_vacancy_region_summary", "entity_id_str"): "Single legacy/broken row",
}


def reason_for(table, field, empty_count):
    if empty_count == 0:
        return "Always populated"
    return REASONS.get((table, field), "Well populated — isolated gaps")

# Exact tables/columns the dashboard loads (data/loader.py)
DASHBOARD_TABLES = {
    "dashboard_vacancy_summary": [
        "entity_id_str", "first_event_date", "last_event_date",
        "clicks", "applies", "title", "organization_name",
        "uk_regions", "primary_uk_region", "occupational_fields",
        "importer_ID", "importer_name", "workflow_state", "upgrades",
        "start_date", "end_date", "category", "contract_type",
        "employment_type", "min_salary", "max_salary", "currency_code",
        "salary_free_text", "salary_exact", "salary_unit", "sites",
    ],
    "dashboard_daily_totals": [
        "event_date",
        "impressions", "impressions_jgp", "impressions_lg",
        "gb_impressions_jgp", "gb_impressions_lg",
        "gsc_clicks", "gsc_clicks_jgp", "gsc_clicks_lg",
        "gb_gsc_clicks_jgp", "gb_gsc_clicks_lg",
        "avg_position_jgp", "avg_position_lg",
        "job_listing_rich_jgp", "job_listing_rich_lg",
        "job_detail_rich_jgp", "job_detail_rich_lg",
        "clicks", "clicks_jgp", "clicks_lg",
        "applies", "applies_jgp", "applies_lg",
        "active_vacancies", "active_jgp", "active_lg",
    ],
    "dashboard_vacancy_region_summary": [
        "entity_id_str", "external_id", "uk_region", "raw_location",
        "town_city", "first_event_date", "last_event_date",
        "clicks", "applies", "title", "organization_name",
        "occupational_fields", "importer_ID", "importer_name",
        "workflow_state", "upgrades", "start_date", "end_date",
        "category", "contract_type", "employment_type",
        "min_salary", "max_salary", "currency_code",
        "salary_free_text", "salary_exact", "salary_unit", "sites",
    ],
}


def get_client():
    sa = os.path.join(project_dir, "service_account.json")
    if not os.path.exists(sa):
        print(f"ERROR: {sa} not found")
        sys.exit(1)
    creds = Credentials.from_service_account_file(
        sa, scopes=["https://www.googleapis.com/auth/bigquery"]
    )
    return bigquery.Client(credentials=creds, project=BQ_PROJECT)


def get_column_types(client, table):
    """Return {column_name: data_type} for a table from INFORMATION_SCHEMA."""
    q = f"""
    SELECT column_name, data_type
    FROM `{BQ_PROJECT}.{BQ_DATASET}.INFORMATION_SCHEMA.COLUMNS`
    WHERE table_name = '{table}'
    """
    return {
        r.column_name: r.data_type
        for r in client.query(q).result()
    }


def build_empty_query(table, columns, col_types):
    """One SELECT that returns row count + empty count for each column."""
    parts = ["COUNT(*) AS _row_count"]
    for c in columns:
        dt = col_types.get(c, "").upper()
        if dt == "STRING":
            # NULL OR empty/whitespace-only OR sentinel values
            parts.append(
                f"COUNTIF({c} IS NULL OR TRIM({c}) IN "
                f"('', '(none)', '(not set)', 'NULL', 'null')) "
                f"AS `{c}_empty`"
            )
        else:
            parts.append(f"COUNTIF({c} IS NULL) AS `{c}_empty`")
    select = ",\n  ".join(parts)
    return f"SELECT\n  {select}\nFROM `{BQ_PROJECT}.{BQ_DATASET}.{table}`"


def analyze_table(client, table, columns):
    col_types = get_column_types(client, table)
    missing = [c for c in columns if c not in col_types]
    if missing:
        print(f"  WARN: columns not in table: {missing}")
        columns = [c for c in columns if c in col_types]

    sql = build_empty_query(table, columns, col_types)
    row = list(client.query(sql).result())[0]
    row_count = row["_row_count"]

    stats = []
    total_empty = 0
    for c in columns:
        e = row[f"{c}_empty"]
        total_empty += e
        pct_pop = (1 - e / row_count) * 100 if row_count else 0
        stats.append({
            "column": c,
            "type": col_types[c],
            "empty": e,
            "populated": row_count - e,
            "pct_populated": pct_pop,
        })
    stats.sort(key=lambda x: x["pct_populated"])

    total_cells = row_count * len(columns)
    return {
        "table": table,
        "rows": row_count,
        "cols": len(columns),
        "total_cells": total_cells,
        "total_empty_cells": total_empty,
        "pct_empty_cells": total_empty / total_cells * 100 if total_cells else 0,
        "stats": stats,
    }


def print_report(results):
    print()
    print("=" * 78)
    print(f"  DASHBOARD EMPTY-FIELD ANALYSIS — {datetime.now():%Y-%m-%d %H:%M}")
    print("=" * 78)

    grand_cells = 0
    grand_empty = 0

    for r in results:
        grand_cells += r["total_cells"]
        grand_empty += r["total_empty_cells"]
        print()
        print(f"  {r['table']}")
        print(f"    rows: {r['rows']:,}    columns: {r['cols']}")
        print(f"    total cells: {r['total_cells']:,}")
        print(f"    empty cells: {r['total_empty_cells']:,}  "
              f"({r['pct_empty_cells']:.1f}%)")
        print()
        print(f"    {'column':<32s} {'type':<12s} {'empty':>10s} "
              f"{'populated':>10s} {'% pop':>7s}")
        print(f"    {'-' * 32} {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 7}")
        for s in r["stats"]:
            print(f"    {s['column']:<32s} {s['type']:<12s} "
                  f"{s['empty']:>10,} {s['populated']:>10,} "
                  f"{s['pct_populated']:>6.1f}%")

    print()
    print("=" * 78)
    print(f"  OVERALL")
    print(f"    grand-total cells: {grand_cells:,}")
    print(f"    grand-empty cells: {grand_empty:,}  "
          f"({grand_empty / grand_cells * 100:.1f}%)")
    print("=" * 78)


def write_excel(results, output_path):
    """Write multi-tab Excel: one tab per table + a Summary tab.

    Each per-table tab: field, type, total_rows, empty, populated,
    % empty, % complete, reason. Sorted worst-first.
    """
    summary_rows = []
    for r in results:
        summary_rows.append({
            "Table": r["table"],
            "Rows": r["rows"],
            "Columns": r["cols"],
            "Total cells": r["total_cells"],
            "Empty cells": r["total_empty_cells"],
            "% empty": round(r["pct_empty_cells"], 2),
            "% complete": round(100 - r["pct_empty_cells"], 2),
        })
    summary_df = pd.DataFrame(summary_rows)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        for r in results:
            rows = []
            for s in r["stats"]:
                pct_empty = 100 - s["pct_populated"]
                rows.append({
                    "field": s["column"],
                    "type": s["type"],
                    "total_rows": r["rows"],
                    "empty": s["empty"],
                    "populated": s["populated"],
                    "% empty": round(pct_empty, 2),
                    "% complete": round(s["pct_populated"], 2),
                    "reason": reason_for(r["table"], s["column"], s["empty"]),
                })
            df = pd.DataFrame(rows)
            # Excel sheet name limit is 31 chars
            sheet = r["table"][:31]
            df.to_excel(writer, sheet_name=sheet, index=False)

            # Set column widths for readability
            ws = writer.sheets[sheet]
            widths = {"A": 28, "B": 12, "C": 12, "D": 10, "E": 11,
                      "F": 10, "G": 12, "H": 80}
            for col, w in widths.items():
                ws.column_dimensions[col].width = w


def main():
    client = get_client()
    results = []
    for table, cols in DASHBOARD_TABLES.items():
        print(f"\n  Analyzing {table}...")
        results.append(analyze_table(client, table, cols))
    print_report(results)

    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = os.path.join(
        project_dir, f"dashboard_empty_fields_{date_str}.xlsx"
    )
    write_excel(results, output_path)
    print(f"\n  Excel report: {output_path}")


if __name__ == "__main__":
    main()
