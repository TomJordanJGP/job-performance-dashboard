#!/usr/bin/env python3
"""Sync job feeds into BigQuery job_metadata table.

Fetches XML feeds, upserts jobs into job_metadata, marks removed jobs
as unpublished, and records daily live job counts for historical tracking.

Field mapping (from field_mapping.csv):
  - external_id      ← feed id (hash)
  - title             ← feed title
  - workflow_state    ← 'published' (if in feed)
  - organization_id   ← feed organization_id (Scrape/ATS) or jobiqo_id (Civil Service)
  - organization_profile_name ← feed organization_name (Scrape/ATS only)
  - locations         ← feed job_location (Scrape/ATS) or location (Civil Service)
  - employment_type   ← feed working_pattern
  - occupational_fields ← feed category
  - category          ← feed occupation
  - contract_type     ← feed contract_type
  - publishing_date   ← feed start_date
  - expiration_date   ← feed close_date
  - salary_free_text  ← feed salary_free_text
  - min_salary        ← feed salary/salary_min
  - max_salary        ← feed salary/salary_max
  - salary_exact      ← feed salary/salary_exact
  - currency_code     ← feed salary/salary_currency
  - salary_unit       ← feed salary/salary_type

Usage:
    python scripts/sync_feeds.py
    python scripts/sync_feeds.py --dry-run
"""

import os
import sys
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime
from dateutil import parser as dateparser

import pandas as pd
import requests

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)

BQ_PROJECT = "site-monitoring-421401"
BQ_DATASET = "job_data_export"

FEEDS = {
    "Scrape": "https://storage.googleapis.com/scrpr-job-data-export/jgp_scrapes/jgp_scraping_feed.xml",
    "Civil Service": "https://storage.googleapis.com/scrpr-job-data-export/jgp_scrapes/civil_service_jobs_uk.xml",
    "ATS": "https://storage.googleapis.com/scrpr-job-data-export/jgp_scrapes/jgp_ats_feed.xml",
}


def get_client():
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


def parse_date(date_str):
    """Parse various date formats from feeds."""
    if not date_str or not date_str.strip():
        return None
    try:
        return dateparser.parse(date_str)
    except Exception:
        return None


def get_text(element, tag, default=''):
    """Safely get text from an XML child element."""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def get_nested_text(element, parent_tag, child_tag, default=''):
    """Safely get text from a nested XML element like salary/salary_min."""
    parent = element.find(parent_tag)
    if parent is not None:
        child = parent.find(child_tag)
        if child is not None and child.text:
            return child.text.strip()
    return default


def parse_float(value):
    """Parse a string to float, returning None on failure."""
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_location(job_el, feed_name):
    """Extract location string from job element."""
    if feed_name == "Civil Service":
        # Civil Service uses <location>
        return get_text(job_el, 'location')
    else:
        # Scrape and ATS use <job_location>
        return get_text(job_el, 'job_location')


def fetch_feed(feed_name, url):
    """Fetch and parse a single XML feed."""
    print(f"  Fetching {feed_name}...", end=' ', flush=True)
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        jobs = root.findall('.//job')
        print(f"{len(jobs)} jobs")
        return jobs
    except Exception as e:
        print(f"FAILED: {e}")
        return []


def parse_feed_jobs(feed_name, job_elements):
    """Parse job elements into metadata records using field_mapping.csv."""
    records = []
    now = datetime.now(tz=None)

    for job_el in job_elements:
        # Core IDs
        feed_id = get_text(job_el, 'id')  # → external_id
        title = get_text(job_el, 'title')

        # Organization - Civil Service uses jobiqo_id for org_id, others use organization_id
        if feed_name == "Civil Service":
            org_id = get_text(job_el, 'jobiqo_id', '')
            org_name = ''  # Civil Service doesn't provide org name
        else:
            org_id = get_text(job_el, 'organization_id', '')
            org_name = get_text(job_el, 'organization_name', '')

        # Location
        location = parse_location(job_el, feed_name)

        # Classification fields
        employment_type = get_text(job_el, 'working_pattern', '')  # → employment_type
        occupational_fields = get_text(job_el, 'category', '')     # → occupational_fields
        category = get_text(job_el, 'occupation', '')               # → category
        contract_type = get_text(job_el, 'contract_type', '')       # → contract_type

        # Dates
        start_date = parse_date(get_text(job_el, 'start_date'))
        close_date = parse_date(get_text(job_el, 'close_date'))

        # Salary fields
        salary_free_text = get_text(job_el, 'salary_free_text', '')
        min_salary = parse_float(get_nested_text(job_el, 'salary', 'salary_min'))
        max_salary = parse_float(get_nested_text(job_el, 'salary', 'salary_max'))
        salary_exact = parse_float(get_nested_text(job_el, 'salary', 'salary_exact'))
        currency_code = get_nested_text(job_el, 'salary', 'salary_currency')
        salary_unit = get_nested_text(job_el, 'salary', 'salary_type')

        records.append({
            'feed_id': feed_id,
            'feed_name': feed_name,
            'title': title,
            'workflow_state': 'published',  # If in feed, it's live
            'organization_id': org_id,
            'organization_profile_name': org_name,
            'locations': location,
            'employment_type': employment_type,
            'occupational_fields': occupational_fields,
            'category': category,
            'contract_type': contract_type,
            'publishing_date': start_date,
            'expiration_date': close_date,
            'salary_free_text': salary_free_text,
            'min_salary': min_salary,
            'max_salary': max_salary,
            'salary_exact': salary_exact,
            'currency_code': currency_code,
            'salary_unit': salary_unit,
            'last_updated': now,
        })

    return records


def sync_to_bigquery(client, all_records, dry_run=False):
    """Sync feed records to job_metadata table.

    Strategy:
    - Match by external_id (feed hash = metadata external_id, N_ prefix already stripped)
    - Update matched rows: set published + update feed-sourced fields
    - Do NOT insert unmatched rows (only CSV export creates new metadata rows)
    - Mark jobs no longer in any feed as unpublished
    """
    from google.cloud import bigquery

    if not all_records:
        print("  No records to sync")
        return

    feed_df = pd.DataFrame(all_records)
    print(f"\n  Total feed jobs: {len(feed_df):,}")
    for feed in feed_df['feed_name'].unique():
        count = len(feed_df[feed_df['feed_name'] == feed])
        print(f"    {feed}: {count:,}")

    if dry_run:
        print("  [DRY RUN] Would sync to BigQuery")
        return feed_df

    # Write to staging table (feed_jobs_latest) - full replace each run
    table_ref = f"{BQ_PROJECT}.{BQ_DATASET}.feed_jobs_latest"

    # Prepare for BigQuery upload
    upload_df = feed_df.copy()
    upload_df['publishing_date'] = pd.to_datetime(upload_df['publishing_date'], utc=True, errors='coerce')
    upload_df['expiration_date'] = pd.to_datetime(upload_df['expiration_date'], utc=True, errors='coerce')
    upload_df['last_updated'] = pd.to_datetime(upload_df['last_updated'], utc=True)

    job_config = bigquery.LoadJobConfig(write_disposition='WRITE_TRUNCATE')
    job = client.load_table_from_dataframe(upload_df, table_ref, job_config=job_config)
    job.result()
    print(f"  Wrote {len(upload_df):,} rows to feed_jobs_latest")

    # MERGE: Match feed jobs to metadata by external_id
    # - MATCHED: update to published + refresh feed fields
    # - NOT MATCHED: insert as new row (new job not in CSV export)
    update_sql = f"""
    MERGE `{BQ_PROJECT}.{BQ_DATASET}.job_metadata` AS target
    USING (
        SELECT
            feed_id,
            feed_name,
            title,
            organization_id,
            organization_profile_name,
            locations,
            employment_type,
            occupational_fields,
            category,
            contract_type,
            publishing_date,
            expiration_date,
            salary_free_text,
            min_salary,
            max_salary,
            salary_exact,
            currency_code,
            salary_unit,
            last_updated
        FROM `{BQ_PROJECT}.{BQ_DATASET}.feed_jobs_latest`
    ) AS source
    ON target.external_id = source.feed_id
    WHEN MATCHED THEN UPDATE SET
        target.workflow_state = 'published',
        target.title = source.title,
        target.locations = source.locations,
        target.employment_type = source.employment_type,
        target.occupational_fields = source.occupational_fields,
        target.category = source.category,
        target.contract_type = source.contract_type,
        target.expiration_date = source.expiration_date,
        target.salary_free_text = source.salary_free_text,
        target.min_salary = source.min_salary,
        target.max_salary = source.max_salary,
        target.salary_exact = source.salary_exact,
        target.currency_code = source.currency_code,
        target.salary_unit = source.salary_unit,
        target.last_updated = source.last_updated
    WHEN NOT MATCHED THEN INSERT (
        external_id, title, workflow_state, organization_id,
        organization_profile_name, locations, employment_type,
        occupational_fields, category, contract_type,
        publishing_date, expiration_date,
        salary_free_text, min_salary, max_salary, salary_exact,
        currency_code, salary_unit, last_updated
    ) VALUES (
        source.feed_id, source.title, 'published', source.organization_id,
        source.organization_profile_name, source.locations, source.employment_type,
        source.occupational_fields, source.category, source.contract_type,
        source.publishing_date, source.expiration_date,
        source.salary_free_text, source.min_salary, source.max_salary, source.salary_exact,
        source.currency_code, source.salary_unit, source.last_updated
    )
    """

    print("  Running MERGE into job_metadata...", end=' ', flush=True)
    job = client.query(update_sql)
    job.result()
    print(f"OK ({job.num_dml_affected_rows} rows affected)")

    # Report jobs inserted from feeds that have no entity_id (need Jobiqo export to get one)
    missing_entity_sql = f"""
    SELECT external_id, title, organization_profile_name, locations, workflow_state,
           publishing_date, last_updated
    FROM `{BQ_PROJECT}.{BQ_DATASET}.job_metadata`
    WHERE (entity_id IS NULL OR entity_id = '')
      AND external_id IS NOT NULL AND external_id != ''
    ORDER BY last_updated DESC
    """
    missing_df = client.query(missing_entity_sql).to_dataframe()

    if len(missing_df) > 0:
        print(f"\n  ⚠️  {len(missing_df):,} vacancies without entity_id (need Jobiqo export):")
        for _, row in missing_df.head(20).iterrows():
            ext_id = str(row['external_id'])[:20]
            title = str(row.get('title', ''))[:50]
            org = str(row.get('organization_profile_name', ''))[:30]
            print(f"    {ext_id:20s}  {title:50s}  {org}")
        if len(missing_df) > 20:
            print(f"    ... and {len(missing_df) - 20} more")
    else:
        print(f"\n  ✅ All vacancies have an entity_id")

    # Always write to BigQuery table (even if empty) so it's always queryable
    try:
        missing_table = f"{BQ_PROJECT}.{BQ_DATASET}.vacancies_missing_entity_id"
        job_config = bigquery.LoadJobConfig(write_disposition='WRITE_TRUNCATE')
        job = client.load_table_from_dataframe(missing_df, missing_table, job_config=job_config)
        job.result()
        print(f"  Written to BigQuery: vacancies_missing_entity_id ({len(missing_df)} rows)")
    except Exception as e:
        print(f"  WARNING: Failed to write vacancies_missing_entity_id table: {e}")

    # Also save locally if running locally
    if len(missing_df) > 0:
        try:
            output_path = os.path.join(project_dir, 'vacancies_missing_entity_id.csv')
            missing_df.to_csv(output_path, index=False)
            print(f"  Saved locally: vacancies_missing_entity_id.csv")
        except Exception:
            pass  # May fail in CI environment, that's fine

    # Mark jobs no longer in any feed as unpublished
    unpublish_sql = f"""
    UPDATE `{BQ_PROJECT}.{BQ_DATASET}.job_metadata`
    SET workflow_state = 'unpublished',
        last_updated = CURRENT_TIMESTAMP()
    WHERE workflow_state = 'published'
      AND external_id IS NOT NULL
      AND external_id != ''
      AND external_id NOT IN (
          SELECT feed_id FROM `{BQ_PROJECT}.{BQ_DATASET}.feed_jobs_latest`
      )
    """

    print("  Marking removed jobs as unpublished...", end=' ', flush=True)
    job = client.query(unpublish_sql)
    job.result()
    print(f"OK ({job.num_dml_affected_rows} rows affected)")

    return feed_df


def record_daily_live_count(client, feed_df, dry_run=False):
    """Record today's live job count for historical tracking."""
    from google.cloud import bigquery

    today = datetime.now(tz=None).strftime('%Y-%m-%d')
    total_live = len(feed_df) if feed_df is not None else 0

    # Per-feed counts
    feed_counts = {}
    if feed_df is not None:
        for feed in feed_df['feed_name'].unique():
            feed_counts[feed] = len(feed_df[feed_df['feed_name'] == feed])

    print(f"\n  Live job count for {today}: {total_live:,}")
    for feed, count in feed_counts.items():
        print(f"    {feed}: {count:,}")

    if dry_run:
        print("  [DRY RUN] Would record daily count")
        return

    # Ensure the history table exists
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS `{BQ_PROJECT}.{BQ_DATASET}.daily_live_job_counts` (
        date DATE,
        total_live_jobs INT64,
        scrape_jobs INT64,
        civil_service_jobs INT64,
        ats_jobs INT64,
        recorded_at TIMESTAMP
    )
    """
    client.query(create_sql).result()

    # Insert or replace today's count
    merge_sql = f"""
    MERGE `{BQ_PROJECT}.{BQ_DATASET}.daily_live_job_counts` AS target
    USING (
        SELECT
            DATE('{today}') as date,
            {total_live} as total_live_jobs,
            {feed_counts.get('Scrape', 0)} as scrape_jobs,
            {feed_counts.get('Civil Service', 0)} as civil_service_jobs,
            {feed_counts.get('ATS', 0)} as ats_jobs,
            CURRENT_TIMESTAMP() as recorded_at
    ) AS source
    ON target.date = source.date
    WHEN MATCHED THEN UPDATE SET
        total_live_jobs = source.total_live_jobs,
        scrape_jobs = source.scrape_jobs,
        civil_service_jobs = source.civil_service_jobs,
        ats_jobs = source.ats_jobs,
        recorded_at = source.recorded_at
    WHEN NOT MATCHED THEN INSERT (date, total_live_jobs, scrape_jobs, civil_service_jobs, ats_jobs, recorded_at)
    VALUES (source.date, source.total_live_jobs, source.scrape_jobs, source.civil_service_jobs, source.ats_jobs, source.recorded_at)
    """

    print("  Recording daily count...", end=' ', flush=True)
    job = client.query(merge_sql)
    job.result()
    print("OK")


def main():
    parser = argparse.ArgumentParser(description='Sync job feeds to BigQuery')
    parser.add_argument('--dry-run', action='store_true', help='Preview without executing')
    args = parser.parse_args()

    start_time = datetime.now()
    print(f"Job Feed Sync")
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    client = get_client() if not args.dry_run else None

    # Step 1: Fetch all feeds
    print(f"\nFetching feeds...")
    all_records = []
    for feed_name, url in FEEDS.items():
        job_elements = fetch_feed(feed_name, url)
        records = parse_feed_jobs(feed_name, job_elements)
        all_records.extend(records)

    print(f"\nTotal jobs across all feeds: {len(all_records):,}")

    # Step 2: Sync to BigQuery
    print(f"\nSyncing to BigQuery...")
    if args.dry_run:
        feed_df = pd.DataFrame(all_records) if all_records else None
        sync_to_bigquery(None, all_records, dry_run=True)
    else:
        feed_df = sync_to_bigquery(client, all_records, dry_run=False)

    # Step 3: Record daily live job count
    print(f"\nRecording daily live job count...")
    if args.dry_run:
        record_daily_live_count(None, feed_df, dry_run=True)
    else:
        record_daily_live_count(client, feed_df, dry_run=False)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"Completed in {elapsed:.0f}s")


if __name__ == '__main__':
    main()
