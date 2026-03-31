"""
Upload location lookup CSV directly to BigQuery using file upload
This bypasses the table creation permission issue by loading directly from file
"""

from google.cloud import bigquery
import os

# Set credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard/service_account.json'

# Configuration
PROJECT_ID = 'site-monitoring-421401'
DATASET_ID = 'job_data_export'
TABLE_ID = 'location_lookup'
CSV_FILE = '/Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard/location_lookup_with_regions.csv'

print("=" * 80)
print("Uploading Location Lookup to BigQuery")
print("=" * 80)

# Initialize BigQuery client
client = bigquery.Client(project=PROJECT_ID)

# Define the full table ID
full_table_id = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

# Configure the load job with schema
print(f"\n1. Preparing to load CSV to: {full_table_id}")
print(f"   Source: {CSV_FILE}")

# Define schema explicitly
schema = [
    bigquery.SchemaField("country_code", "STRING"),
    bigquery.SchemaField("town_city", "STRING"),
    bigquery.SchemaField("country", "STRING"),
    bigquery.SchemaField("county", "STRING"),
    bigquery.SchemaField("region", "STRING"),
]

job_config = bigquery.LoadJobConfig(
    schema=schema,
    skip_leading_rows=1,  # Skip header row
    source_format=bigquery.SourceFormat.CSV,
    write_disposition="WRITE_TRUNCATE",  # Replace table if it exists
    create_disposition="CREATE_IF_NEEDED",  # Create table if needed
)

# Load from file
print(f"\n2. Loading CSV file...")
with open(CSV_FILE, "rb") as source_file:
    job = client.load_table_from_file(
        source_file,
        full_table_id,
        job_config=job_config,
    )

# Wait for the job to complete
print(f"   ⏳ Waiting for load job to complete...")
job.result()

print(f"   ✅ Upload complete!")

# Verify the table
print(f"\n3. Verifying table...")
table = client.get_table(full_table_id)
print(f"   ✅ Table has {table.num_rows:,} rows")
print(f"   ✅ Schema:")
for field in table.schema:
    print(f"      - {field.name}: {field.field_type}")

# Run a test query
print(f"\n4. Running test query...")
query = f"""
SELECT
  region,
  COUNT(*) as town_count
FROM `{full_table_id}`
GROUP BY region
ORDER BY town_count DESC
"""

df_result = client.query(query).to_dataframe()
print(f"\n   Towns by Region:")
print(df_result)

print("\n" + "=" * 80)
print("✅ COMPLETE!")
print("=" * 80)
print(f"\nLocation lookup table is ready at: {full_table_id}")
print("\nNext steps:")
print("1. Run create_enriched_table_with_regions.sql in BigQuery console")
print("2. This will create the enriched table with proper regions")
