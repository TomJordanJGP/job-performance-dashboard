"""
Create and populate job metadata table in BigQuery from Google Sheets
This table will be joined with events data to add occupation, location, status, etc.
"""

from google.cloud import bigquery
from google.oauth2 import service_account
import gspread
import pandas as pd
import os

# Set credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '../service_account.json'

# Google Sheets configuration
SPREADSHEET_ID = '1eREp6EfdS4Tm4c-GUZQ4GdFH1LFZfBpx20ZbkSTiyZE'
SHEET_NAME = 'Sheet1'  # Adjust if needed

def create_metadata_table():
    """Create the job_metadata table in BigQuery if it doesn't exist."""
    client = bigquery.Client()

    table_id = "site-monitoring-421401.job_data_export.job_metadata"

    # Check if table already exists
    try:
        client.get_table(table_id)
        print(f"✅ Table {table_id} already exists")
        return table_id
    except Exception:
        print(f"Table doesn't exist, attempting to create...")

    # Define table schema
    schema = [
        bigquery.SchemaField("entity_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("title", "STRING"),
        bigquery.SchemaField("workflow_state", "STRING"),
        bigquery.SchemaField("occupational_fields", "STRING"),
        bigquery.SchemaField("locations", "STRING"),
        bigquery.SchemaField("publishing_date", "TIMESTAMP"),
        bigquery.SchemaField("expiration_date", "TIMESTAMP"),
        bigquery.SchemaField("organization_profile_name", "STRING"),
        bigquery.SchemaField("organization_id", "STRING"),
        bigquery.SchemaField("employment_type", "STRING"),
        bigquery.SchemaField("last_updated", "TIMESTAMP"),
    ]

    # Create table
    table = bigquery.Table(table_id, schema=schema)
    table = client.create_table(table, exists_ok=True)

    print(f"✅ Created table {table_id}")
    return table_id


def load_data_from_sheets(table_id):
    """Load data from Google Sheets into BigQuery table."""
    client = bigquery.Client()

    print(f"Loading data from Google Sheets (ID: {SPREADSHEET_ID})...")

    # Authenticate with Google Sheets
    creds = service_account.Credentials.from_service_account_file(
        '../service_account.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )
    gc = gspread.authorize(creds)

    # Open spreadsheet and get data
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_NAME)

    # Get all values and convert to DataFrame
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    print(f"Found {len(df)} jobs in Google Sheets")

    # Prepare dataframe for BigQuery with proper type conversions
    df_clean = pd.DataFrame({
        'entity_id': df['job_id'].fillna('').astype(str),
        'title': df['title'].fillna('').astype(str),
        'workflow_state': df['workflow_state'].fillna('').astype(str),
        'occupational_fields': df['occupational_fields'].fillna('').astype(str),
        'locations': df['locations'].fillna('').astype(str),
        'publishing_date': pd.to_datetime(df['publishing_date'], format='%d/%m/%Y %H:%M', errors='coerce'),
        'expiration_date': pd.to_datetime(df['expiration_date'], format='%d/%m/%Y %H:%M', errors='coerce'),
        'organization_profile_name': df['organization_profile_name'].fillna('').astype(str),
        'organization_id': df.get('organization_id', pd.Series([''] * len(df))).fillna('').astype(str),
        'employment_type': df.get('employment_type', pd.Series([''] * len(df))).fillna('').astype(str),
        'last_updated': pd.Timestamp.now()
    })

    # Remove duplicates (keep most recent)
    df_clean = df_clean.drop_duplicates(subset=['entity_id'], keep='last')

    print(f"Loading {len(df_clean)} unique jobs to BigQuery...")

    # Configure load job
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",  # Replace all data
        schema_update_options=[
            bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION
        ]
    )

    # Load to BigQuery
    job = client.load_table_from_dataframe(
        df_clean,
        table_id,
        job_config=job_config
    )

    job.result()  # Wait for completion

    print(f"✅ Loaded {len(df_clean)} jobs to {table_id}")

    # Verify
    table = client.get_table(table_id)
    print(f"✅ Table now contains {table.num_rows} rows")


def test_query():
    """Test the metadata table with a sample query."""
    client = bigquery.Client()

    query = """
    SELECT
        entity_id,
        title,
        workflow_state,
        occupational_fields,
        locations,
        publishing_date,
        expiration_date
    FROM `site-monitoring-421401.job_data_export.job_metadata`
    LIMIT 10
    """

    print("\nTesting query...")
    df = client.query(query).to_dataframe()
    print(df)
    print(f"\n✅ Query successful! Retrieved {len(df)} rows")


if __name__ == "__main__":
    print("=" * 80)
    print("Loading Job Metadata to BigQuery from Google Sheets")
    print("=" * 80)

    table_id = "site-monitoring-421401.job_data_export.job_metadata"

    # Check if table exists, create if needed
    try:
        create_metadata_table()
    except Exception as e:
        print(f"⚠️  Could not create table: {e}")
        print("Please run the SQL in scripts/create_table.sql in BigQuery console first")
        print("Then run this script again")
        exit(1)

    # Load data from Google Sheets
    load_data_from_sheets(table_id)

    # Test
    test_query()

    print("\n" + "=" * 80)
    print("✅ COMPLETE!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Update app.py to use new joined query")
    print("2. Test dashboard")
