-- Load data from Google Sheets directly into BigQuery
-- Run this SQL in BigQuery console: https://console.cloud.google.com/bigquery

-- First, create an external table that reads from Google Sheets
CREATE OR REPLACE EXTERNAL TABLE `site-monitoring-421401.job_data_export.job_metadata_external`
OPTIONS (
  format = 'GOOGLE_SHEETS',
  uris = ['https://docs.google.com/spreadsheets/d/1eREp6EfdS4Tm4c-GUZQ4GdFH1LFZfBpx20ZbkSTiyZE'],
  skip_leading_rows = 1
);

-- Then, load the data into the permanent table with proper types
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.job_metadata` AS
SELECT
  CAST(job_id AS STRING) as entity_id,
  CAST(title AS STRING) as title,
  CAST(workflow_state AS STRING) as workflow_state,
  CAST(occupational_fields AS STRING) as occupational_fields,
  CAST(locations AS STRING) as locations,
  TIMESTAMP(publishing_date) as publishing_date,
  TIMESTAMP(expiration_date) as expiration_date,
  CAST(organization_profile_name AS STRING) as organization_profile_name,
  CAST(organization_id AS STRING) as organization_id,
  CAST(employment_type AS STRING) as employment_type,
  CURRENT_TIMESTAMP() as last_updated
FROM `site-monitoring-421401.job_data_export.job_metadata_external`;

-- Verify the load
SELECT COUNT(*) as total_jobs FROM `site-monitoring-421401.job_data_export.job_metadata`;
SELECT * FROM `site-monitoring-421401.job_data_export.job_metadata` LIMIT 10;
