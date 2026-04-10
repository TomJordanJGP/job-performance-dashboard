#!/usr/bin/env python3
"""Detect vacancies missing from job_metadata and write to Google Sheets.

Queries the missing_external_ids reconciliation table (pre-computed by
create_reconciliation_tables.sql) for GA4 vacancies with no matching
job_metadata row. Overwrites the "Missing IDs" tab each run so the Sheet
always reflects the current outstanding items.

The user then XLOOKUPs from a Jobiqo export to fill in metadata fields
(external_id, salary, occupation, etc.) and marks done=TRUE. The pipeline
MERGEs approved rows into job_metadata via sync_external_id_additions.sql
BEFORE this export runs, so done=TRUE rows are already synced.

Run as part of daily_refresh.py (after create_reconciliation_tables.sql).

Requirements:
    - service_account.json in project root
    - gspread, google-cloud-bigquery, pandas

Usage:
    python scripts/export_missing_ids_to_sheet.py
    python scripts/export_missing_ids_to_sheet.py --dry-run
"""

import os
import sys
import argparse

import gspread
import pandas as pd
from google.oauth2 import service_account
from google.cloud import bigquery

# Same Google Sheet as the location review queue — different tab.
SHEET_ID = os.environ.get(
    'MISSING_IDS_SHEET_ID',
    '1YPfZMxK2Rdl91JjAKd60xtjNinDfBe0DHpa5euFwmDc',
)
SHEET_NAME = 'Missing IDs'

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
SA_PATH = os.path.join(project_dir, 'service_account.json')

# 21-column header matching the Sheet tab.
HEADER_ROW = [
    'entity_id', 'title', 'organization_name', 'importer_name',
    'first_seen_date', 'event_count',
    'external_id', 'organization_id', 'locations', 'employment_type',
    'occupational_fields', 'employer_type', 'workflow_state',
    'publishing_date', 'expiration_date',
    'min_salary', 'max_salary', 'currency_code', 'salary_unit',
    'salary_free_text', 'done',
]


def get_bq_client():
    """Initialize BigQuery client."""
    creds = service_account.Credentials.from_service_account_file(
        SA_PATH,
        scopes=['https://www.googleapis.com/auth/bigquery'],
    )
    return bigquery.Client(credentials=creds, project='site-monitoring-421401')


def get_sheets_client():
    """Initialize Google Sheets client."""
    creds = service_account.Credentials.from_service_account_file(
        SA_PATH,
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
        ],
    )
    return gspread.authorize(creds)


def get_missing_from_bq(bq_client):
    """Query the pre-computed missing_external_ids reconciliation table."""
    sql = """
    SELECT
      entity_id_str AS entity_id,
      title,
      organization_name,
      importer_name,
      first_seen_date,
      event_count
    FROM `site-monitoring-421401.job_data_export.missing_external_ids`
    ORDER BY event_count DESC
    """
    return bq_client.query(sql).to_dataframe()


def get_or_create_worksheet(gc):
    """Get the Missing IDs worksheet, creating it if it doesn't exist."""
    spreadsheet = gc.open_by_key(SHEET_ID)
    try:
        return spreadsheet.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        print(f"  Creating '{SHEET_NAME}' tab...")
        worksheet = spreadsheet.add_worksheet(
            title=SHEET_NAME, rows=1, cols=len(HEADER_ROW),
        )
        print(f"  Created with {len(HEADER_ROW)} columns.")
        print(f"  Tab gid: {worksheet.id}")
        return worksheet


def overwrite_sheet(gc, data_df):
    """Clear and rewrite the Missing IDs tab with current outstanding items."""
    worksheet = get_or_create_worksheet(gc)

    rows = [HEADER_ROW]
    for _, row in data_df.iterrows():
        rows.append([
            str(row['entity_id']),
            row['title'] if pd.notna(row['title']) else '',
            row['organization_name'] if pd.notna(row['organization_name']) else '',
            row['importer_name'] if pd.notna(row['importer_name']) else '',
            str(row['first_seen_date']) if pd.notna(row['first_seen_date']) else '',
            int(row['event_count']),
            # 15 blank user-fill columns: external_id through salary_free_text + done
            '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
        ])

    worksheet.clear()
    worksheet.update(range_name='A1', values=rows, value_input_option='USER_ENTERED')

    return len(rows) - 1  # exclude header


def main():
    parser = argparse.ArgumentParser(
        description='Detect and export missing vacancy metadata to Google Sheets',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be written without modifying the Sheet',
    )
    args = parser.parse_args()

    if not os.path.exists(SA_PATH):
        print(f"ERROR: service_account.json not found at {SA_PATH}")
        sys.exit(1)

    print("Querying missing_external_ids table...")
    bq_client = get_bq_client()
    missing = get_missing_from_bq(bq_client)
    print(f"  Found {len(missing)} vacancies with no job_metadata row")

    gc = get_sheets_client()

    if missing.empty:
        print("  No missing vacancies found. Clearing Sheet to header-only.")
        if not args.dry_run:
            worksheet = get_or_create_worksheet(gc)
            worksheet.clear()
            worksheet.update(range_name='A1', values=[HEADER_ROW],
                             value_input_option='USER_ENTERED')
            print("  Sheet cleared.")
        return

    if args.dry_run:
        print(f"\n  [DRY RUN] Would write {len(missing)} rows:")
        display_cols = ['entity_id', 'organization_name', 'event_count']
        print(missing[display_cols].head(20).to_string())
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
        return

    print("Writing to Missing IDs Sheet (overwrite)...")
    count = overwrite_sheet(gc, missing)
    print(f"  Wrote {count} rows")
    print(f"  Total GA4 events covered: {missing['event_count'].sum():,}")


if __name__ == '__main__':
    main()
