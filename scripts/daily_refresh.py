#!/usr/bin/env python3
"""Daily refresh script for the Job Performance Dashboard.

Runs four steps in sequence:
1. Incremental sync: Append new events from the source table
2. Sync feeds: Update job_metadata from XML feeds
3. Rebuild enriched table: Re-join with metadata and location lookup
4. Rebuild aggregated tables: Pre-compute vacancy summary and daily totals

Can be run manually, via cron, or as a GitHub Action.

Usage:
    python scripts/daily_refresh.py
    python scripts/daily_refresh.py --dry-run    # Preview without executing
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime

# Add parent directory to path so we can find service_account.json
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)

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
    return bigquery.Client(credentials=creds, project='site-monitoring-421401')


def run_sql_file(client, filename, description, dry_run=False):
    """Run a SQL file against BigQuery."""
    sql_path = os.path.join(script_dir, filename)
    if not os.path.exists(sql_path):
        print(f"  ERROR: {sql_path} not found")
        return False

    with open(sql_path) as f:
        sql = f.read()

    # Remove comment-only lines and split into statements
    lines = [line for line in sql.split('\n') if not line.strip().startswith('--')]
    clean_sql = '\n'.join(lines)
    statements = [s.strip() for s in clean_sql.split(';') if s.strip()]

    print(f"\n{'='*60}")
    print(f"Step: {description}")
    print(f"File: {filename}")
    print(f"Statements: {len(statements)}")

    if dry_run:
        print("  [DRY RUN] Would execute:")
        for i, stmt in enumerate(statements):
            preview = stmt[:100].replace('\n', ' ')
            print(f"    {i+1}. {preview}...")
        return True

    for i, stmt in enumerate(statements):
        try:
            print(f"  Running statement {i+1}/{len(statements)}...", end=' ', flush=True)
            job = client.query(stmt)
            job.result()
            if job.num_dml_affected_rows is not None:
                print(f"OK ({job.num_dml_affected_rows:,} rows affected)")
            else:
                print("OK")
        except Exception as e:
            print(f"FAILED: {e}")
            return False

    return True


def verify_tables(client):
    """Print current state of all tables."""
    print(f"\n{'='*60}")
    print("Verification:")

    tables = [
        ('job_performance_details_combined', 'MAX(event_date)'),
        ('job_metadata', 'MAX(last_updated)'),
        ('vacancy_locations', 'COUNT(DISTINCT entity_id)'),
        ('feed_jobs_latest', 'MAX(last_seen)'),
        ('job_performance_enriched', 'MAX(event_date_parsed)'),
        ('dashboard_vacancy_summary', 'MAX(last_event_date)'),
        ('dashboard_daily_totals', 'MAX(event_date)'),
    ]

    for table, max_date_expr in tables:
        try:
            q = f"SELECT COUNT(*) as cnt, {max_date_expr} as max_d FROM `site-monitoring-421401.job_data_export.{table}`"
            r = client.query(q).to_dataframe()
            print(f"  {table}: {r.iloc[0]['cnt']:,} rows, latest: {r.iloc[0]['max_d']}")
        except Exception as e:
            print(f"  {table}: ERROR - {e}")


def main():
    parser = argparse.ArgumentParser(description='Daily refresh for Job Performance Dashboard')
    parser.add_argument('--dry-run', action='store_true', help='Preview without executing')
    args = parser.parse_args()

    start_time = datetime.now()
    print(f"Job Performance Dashboard - Daily Refresh")
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    client = get_client()

    # Step 1: Incremental sync
    ok = run_sql_file(client, 'incremental_sync_combined.sql',
                      'Sync new events from source table', args.dry_run)
    if not ok:
        print("FAILED at step 1. Aborting.")
        sys.exit(1)

    # Step 2: Sync feeds to update job_metadata
    print(f"\n{'='*60}")
    print("Step: Sync job feeds (update job_metadata)")
    sync_feeds_path = os.path.join(script_dir, 'sync_feeds.py')
    if args.dry_run:
        print("  [DRY RUN] Would run sync_feeds.py")
    else:
        result = subprocess.run(
            [sys.executable, sync_feeds_path],
            capture_output=True, text=True
        )
        # Always print full output for visibility (especially in GitHub Actions logs)
        if result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                print(f"  {line}")
        if result.returncode != 0:
            print(f"  WARNING: Feed sync failed (exit code {result.returncode}):")
            if result.stderr.strip():
                for line in result.stderr.strip().split('\n'):
                    print(f"  STDERR: {line}")
            print("  Continuing with existing feed data...")

    # Step 3: Rebuild enriched table
    ok = run_sql_file(client, 'refresh_enriched_table.sql',
                      'Rebuild enriched table with metadata + locations', args.dry_run)
    if not ok:
        print("FAILED at step 3. Aborting.")
        sys.exit(1)

    # Step 4: Rebuild aggregated tables
    ok = run_sql_file(client, 'create_aggregated_tables.sql',
                      'Rebuild dashboard summary tables', args.dry_run)
    if not ok:
        print("FAILED at step 4. Aborting.")
        sys.exit(1)

    # Verify
    if not args.dry_run:
        verify_tables(client)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"Completed in {elapsed:.0f}s")


if __name__ == '__main__':
    main()
