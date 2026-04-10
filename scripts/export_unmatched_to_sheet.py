#!/usr/bin/env python3
"""Detect unmatched towns in vacancy_locations and append new ones to Google Sheets.

Queries BigQuery for vacancy_locations rows where uk_region is NULL (town not in
location_lookup). Compares against the existing review Sheet and appends only NEW
unmatched towns (append-only — never overwrites existing rows).

Run as part of daily_refresh.py (after refresh_vacancy_locations.sql).

Requirements:
    - service_account.json in project root
    - gspread, google-cloud-bigquery, pandas

Usage:
    python scripts/export_unmatched_to_sheet.py
    python scripts/export_unmatched_to_sheet.py --dry-run
"""

import os
import sys
import argparse

import gspread
import pandas as pd
from google.oauth2 import service_account
from google.cloud import bigquery

# Google Sheet ID for the location review queue.
# Replace with the actual Sheet ID after creating it from location_review.xlsx.
SHEET_ID = os.environ.get('LOCATION_REVIEW_SHEET_ID', '1YPfZMxK2Rdl91JjAKd60xtjNinDfBe0DHpa5euFwmDc')
SHEET_NAME = 'Review'

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
SA_PATH = os.path.join(project_dir, 'service_account.json')

# Add parent directory for imports
sys.path.insert(0, project_dir)


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


def get_unmatched_from_bq(bq_client):
    """Query BigQuery for unmatched towns (NULL uk_region in vacancy_locations)."""
    sql = """
    SELECT
      vl.town_city,
      vl.country_region,
      'GB' as country_code,
      COUNT(*) as vacancy_count
    FROM `site-monitoring-421401.job_data_export.vacancy_locations` vl
    WHERE (vl.uk_region IS NULL OR TRIM(vl.uk_region) = '')
      AND vl.town_city IS NOT NULL
      AND TRIM(vl.town_city) != ''
    GROUP BY vl.town_city, vl.country_region
    ORDER BY vacancy_count DESC
    """
    return bq_client.query(sql).to_dataframe()


def get_existing_towns_from_sheet(gc):
    """Read existing town_city values from the review Sheet."""
    try:
        spreadsheet = gc.open_by_key(SHEET_ID)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        records = worksheet.get_all_records()
        if not records:
            return set()
        df = pd.DataFrame(records)
        return set(df['town_city'].str.strip().str.upper())
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"  WARNING: Sheet {SHEET_ID} not found. Will create if --create-sheet is passed.")
        return set()
    except gspread.exceptions.WorksheetNotFound:
        print(f"  WARNING: Worksheet '{SHEET_NAME}' not found in sheet.")
        return set()


def auto_suggest_region(town, country_region):
    """Quick auto-suggestion for new unmatched towns using region_parser logic."""
    from scripts.generate_location_review import (
        suggest_region, load_county_mapping,
    )
    county_to_region = load_county_mapping(project_dir)
    row = {
        'town_city': town,
        'country_region': country_region,
        'country_code': 'GB',
    }
    region, county, confidence, source = suggest_region(
        pd.Series(row), county_to_region, {}
    )
    return region, confidence, source


def append_to_sheet(gc, new_rows_df):
    """Append new unmatched towns to the review Sheet."""
    spreadsheet = gc.open_by_key(SHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_NAME)

    rows_to_append = []
    for _, row in new_rows_df.iterrows():
        region, confidence, source = auto_suggest_region(
            row['town_city'], row['country_region']
        )
        rows_to_append.append([
            row['town_city'],
            row['country_region'] if pd.notna(row['country_region']) else '',
            row['country_code'],
            int(row['vacancy_count']),
            region if region else '',
            '',  # suggested_county
            confidence,
            source,
            '',  # done
        ])

    if rows_to_append:
        worksheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')

    return len(rows_to_append)


def main():
    parser = argparse.ArgumentParser(
        description='Detect and export unmatched towns to Google Sheets'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be appended without writing')
    args = parser.parse_args()

    if not os.path.exists(SA_PATH):
        print(f"ERROR: service_account.json not found at {SA_PATH}")
        sys.exit(1)

    if SHEET_ID == 'REPLACE_WITH_SHEET_ID':
        print("ERROR: Set LOCATION_REVIEW_SHEET_ID env var or update SHEET_ID in script")
        sys.exit(1)

    print("Detecting unmatched towns...")
    bq_client = get_bq_client()
    unmatched = get_unmatched_from_bq(bq_client)
    print(f"  Found {len(unmatched)} unmatched town entries in vacancy_locations")

    if unmatched.empty:
        print("  No unmatched towns found. Nothing to do.")
        return

    print("Reading existing review Sheet...")
    gc = get_sheets_client()
    existing_towns = get_existing_towns_from_sheet(gc)
    print(f"  {len(existing_towns)} towns already in review Sheet")

    # Filter to only new towns (not already in the Sheet)
    new_mask = ~unmatched['town_city'].str.strip().str.upper().isin(existing_towns)
    new_towns = unmatched[new_mask]
    print(f"  {len(new_towns)} NEW unmatched towns to append")

    if new_towns.empty:
        print("  All unmatched towns already in review Sheet. Nothing to append.")
        return

    if args.dry_run:
        print("\n  [DRY RUN] Would append:")
        print(new_towns[['town_city', 'country_region', 'vacancy_count']].head(20).to_string())
        if len(new_towns) > 20:
            print(f"  ... and {len(new_towns) - 20} more")
        return

    print("Appending to review Sheet...")
    count = append_to_sheet(gc, new_towns)
    print(f"  Appended {count} new rows to review Sheet")
    print(f"  Total vacancies covered: {new_towns['vacancy_count'].sum()}")


if __name__ == '__main__':
    main()
