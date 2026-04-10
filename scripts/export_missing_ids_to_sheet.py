#!/usr/bin/env python3
"""Detect vacancies missing from job_metadata and append to Google Sheets.

Queries the missing_external_ids reconciliation table (pre-computed by
create_reconciliation_tables.sql) for GA4 vacancies with no matching
job_metadata row. Compares against the existing "Missing IDs" review Sheet
and appends only NEW entity_ids (append-only — never overwrites existing rows).

The user then XLOOKUPs from a Jobiqo export to fill in metadata fields
(external_id, salary, occupation, etc.) and marks done=TRUE. The pipeline
MERGEs approved rows into job_metadata via sync_external_id_additions.sql.

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


def get_existing_ids_from_sheet(gc):
    """Read existing entity_id values from the Missing IDs Sheet tab."""
    try:
        spreadsheet = gc.open_by_key(SHEET_ID)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        records = worksheet.get_all_records()
        if not records:
            return set()
        df = pd.DataFrame(records)
        return set(df['entity_id'].astype(str).str.strip())
    except gspread.exceptions.WorksheetNotFound:
        return None  # signals that tab needs to be created
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"  ERROR: Sheet {SHEET_ID} not found.")
        sys.exit(1)


def create_tab_if_needed(gc):
    """Create the Missing IDs tab with headers if it doesn't exist."""
    spreadsheet = gc.open_by_key(SHEET_ID)
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        print(f"  Creating '{SHEET_NAME}' tab...")
        worksheet = spreadsheet.add_worksheet(
            title=SHEET_NAME, rows=1, cols=len(HEADER_ROW),
        )
        worksheet.append_row(HEADER_ROW, value_input_option='USER_ENTERED')
        print(f"  Created with {len(HEADER_ROW)} columns.")
        # Print the gid so it can be used in sync_external_id_additions.sql.
        print(f"  Tab gid: {worksheet.id}")
        return worksheet


def append_to_sheet(gc, new_rows_df):
    """Append new missing-ID rows to the Sheet."""
    spreadsheet = gc.open_by_key(SHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_NAME)

    rows_to_append = []
    for _, row in new_rows_df.iterrows():
        rows_to_append.append([
            str(row['entity_id']),
            row['title'] if pd.notna(row['title']) else '',
            row['organization_name'] if pd.notna(row['organization_name']) else '',
            row['importer_name'] if pd.notna(row['importer_name']) else '',
            str(row['first_seen_date']) if pd.notna(row['first_seen_date']) else '',
            int(row['event_count']),
            # 15 blank user-fill columns: external_id through salary_free_text + done
            '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
        ])

    if rows_to_append:
        worksheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')

    return len(rows_to_append)


def main():
    parser = argparse.ArgumentParser(
        description='Detect and export missing vacancy metadata to Google Sheets',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be appended without writing',
    )
    args = parser.parse_args()

    if not os.path.exists(SA_PATH):
        print(f"ERROR: service_account.json not found at {SA_PATH}")
        sys.exit(1)

    print("Querying missing_external_ids table...")
    bq_client = get_bq_client()
    missing = get_missing_from_bq(bq_client)
    print(f"  Found {len(missing)} vacancies with no job_metadata row")

    if missing.empty:
        print("  No missing vacancies found. Nothing to do.")
        return

    print("Reading existing Missing IDs Sheet...")
    gc = get_sheets_client()
    existing_ids = get_existing_ids_from_sheet(gc)

    if existing_ids is None:
        # Tab doesn't exist yet — create it.
        create_tab_if_needed(gc)
        existing_ids = set()
        print(f"  0 entity_ids already in Sheet (new tab)")
    else:
        print(f"  {len(existing_ids)} entity_ids already in Sheet")

    # Filter to only new entity_ids not already in the Sheet.
    new_mask = ~missing['entity_id'].astype(str).str.strip().isin(existing_ids)
    new_rows = missing[new_mask]
    print(f"  {len(new_rows)} NEW missing vacancies to append")

    if new_rows.empty:
        print("  All missing vacancies already in Sheet. Nothing to append.")
        return

    if args.dry_run:
        print("\n  [DRY RUN] Would append:")
        display_cols = ['entity_id', 'organization_name', 'event_count']
        print(new_rows[display_cols].head(20).to_string())
        if len(new_rows) > 20:
            print(f"  ... and {len(new_rows) - 20} more")
        return

    print("Appending to Missing IDs Sheet...")
    count = append_to_sheet(gc, new_rows)
    print(f"  Appended {count} new rows")
    print(f"  Total GA4 events covered: {new_rows['event_count'].sum():,}")


if __name__ == '__main__':
    main()
