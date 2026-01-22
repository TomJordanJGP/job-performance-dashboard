"""
Upload job_export CSV data to BigQuery.

This script uploads the job_export.csv file to BigQuery, replacing the existing table.
Run this script whenever you have new job export data to upload.

Usage:
    python scripts/upload_job_export_to_bq.py [path_to_csv]

Example:
    python scripts/upload_job_export_to_bq.py data/job_export.csv
    python scripts/upload_job_export_to_bq.py  # Uses default path: data/job_export.csv
"""

import os
import sys
from pathlib import Path
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd

# Configuration
PROJECT_ID = "jgp-data-dev"
DATASET_ID = "jgp_recruitment"
TABLE_ID = "job_export"
DEFAULT_CSV_PATH = "data/job_export.csv"

def get_credentials():
    """Get BigQuery credentials from service account file."""
    # Get the project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Path to service account key
    key_path = project_root / "jgp-data-dev-bq-key.json"

    if not key_path.exists():
        raise FileNotFoundError(
            f"Service account key not found at: {key_path}\n"
            "Please ensure jgp-data-dev-bq-key.json is in the project root directory."
        )

    return service_account.Credentials.from_service_account_file(
        str(key_path),
        scopes=["https://www.googleapis.com/auth/bigquery"]
    )

def validate_csv(csv_path):
    """Validate that the CSV file exists and has data."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Check if file has data
    df = pd.read_csv(csv_path, nrows=1)
    if df.empty:
        raise ValueError(f"CSV file is empty: {csv_path}")

    print(f"✓ CSV file validated: {csv_path}")
    return True

def upload_to_bigquery(csv_path, credentials):
    """Upload CSV file to BigQuery, replacing existing table."""
    # Initialize BigQuery client
    client = bigquery.Client(
        credentials=credentials,
        project=PROJECT_ID
    )

    # Full table ID
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    print(f"\nUploading to BigQuery table: {table_ref}")
    print(f"Source file: {csv_path}")

    # Configure the load job
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,  # Skip header row
        autodetect=True,  # Auto-detect schema
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # Replace table
    )

    # Load the CSV file
    with open(csv_path, "rb") as source_file:
        load_job = client.load_table_from_file(
            source_file,
            table_ref,
            job_config=job_config
        )

    # Wait for the job to complete
    print("\nUploading... ", end="", flush=True)
    load_job.result()  # Waits for job to complete

    # Get table info
    table = client.get_table(table_ref)

    print(f"✓ Upload complete!")
    print(f"\nTable details:")
    print(f"  - Rows: {table.num_rows:,}")
    print(f"  - Size: {table.num_bytes / 1024 / 1024:.2f} MB")
    print(f"  - Columns: {len(table.schema)}")
    print(f"\nTable updated: {table_ref}")

    return table

def main():
    """Main execution function."""
    # Get CSV path from command line argument or use default
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = DEFAULT_CSV_PATH

    # Convert to absolute path
    csv_path = os.path.abspath(csv_path)

    print("=" * 60)
    print("BigQuery Job Export Upload Script")
    print("=" * 60)

    try:
        # Validate CSV file
        validate_csv(csv_path)

        # Get credentials
        print("\n✓ Loading credentials...")
        credentials = get_credentials()

        # Upload to BigQuery
        upload_to_bigquery(csv_path, credentials)

        print("\n" + "=" * 60)
        print("✓ SUCCESS: Data uploaded successfully!")
        print("=" * 60)

    except FileNotFoundError as e:
        print(f"\n✗ ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"\n✗ ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: Upload failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
