#!/usr/bin/env python3
"""Upload a Jobiqo CSV export to backfill entity_ids and CSV-only fields in job_metadata.

The CSV export is the source of truth. This script:
1. Matches CSV rows to job_metadata by external_id (primary) then entity_id (secondary)
2. Backfills entity_id (always) and CSV-only fields (fill blanks only — never overwrites feed data)
3. Inserts any CSV rows not already in job_metadata
4. Runs dedup checks to flag any issues

Usage:
    python scripts/upload_csv_export.py path/to/jobs-export-XXXXXXX.csv
    python scripts/upload_csv_export.py path/to/jobs-export-XXXXXXX.csv --dry-run
"""

import os
import sys
import re
import argparse
from datetime import datetime

import pandas as pd

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)

BQ_PROJECT = "site-monitoring-421401"
BQ_DATASET = "job_data_export"
STAGING_TABLE = f"{BQ_PROJECT}.{BQ_DATASET}.staging_csv_export"


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


def load_and_clean_csv(csv_path):
    """Load CSV export and normalise columns to match job_metadata schema."""
    df = pd.read_csv(csv_path)
    print(f"  Loaded {len(df)} rows from {os.path.basename(csv_path)}")

    # Rename columns to match job_metadata
    rename_map = {
        'job_id': 'entity_id',
        'External ID': 'external_id',
        'Employer type (Industry)': 'employer_type',
        'Original publishing date': 'original_publishing_date',
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Strip N_ prefix from external_id (e.g. "2_abc123" → "abc123")
    if 'external_id' in df.columns:
        df['external_id'] = df['external_id'].apply(
            lambda x: re.sub(r'^[0-9]+_', '', str(x)) if pd.notna(x) else ''
        )

    # Convert entity_id to string
    df['entity_id'] = df['entity_id'].apply(
        lambda x: str(int(x)) if pd.notna(x) else ''
    )

    # Convert organization_id to string
    if 'organization_id' in df.columns:
        df['organization_id'] = df['organization_id'].apply(
            lambda x: str(int(x)) if pd.notna(x) and str(x).strip() not in ('', 'nan') else ''
        )

    # Parse date columns
    date_cols = ['publishing_date', 'expiration_date', 'original_publishing_date']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce', utc=True)

    # Parse salary fields to float
    for col in ['min_salary', 'max_salary']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Add last_updated
    df['last_updated'] = pd.Timestamp.now(tz='UTC')

    # Keep only columns that exist in job_metadata
    metadata_cols = [
        'entity_id', 'external_id', 'title', 'workflow_state',
        'organization_id', 'organization_profile_name', 'locations',
        'employment_type', 'occupational_fields', 'employer_type',
        'publishing_date', 'expiration_date', 'original_publishing_date',
        'salary_free_text', 'min_salary', 'max_salary', 'currency_code',
        'salary_unit', 'last_updated'
    ]
    # Map CSV 'salary' to 'salary_free_text' if present
    if 'salary' in df.columns and 'salary_free_text' not in df.columns:
        df = df.rename(columns={'salary': 'salary_free_text'})

    available = [c for c in metadata_cols if c in df.columns]
    df = df[available]

    print(f"  Columns: {', '.join(available)}")
    print(f"  With external_id: {(df['external_id'].str.strip() != '').sum()}")
    print(f"  Without external_id: {(df['external_id'].str.strip() == '').sum()}")

    return df


def upload_staging(client, df):
    """Upload cleaned CSV to BigQuery staging table."""
    from google.cloud import bigquery

    schema = [
        bigquery.SchemaField('entity_id', 'STRING'),
        bigquery.SchemaField('external_id', 'STRING'),
        bigquery.SchemaField('title', 'STRING'),
        bigquery.SchemaField('workflow_state', 'STRING'),
        bigquery.SchemaField('organization_id', 'STRING'),
        bigquery.SchemaField('organization_profile_name', 'STRING'),
        bigquery.SchemaField('locations', 'STRING'),
        bigquery.SchemaField('employment_type', 'STRING'),
        bigquery.SchemaField('occupational_fields', 'STRING'),
        bigquery.SchemaField('employer_type', 'STRING'),
        bigquery.SchemaField('publishing_date', 'TIMESTAMP'),
        bigquery.SchemaField('expiration_date', 'TIMESTAMP'),
        bigquery.SchemaField('original_publishing_date', 'TIMESTAMP'),
        bigquery.SchemaField('salary_free_text', 'STRING'),
        bigquery.SchemaField('min_salary', 'FLOAT64'),
        bigquery.SchemaField('max_salary', 'FLOAT64'),
        bigquery.SchemaField('currency_code', 'STRING'),
        bigquery.SchemaField('salary_unit', 'STRING'),
        bigquery.SchemaField('last_updated', 'TIMESTAMP'),
    ]
    # Only include schema fields that exist in the dataframe
    schema = [s for s in schema if s.name in df.columns]

    job_config = bigquery.LoadJobConfig(
        write_disposition='WRITE_TRUNCATE',
        schema=schema
    )
    job = client.load_table_from_dataframe(df, STAGING_TABLE, job_config=job_config)
    job.result()
    print(f"  Uploaded {len(df)} rows to staging table")


def preview_matches(client):
    """Report how CSV rows will match against job_metadata."""
    q = f"""
    WITH staging AS (
        SELECT * FROM `{STAGING_TABLE}`
    ),
    -- Pass 1: match by external_id
    ext_match AS (
        SELECT s.entity_id as csv_entity_id, s.external_id,
               m.entity_id as existing_entity_id
        FROM staging s
        JOIN `{BQ_PROJECT}.{BQ_DATASET}.job_metadata` m
          ON s.external_id = m.external_id
        WHERE s.external_id IS NOT NULL AND TRIM(s.external_id) != ''
    ),
    -- Pass 2: match by entity_id (for rows that didn't match on external_id)
    eid_match AS (
        SELECT s.entity_id as csv_entity_id, s.external_id,
               m.entity_id as existing_entity_id
        FROM staging s
        JOIN `{BQ_PROJECT}.{BQ_DATASET}.job_metadata` m
          ON s.entity_id = m.entity_id
        WHERE (s.external_id IS NULL OR TRIM(s.external_id) = ''
               OR s.external_id NOT IN (SELECT external_id FROM ext_match))
          AND s.entity_id IS NOT NULL AND TRIM(s.entity_id) != ''
    )
    SELECT
        (SELECT COUNT(*) FROM staging) as total_csv_rows,
        (SELECT COUNT(*) FROM ext_match) as matched_by_external_id,
        (SELECT COUNT(*) FROM ext_match WHERE existing_entity_id IS NULL OR TRIM(existing_entity_id) = '') as will_get_entity_id,
        (SELECT COUNT(*) FROM eid_match) as matched_by_entity_id,
        (SELECT COUNT(*) FROM staging s
         WHERE (s.external_id IS NULL OR TRIM(s.external_id) = ''
                OR s.external_id NOT IN (SELECT external_id FROM ext_match))
           AND (s.entity_id IS NULL OR TRIM(s.entity_id) = ''
                OR s.entity_id NOT IN (SELECT csv_entity_id FROM eid_match))
        ) as unmatched_will_insert
    """
    r = client.query(q).to_dataframe()
    row = r.iloc[0]
    print(f"\n  Match preview:")
    print(f"    Total CSV rows:              {int(row['total_csv_rows']):,}")
    print(f"    Matched by external_id:      {int(row['matched_by_external_id']):,}")
    print(f"      → Will receive entity_id:  {int(row['will_get_entity_id']):,}")
    print(f"    Matched by entity_id:        {int(row['matched_by_entity_id']):,}")
    print(f"    Unmatched (will insert):     {int(row['unmatched_will_insert']):,}")
    return row


def run_merge(client):
    """Execute the three-pass merge."""

    # Fill-blanks-only helper for SQL
    def fill_blank(target_col, source_col):
        return f"target.{target_col} = IF(target.{target_col} IS NULL OR TRIM(CAST(target.{target_col} AS STRING)) IN ('', 'nan'), source.{source_col}, target.{target_col})"

    fill_cols = [
        ('employer_type', 'employer_type'),
        ('occupational_fields', 'occupational_fields'),
        ('original_publishing_date', 'original_publishing_date'),
        ('organization_id', 'organization_id'),
        ('organization_profile_name', 'organization_profile_name'),
        ('workflow_state', 'workflow_state'),
        ('locations', 'locations'),
        ('employment_type', 'employment_type'),
        ('publishing_date', 'publishing_date'),
        ('expiration_date', 'expiration_date'),
        ('salary_free_text', 'salary_free_text'),
        ('min_salary', 'min_salary'),
        ('max_salary', 'max_salary'),
        ('currency_code', 'currency_code'),
        ('salary_unit', 'salary_unit'),
        ('title', 'title'),
    ]
    fill_sql = ',\n        '.join([fill_blank(t, s) for t, s in fill_cols])

    # Pass 1: Match on external_id — set entity_id + fill blanks
    pass1_sql = f"""
    MERGE `{BQ_PROJECT}.{BQ_DATASET}.job_metadata` AS target
    USING `{STAGING_TABLE}` AS source
    ON target.external_id = source.external_id
       AND source.external_id IS NOT NULL AND TRIM(source.external_id) != ''
    WHEN MATCHED THEN UPDATE SET
        target.entity_id = source.entity_id,
        {fill_sql},
        target.last_updated = source.last_updated
    """

    print("  Pass 1: MERGE on external_id...", end=' ', flush=True)
    job1 = client.query(pass1_sql)
    job1.result()
    print(f"OK ({job1.num_dml_affected_rows} rows)")

    # Pass 2: Match on entity_id for rows without external_id match — fill blanks only
    pass2_sql = f"""
    MERGE `{BQ_PROJECT}.{BQ_DATASET}.job_metadata` AS target
    USING (
        SELECT s.*
        FROM `{STAGING_TABLE}` s
        WHERE s.external_id IS NULL OR TRIM(s.external_id) = ''
           OR s.external_id NOT IN (
               SELECT external_id FROM `{BQ_PROJECT}.{BQ_DATASET}.job_metadata`
               WHERE external_id IS NOT NULL AND TRIM(external_id) != ''
           )
    ) AS source
    ON target.entity_id = source.entity_id
       AND source.entity_id IS NOT NULL AND TRIM(source.entity_id) != ''
    WHEN MATCHED THEN UPDATE SET
        target.external_id = IF(target.external_id IS NULL OR TRIM(target.external_id) = '', source.external_id, target.external_id),
        {fill_sql},
        target.last_updated = source.last_updated
    """

    print("  Pass 2: MERGE on entity_id...", end=' ', flush=True)
    job2 = client.query(pass2_sql)
    job2.result()
    print(f"OK ({job2.num_dml_affected_rows} rows)")

    # Pass 3: Insert unmatched rows
    insert_cols = [
        'entity_id', 'external_id', 'title', 'workflow_state',
        'organization_id', 'organization_profile_name', 'locations',
        'employment_type', 'occupational_fields', 'employer_type',
        'publishing_date', 'expiration_date', 'original_publishing_date',
        'salary_free_text', 'min_salary', 'max_salary', 'currency_code',
        'salary_unit', 'last_updated'
    ]
    cols_list = ', '.join(insert_cols)
    source_cols = ', '.join([f'source.{c}' for c in insert_cols])

    pass3_sql = f"""
    MERGE `{BQ_PROJECT}.{BQ_DATASET}.job_metadata` AS target
    USING (
        SELECT s.*
        FROM `{STAGING_TABLE}` s
        LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.job_metadata` m1
          ON s.external_id = m1.external_id
             AND s.external_id IS NOT NULL AND TRIM(s.external_id) != ''
        LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.job_metadata` m2
          ON s.entity_id = m2.entity_id
             AND s.entity_id IS NOT NULL AND TRIM(s.entity_id) != ''
        WHERE m1.external_id IS NULL AND m2.entity_id IS NULL
    ) AS source
    ON FALSE
    WHEN NOT MATCHED THEN INSERT ({cols_list})
    VALUES ({source_cols})
    """

    print("  Pass 3: INSERT unmatched...", end=' ', flush=True)
    job3 = client.query(pass3_sql)
    job3.result()
    print(f"OK ({job3.num_dml_affected_rows} rows)")


def run_dedup_checks(client):
    """Check for duplicates after merge."""
    print("\n  Dedup checks:")

    # Duplicate entity_ids
    q1 = f"""
    SELECT entity_id, COUNT(*) as cnt
    FROM `{BQ_PROJECT}.{BQ_DATASET}.job_metadata`
    WHERE entity_id IS NOT NULL AND TRIM(entity_id) != ''
    GROUP BY entity_id HAVING cnt > 1
    ORDER BY cnt DESC LIMIT 10
    """
    r1 = client.query(q1).to_dataframe()
    if len(r1) > 0:
        print(f"    ⚠️  {len(r1)} duplicate entity_ids found:")
        for _, row in r1.iterrows():
            print(f"      entity_id={row['entity_id']} appears {row['cnt']} times")
    else:
        print("    ✅ No duplicate entity_ids")

    # Duplicate external_ids
    q2 = f"""
    SELECT external_id, COUNT(*) as cnt
    FROM `{BQ_PROJECT}.{BQ_DATASET}.job_metadata`
    WHERE external_id IS NOT NULL AND TRIM(external_id) != ''
    GROUP BY external_id HAVING cnt > 1
    ORDER BY cnt DESC LIMIT 10
    """
    r2 = client.query(q2).to_dataframe()
    if len(r2) > 0:
        print(f"    ⚠️  {len(r2)} duplicate external_ids found:")
        for _, row in r2.iterrows():
            print(f"      external_id={row['external_id'][:30]}... appears {row['cnt']} times")
    else:
        print("    ✅ No duplicate external_ids")

    # Entity_id with multiple external_ids
    q3 = f"""
    SELECT entity_id, COUNT(DISTINCT external_id) as ext_count
    FROM `{BQ_PROJECT}.{BQ_DATASET}.job_metadata`
    WHERE entity_id IS NOT NULL AND TRIM(entity_id) != ''
      AND external_id IS NOT NULL AND TRIM(external_id) != ''
    GROUP BY entity_id HAVING ext_count > 1
    ORDER BY ext_count DESC LIMIT 10
    """
    r3 = client.query(q3).to_dataframe()
    if len(r3) > 0:
        print(f"    ⚠️  {len(r3)} entity_ids with multiple external_ids (possible reimports):")
        for _, row in r3.iterrows():
            print(f"      entity_id={row['entity_id']} has {row['ext_count']} external_ids")
    else:
        print("    ✅ No entity_ids with multiple external_ids")


def report_remaining(client):
    """Report remaining gaps."""
    q = f"""
    SELECT
        COUNT(*) as total,
        COUNTIF(entity_id IS NULL OR TRIM(entity_id) = '') as missing_entity_id,
        COUNTIF(organization_profile_name IS NULL OR TRIM(organization_profile_name) = '') as missing_org_name,
        COUNTIF(employer_type IS NULL OR TRIM(employer_type) = '') as missing_employer_type
    FROM `{BQ_PROJECT}.{BQ_DATASET}.job_metadata`
    """
    r = client.query(q).to_dataframe()
    row = r.iloc[0]
    print(f"\n  Final state of job_metadata:")
    print(f"    Total rows:            {int(row['total']):,}")
    print(f"    Missing entity_id:     {int(row['missing_entity_id']):,}")
    print(f"    Missing org_name:      {int(row['missing_org_name']):,}")
    print(f"    Missing employer_type: {int(row['missing_employer_type']):,}")


def main():
    parser = argparse.ArgumentParser(description='Upload Jobiqo CSV export to backfill job_metadata')
    parser.add_argument('csv_path', help='Path to the jobs-export CSV file')
    parser.add_argument('--dry-run', action='store_true', help='Preview matches without updating')
    args = parser.parse_args()

    if not os.path.exists(args.csv_path):
        print(f"ERROR: File not found: {args.csv_path}")
        sys.exit(1)

    start_time = datetime.now()
    print(f"CSV Export Upload")
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"File: {args.csv_path}")

    # Load and clean CSV
    print(f"\nStep 1: Load CSV")
    df = load_and_clean_csv(args.csv_path)

    # Upload to staging
    print(f"\nStep 2: Upload to staging")
    client = get_client()
    upload_staging(client, df)

    # Preview matches
    print(f"\nStep 3: Preview matches")
    preview_matches(client)

    if args.dry_run:
        print(f"\n[DRY RUN] No changes made. Remove --dry-run to execute.")
        client.delete_table(STAGING_TABLE, not_found_ok=True)
        return

    # Run merge
    print(f"\nStep 4: Run merge")
    run_merge(client)

    # Dedup checks
    print(f"\nStep 5: Dedup checks")
    run_dedup_checks(client)

    # Report
    print(f"\nStep 6: Report")
    report_remaining(client)

    # Clean up
    client.delete_table(STAGING_TABLE, not_found_ok=True)
    print(f"\n  Staging table cleaned up.")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"Completed in {elapsed:.0f}s")


if __name__ == '__main__':
    main()
