#!/usr/bin/env python3
"""Check data completeness across BigQuery dashboard tables.

Identifies vacancies with empty fields across three tables:
- dashboard_vacancy_summary
- dashboard_media_summary
- job_metadata

Outputs: console summary + Excel file with per-vacancy detail.

Usage:
    python scripts/check_data_completeness.py
    python scripts/check_data_completeness.py --since 2026-01-01
    python scripts/check_data_completeness.py --table vacancy_summary
    python scripts/check_data_completeness.py --output my_report.xlsx
    python scripts/check_data_completeness.py --dry-run
"""

import os
import sys
import argparse
from datetime import datetime

import pandas as pd

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)

BQ_PROJECT = "site-monitoring-421401"
BQ_DATASET = "job_data_export"

# ---------------------------------------------------------------------------
# Table configurations
# Each table defines its vacancy ID column, optional date filter column,
# and fields grouped by type (determines "empty" definition).
# ---------------------------------------------------------------------------

TABLE_CONFIGS = {
    "vacancy_summary": {
        "table": "dashboard_vacancy_summary",
        "id_col": "entity_id_str",
        "date_filter_col": "first_event_date",
        "string_fields": [
            "title", "organization_name", "uk_regions", "primary_uk_region",
            "occupational_fields", "importer_name", "workflow_state",
            "upgrades", "category", "contract_type", "employment_type",
            "currency_code", "salary_free_text", "salary_unit",
        ],
        "numeric_fields": [
            "clicks", "applies", "min_salary", "max_salary",
            "salary_exact", "importer_ID",
        ],
        "date_fields": [
            "first_event_date", "last_event_date", "start_date", "end_date",
        ],
        # Extra columns to include in the gaps sheet for context
        "context_cols": ["title", "organization_name"],
    },
    "media_summary": {
        "table": "dashboard_media_summary",
        "id_col": "entity_id_str",
        "date_filter_col": None,  # no date column in this table
        "string_fields": [
            "importer_name", "source", "medium", "campaign",
        ],
        "numeric_fields": [
            "clicks", "applies", "importer_ID",
        ],
        "date_fields": [],
        "context_cols": [],
        # Use MIN aggregation: field is empty only if ALL rows for that
        # vacancy lack it (vacancy has multiple source rows).
        "use_min_agg": True,
    },
    "job_metadata": {
        "table": "job_metadata",
        "id_col": "entity_id",
        "date_filter_col": "last_updated",
        "string_fields": [
            "title", "workflow_state", "occupational_fields", "locations",
            "organization_profile_name", "organization_id", "employment_type",
            "external_id", "category", "contract_type", "employer_type",
            "currency_code", "salary_free_text", "salary_unit",
            "hq_region", "hq_county",
        ],
        "numeric_fields": [
            "min_salary", "max_salary", "salary_exact",
        ],
        "date_fields": [
            "publishing_date", "expiration_date", "last_updated",
        ],
        "context_cols": ["title", "organization_profile_name"],
    },
}


def get_client():
    """Initialize BigQuery client."""
    from google.oauth2.service_account import Credentials
    from google.cloud import bigquery

    sa_path = os.path.join(project_dir, 'service_account.json')
    if not os.path.exists(sa_path):
        print(f"ERROR: service_account.json not found at {sa_path}")
        sys.exit(1)

    creds = Credentials.from_service_account_file(sa_path, scopes=[
        'https://www.googleapis.com/auth/bigquery'
    ])
    return bigquery.Client(credentials=creds, project=BQ_PROJECT)


def all_fields(config):
    """Return all field names for a table config."""
    return config["string_fields"] + config["numeric_fields"] + config["date_fields"]


def build_completeness_query(config, since_date=None):
    """Build SQL that returns 1 row per vacancy with boolean empty flags.

    Only returns vacancies where at least one field is empty (HAVING clause).
    """
    table_ref = f"`{BQ_PROJECT}.{BQ_DATASET}.{config['table']}`"
    id_col = config["id_col"]
    agg_fn = "MIN" if config.get("use_min_agg") else "MAX"

    case_exprs = []
    empty_cols = []

    for field in config["string_fields"]:
        col_alias = f"{field}_empty"
        empty_cols.append(col_alias)
        case_exprs.append(
            f"  {agg_fn}(CASE WHEN {field} IS NULL "
            f"OR TRIM(CAST({field} AS STRING)) IN ('', '(none)', '(not set)') "
            f"THEN 1 ELSE 0 END) AS {col_alias}"
        )

    for field in config["numeric_fields"]:
        col_alias = f"{field}_empty"
        empty_cols.append(col_alias)
        case_exprs.append(
            f"  {agg_fn}(CASE WHEN {field} IS NULL "
            f"THEN 1 ELSE 0 END) AS {col_alias}"
        )

    for field in config["date_fields"]:
        col_alias = f"{field}_empty"
        empty_cols.append(col_alias)
        case_exprs.append(
            f"  {agg_fn}(CASE WHEN {field} IS NULL "
            f"THEN 1 ELSE 0 END) AS {col_alias}"
        )

    # Context columns (e.g. title, org name) for readability in output
    context_exprs = []
    for col in config.get("context_cols", []):
        context_exprs.append(f"  ANY_VALUE({col}) AS {col}")

    select_parts = [f"  {id_col}"] + context_exprs + case_exprs
    select_clause = ",\n".join(select_parts)

    where_clause = ""
    if since_date and config.get("date_filter_col"):
        where_clause = f"\nWHERE {config['date_filter_col']} >= '{since_date}'"

    having_clause = "\nHAVING " + " OR ".join(f"{c} = 1" for c in empty_cols)

    return (
        f"SELECT\n{select_clause}\n"
        f"FROM {table_ref}{where_clause}\n"
        f"GROUP BY {id_col}{having_clause}"
    )


def build_count_query(config, since_date=None):
    """Build SQL to count total distinct vacancies in a table."""
    table_ref = f"`{BQ_PROJECT}.{BQ_DATASET}.{config['table']}`"
    id_col = config["id_col"]
    where_clause = ""
    if since_date and config.get("date_filter_col"):
        where_clause = f" WHERE {config['date_filter_col']} >= '{since_date}'"
    return f"SELECT COUNT(DISTINCT {id_col}) AS total FROM {table_ref}{where_clause}"


def check_table(client, config, since_date=None):
    """Query a table and return (total_count, gaps_dataframe)."""
    count_sql = build_count_query(config, since_date)
    total = client.query(count_sql).to_dataframe(
        create_bqstorage_client=False
    )["total"].iloc[0]

    gaps_sql = build_completeness_query(config, since_date)
    gaps_df = client.query(gaps_sql).to_dataframe(create_bqstorage_client=False)

    return int(total), gaps_df


def compute_statistics(total_count, gaps_df, config):
    """Compute per-field completeness from the gaps DataFrame."""
    fields = all_fields(config)
    gaps_count = len(gaps_df)
    complete_count = total_count - gaps_count

    field_stats = []
    for field in fields:
        col = f"{field}_empty"
        if col in gaps_df.columns:
            empty_in_gaps = int(gaps_df[col].sum())
        else:
            empty_in_gaps = 0
        # Vacancies NOT in gaps_df have this field populated
        pct = ((total_count - empty_in_gaps) / total_count * 100) if total_count else 0
        field_stats.append({
            "field": field,
            "empty_count": empty_in_gaps,
            "total": total_count,
            "pct_complete": round(pct, 1),
        })

    field_stats.sort(key=lambda x: x["pct_complete"])

    return {
        "table": config["table"],
        "total": total_count,
        "with_gaps": gaps_count,
        "complete": complete_count,
        "pct_complete": round(complete_count / total_count * 100, 1) if total_count else 0,
        "field_stats": field_stats,
    }


def build_gaps_detail(gaps_df, config):
    """Add missing_fields and missing_count columns to the gaps DataFrame."""
    fields = all_fields(config)
    empty_cols = [f"{f}_empty" for f in fields]
    existing_empty_cols = [c for c in empty_cols if c in gaps_df.columns]

    def get_missing(row):
        return ", ".join(
            col.replace("_empty", "")
            for col in existing_empty_cols
            if row.get(col, 0) == 1
        )

    df = gaps_df.copy()
    df["missing_fields"] = df.apply(get_missing, axis=1)
    df["missing_count"] = df[existing_empty_cols].sum(axis=1).astype(int)

    # Keep only useful columns: ID, context cols, missing_fields, missing_count
    keep = [config["id_col"]]
    for col in config.get("context_cols", []):
        if col in df.columns:
            keep.append(col)
    keep += ["missing_fields", "missing_count"]
    df = df[keep].sort_values("missing_count", ascending=False)

    return df


def print_console_report(all_stats):
    """Print formatted console report."""
    print()
    print("=" * 64)
    print(f"  DATA COMPLETENESS REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 64)

    for stats in all_stats:
        print()
        print(f"  Table: {stats['table']}")
        print(f"    Total vacancies:     {stats['total']:>8,}")
        print(f"    With gaps:           {stats['with_gaps']:>8,}  ({100 - stats['pct_complete']:.1f}%)")
        print(f"    Fully complete:      {stats['complete']:>8,}  ({stats['pct_complete']:.1f}%)")
        print()
        print("    Per-field completeness (worst first):")
        for fs in stats["field_stats"]:
            bar = "#" * int(fs["pct_complete"] / 5) + "-" * (20 - int(fs["pct_complete"] / 5))
            print(
                f"      {fs['field']:<30s} {fs['pct_complete']:>6.1f}%  "
                f"|{bar}|  ({fs['empty_count']:,} empty)"
            )

    print()
    print("=" * 64)


def write_excel_report(all_stats, all_details, output_path):
    """Write multi-sheet Excel report."""
    try:
        import openpyxl  # noqa: F401 — check availability
    except ImportError:
        # Fall back to CSV
        csv_path = output_path.replace(".xlsx", ".csv")
        print(f"  openpyxl not installed — writing CSV fallback to {csv_path}")
        combined = pd.concat(all_details.values(), keys=all_details.keys(), names=["table"])
        combined.to_csv(csv_path)
        return csv_path

    # Summary sheet
    summary_rows = []
    for stats in all_stats:
        summary_rows.append({
            "Table": stats["table"],
            "Total Vacancies": stats["total"],
            "With Gaps": stats["with_gaps"],
            "Fully Complete": stats["complete"],
            "% Complete": stats["pct_complete"],
        })
    summary_df = pd.DataFrame(summary_rows)

    # Field completeness sheet
    field_rows = []
    for stats in all_stats:
        for fs in stats["field_stats"]:
            field_rows.append({
                "Table": stats["table"],
                "Field": fs["field"],
                "Empty Count": fs["empty_count"],
                "Total": fs["total"],
                "% Complete": fs["pct_complete"],
            })
    field_df = pd.DataFrame(field_rows).sort_values("% Complete")

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        field_df.to_excel(writer, sheet_name="Field Completeness", index=False)
        for sheet_name, detail_df in all_details.items():
            # Excel sheet names max 31 chars
            detail_df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Check data completeness across BigQuery dashboard tables."
    )
    parser.add_argument(
        "--since",
        help="Only check vacancies with activity since this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--table",
        choices=list(TABLE_CONFIGS.keys()),
        help="Check only a specific table instead of all three",
    )
    parser.add_argument(
        "--output",
        help="Output Excel file path (default: field_completeness_report_<date>.xlsx)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the SQL queries without executing them",
    )
    args = parser.parse_args()

    # Determine which tables to check
    if args.table:
        tables_to_check = {args.table: TABLE_CONFIGS[args.table]}
    else:
        tables_to_check = TABLE_CONFIGS

    since_date = args.since

    # Dry-run mode: print SQL and exit
    if args.dry_run:
        for name, config in tables_to_check.items():
            print(f"\n{'=' * 64}")
            print(f"-- {name}: count query")
            print(f"{'=' * 64}")
            print(build_count_query(config, since_date))
            print(f"\n{'=' * 64}")
            print(f"-- {name}: completeness query")
            print(f"{'=' * 64}")
            print(build_completeness_query(config, since_date))
        return

    # Live run
    start = datetime.now()
    client = get_client()

    all_stats = []
    all_details = {}

    for name, config in tables_to_check.items():
        print(f"\n  Checking {config['table']}...")
        total, gaps_df = check_table(client, config, since_date)
        stats = compute_statistics(total, gaps_df, config)
        detail = build_gaps_detail(gaps_df, config)
        all_stats.append(stats)
        all_details[name] = detail
        print(f"    {total:,} vacancies, {len(gaps_df):,} with gaps")

    # Console report
    print_console_report(all_stats)

    # Excel report
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = args.output or os.path.join(
        project_dir, f"field_completeness_report_{date_str}.xlsx"
    )
    result_path = write_excel_report(all_stats, all_details, output_path)
    print(f"  Report written to: {result_path}")

    elapsed = (datetime.now() - start).total_seconds()
    print(f"  Completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
