-- Create location_lookup table in BigQuery
-- Run this SQL in BigQuery console: https://console.cloud.google.com/bigquery
-- Then manually upload the CSV: location_lookup_with_regions.csv

-- Step 1: Create the table schema
CREATE TABLE IF NOT EXISTS `site-monitoring-421401.job_data_export.location_lookup` (
  country_code STRING,
  town_city STRING,
  country STRING,
  county STRING,
  region STRING,
  last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Step 2: After running the above, go to the BigQuery UI:
-- 1. Click on the location_lookup table
-- 2. Click "+" next to "Query" and select "Load data"
-- 3. Choose "Upload" and select: location_lookup_with_regions.csv
-- 4. Format: CSV
-- 5. Write preference: "Overwrite table"
-- 6. Click "Load data"

-- Step 3: After loading, verify the data
SELECT
  COUNT(*) as total_towns,
  COUNT(DISTINCT region) as unique_regions,
  COUNT(DISTINCT county) as unique_counties
FROM `site-monitoring-421401.job_data_export.location_lookup`;

-- Step 4: Check region distribution
SELECT
  region,
  COUNT(*) as town_count
FROM `site-monitoring-421401.job_data_export.location_lookup`
GROUP BY region
ORDER BY town_count DESC;

-- Step 5: Preview the data
SELECT *
FROM `site-monitoring-421401.job_data_export.location_lookup`
LIMIT 20;
