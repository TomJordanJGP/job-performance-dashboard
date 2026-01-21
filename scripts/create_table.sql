-- Run this SQL in BigQuery console to create the job_metadata table
-- Go to: https://console.cloud.google.com/bigquery

CREATE TABLE IF NOT EXISTS `site-monitoring-421401.job_data_export.job_metadata` (
  entity_id STRING NOT NULL,
  title STRING,
  workflow_state STRING,
  occupational_fields STRING,
  locations STRING,
  publishing_date TIMESTAMP,
  expiration_date TIMESTAMP,
  organization_profile_name STRING,
  organization_id STRING,
  employment_type STRING,
  last_updated TIMESTAMP
);
