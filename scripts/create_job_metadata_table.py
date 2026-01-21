"""
Create and populate job metadata table in BigQuery from jobs-export.csv
This table will be joined with events data to add occupation, location, status, etc.
"""

from google.cloud import bigquery
import pandas as pd
import os

# Set credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '../service_account.json'

def create_metadata_table():
    """Create the job_metadata table in BigQuery."""
    client = bigquery.Client()

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

    table_id = "job-board-analytics-444710.job_board_events.job_metadata"

    # Create table
    table = bigquery.Table(table_id, schema=schema)
    table = client.create_table(table, exists_ok=True)

    print(f"✅ Created table {table_id}")
    return table_id


def load_data_from_csv(table_id):
    """Load data from jobs-export.csv into BigQuery table."""
    client = bigquery.Client()

    print("Loading jobs-export.csv...")
    df = pd.read_csv('../jobs-export.csv', low_memory=False)

    print(f"Found {len(df)} jobs in CSV")

    # Prepare dataframe for BigQuery
    df_clean = pd.DataFrame({
        'entity_id': df['job_id'].astype(str),
        'title': df['title'],
        'workflow_state': df['workflow_state'],
        'occupational_fields': df['occupational_fields'],
        'locations': df['locations'],
        'publishing_date': pd.to_datetime(df['publishing_date'], errors='coerce'),
        'expiration_date': pd.to_datetime(df['expiration_date'], errors='coerce'),
        'organization_profile_name': df['organization_profile_name'],
        'organization_id': df.get('organization_id', ''),
        'employment_type': df.get('employment_type', ''),
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
    FROM `job-board-analytics-444710.job_board_events.job_metadata`
    LIMIT 10
    """

    print("\nTesting query...")
    df = client.query(query).to_dataframe()
    print(df)
    print(f"\n✅ Query successful! Retrieved {len(df)} rows")


if __name__ == "__main__":
    print("=" * 80)
    print("Creating Job Metadata Table in BigQuery")
    print("=" * 80)

    # Step 1: Create table
    table_id = create_metadata_table()

    # Step 2: Load data from CSV
    load_data_from_csv(table_id)

    # Step 3: Test
    test_query()

    print("\n" + "=" * 80)
    print("✅ COMPLETE!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Update app.py to use new joined query")
    print("2. Remove CSV loading code")
    print("3. Test dashboard")
