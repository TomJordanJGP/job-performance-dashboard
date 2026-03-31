-- Load location lookup table from Google Sheets into BigQuery
-- This table maps UK towns/cities to their counties and regions
-- Run this SQL in BigQuery console: https://console.cloud.google.com/bigquery

-- Step 1: Create external table that reads from Google Sheets
-- IMPORTANT: Replace 'YOUR_SPREADSHEET_ID' with the actual Google Sheets ID
CREATE OR REPLACE EXTERNAL TABLE `site-monitoring-421401.job_data_export.location_lookup_external`
OPTIONS (
  format = 'GOOGLE_SHEETS',
  uris = ['https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID'],
  skip_leading_rows = 1
);

-- Step 2: Load data into permanent table with proper types
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.location_lookup` AS
SELECT
  CAST(country_code AS STRING) as country_code,
  CAST(town_city AS STRING) as town_city,
  CAST(country AS STRING) as country,
  CAST(county AS STRING) as county,
  CAST(region AS STRING) as region,
  CURRENT_TIMESTAMP() as last_updated
FROM `site-monitoring-421401.job_data_export.location_lookup_external`;

-- Step 3: Verify the load
SELECT
  COUNT(*) as total_towns,
  COUNT(DISTINCT region) as unique_regions,
  COUNT(DISTINCT county) as unique_counties
FROM `site-monitoring-421401.job_data_export.location_lookup`;

-- Step 4: Preview the data
SELECT *
FROM `site-monitoring-421401.job_data_export.location_lookup`
LIMIT 20;

-- Step 5: Check region distribution
SELECT
  region,
  COUNT(*) as town_count
FROM `site-monitoring-421401.job_data_export.location_lookup`
GROUP BY region
ORDER BY town_count DESC;
