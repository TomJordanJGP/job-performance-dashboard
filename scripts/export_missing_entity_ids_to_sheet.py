#!/usr/bin/env python3
"""Detect vacancies missing an entity_id and write to Google Sheets.

Counterpart to export_missing_ids_to_sheet.py, keyed the other direction:

  export_missing_ids_to_sheet.py   — GA4 entity_id has no job_metadata row
                                     (user supplies external_id etc. from Jobiqo)

  THIS SCRIPT                      — feed row has external_id but no entity_id
                                     (user supplies entity_id + 2 Jobiqo-only
                                     fields)

Reads from `vacancies_missing_entity_id` (maintained each run by sync_feeds.py)
and overwrites the "Missing Entity IDs" tab on the shared review Sheet.

Sheet layout — 10 columns, minimal by design:
    A external_id              (context, XLOOKUP key)
    B title                    (context)
    C organization_profile_name (context)
    D locations                (context)
    E workflow_state           (context — tells user if vacancy is still live)
    F publishing_date          (context — freshness)
    G entity_id                *** user fills from Jobiqo ***
    H employer_type            *** user fills from Jobiqo (0% in feed data) ***
    I original_publishing_date *** user fills from Jobiqo (0% in feed data) ***
    J done                     (user sets TRUE when row is complete)

sync_entity_id_additions.sql MERGEs done=TRUE rows back into job_metadata
BEFORE this export runs, so filled rows are already synced. On the *next*
pipeline run, sync_feeds.py rebuilds vacancies_missing_entity_id and the row
drops off the Sheet naturally.

Run as part of daily_refresh.py (after create_reconciliation_tables.sql).

Requirements:
    - service_account.json in project root
    - gspread, google-cloud-bigquery, pandas

Usage:
    python scripts/export_missing_entity_ids_to_sheet.py
    python scripts/export_missing_entity_ids_to_sheet.py --dry-run
"""

import os
import sys
import argparse

import gspread
import pandas as pd
from google.oauth2 import service_account
from google.cloud import bigquery

# Same Google Sheet as the other review queues — different tab.
SHEET_ID = os.environ.get(
    'MISSING_IDS_SHEET_ID',
    '1YPfZMxK2Rdl91JjAKd60xtjNinDfBe0DHpa5euFwmDc',
)
SHEET_NAME = 'Missing Entity IDs'

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
SA_PATH = os.path.join(project_dir, 'service_account.json')

# 10-column header. Columns A–F are context (feed-sourced, read-only); G–I are
# Jobiqo-only fills; J is the done marker.
HEADER_ROW = [
    'external_id', 'title', 'organization_profile_name', 'locations',
    'workflow_state', 'publishing_date',
    'entity_id', 'employer_type', 'original_publishing_date',
    'done',
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
    """Query the pre-maintained vacancies_missing_entity_id table.

    Built each run by sync_feeds.py (lines 305-335). Contains exactly the
    columns we want as context.
    """
    sql = """
    SELECT
      external_id,
      title,
      organization_profile_name,
      locations,
      workflow_state,
      publishing_date
    FROM `site-monitoring-421401.job_data_export.vacancies_missing_entity_id`
    ORDER BY publishing_date DESC NULLS LAST
    """
    return bq_client.query(sql).to_dataframe()


def get_or_create_worksheet(gc):
    """Get the Missing Entity IDs worksheet, creating it if it doesn't exist."""
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
    """Clear and rewrite the Missing Entity IDs tab."""
    worksheet = get_or_create_worksheet(gc)

    rows = [HEADER_ROW]
    for _, row in data_df.iterrows():
        rows.append([
            str(row['external_id']) if pd.notna(row['external_id']) else '',
            row['title'] if pd.notna(row['title']) else '',
            row['organization_profile_name'] if pd.notna(row['organization_profile_name']) else '',
            row['locations'] if pd.notna(row['locations']) else '',
            row['workflow_state'] if pd.notna(row['workflow_state']) else '',
            str(row['publishing_date']) if pd.notna(row['publishing_date']) else '',
            # 4 blank user-fill columns: entity_id, employer_type,
            # original_publishing_date, done
            '', '', '', '',
        ])

    worksheet.clear()
    worksheet.update(range_name='A1', values=rows, value_input_option='USER_ENTERED')

    return len(rows) - 1  # exclude header


def main():
    parser = argparse.ArgumentParser(
        description='Detect and export vacancies missing entity_id to Google Sheets',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be written without modifying the Sheet',
    )
    args = parser.parse_args()

    if not os.path.exists(SA_PATH):
        print(f"ERROR: service_account.json not found at {SA_PATH}")
        sys.exit(1)

    print("Querying vacancies_missing_entity_id table...")
    bq_client = get_bq_client()
    missing = get_missing_from_bq(bq_client)
    print(f"  Found {len(missing)} vacancies with external_id but no entity_id")

    gc = get_sheets_client()

    if missing.empty:
        print("  No missing entity IDs found. Clearing Sheet to header-only.")
        if not args.dry_run:
            worksheet = get_or_create_worksheet(gc)
            worksheet.clear()
            worksheet.update(range_name='A1', values=[HEADER_ROW],
                             value_input_option='USER_ENTERED')
            print("  Sheet cleared.")
        return

    if args.dry_run:
        print(f"\n  [DRY RUN] Would write {len(missing)} rows:")
        display_cols = ['external_id', 'organization_profile_name', 'publishing_date']
        print(missing[display_cols].head(20).to_string())
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
        return

    print("Writing to Missing Entity IDs Sheet (overwrite)...")
    count = overwrite_sheet(gc, missing)
    print(f"  Wrote {count} rows")


if __name__ == '__main__':
    main()
