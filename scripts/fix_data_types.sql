-- Fix data types in job_performance_details_combined table
-- This will create a new table with proper data types for better performance and partitioning
-- Run this SQL in BigQuery console: https://console.cloud.google.com/bigquery

-- Step 1: Create new table with corrected data types and proper partitioning
CREATE TABLE IF NOT EXISTS `site-monitoring-421401.job_data_export.job_performance_details_combined_fixed`
PARTITION BY event_date_parsed
CLUSTER BY entity_id_str, event_date_parsed
AS
SELECT
  -- Convert entity_id to STRING for joining with metadata table
  CAST(entity_id AS STRING) as entity_id_str,

  -- Convert event_date from STRING (YYYYMMDD) to proper DATE type
  PARSE_DATE('%Y%m%d', event_date) as event_date_parsed,

  -- Keep all original columns (except excluded ones)
  event_name,
  event_date as event_date_original,
  hour_of_day,
  entity_id as entity_id_original,
  entity_type,
  -- entity_subtype (EXCLUDED)
  organization_name,
  title,
  -- application_type (EXCLUDED)
  occupations,
  regions,
  employment_types,
  importer_ID,
  -- current_user_id (EXCLUDED)
  -- user_role (EXCLUDED)
  owner_id,
  -- owner_role does not exist in table
  organization_id,
  page_referrer,
  page_location,
  upgrades,
  ats_vacancy_number,
  ats_account_number,
  device,
  operating_system,
  browser,
  campaign,
  medium,
  source,
  Events
  -- site (EXCLUDED)

FROM `site-monitoring-421401.job_data_export.job_performance_details_combined`;

-- Step 2: Verify the new table
SELECT
  COUNT(*) as total_rows,
  MIN(event_date_parsed) as min_date,
  MAX(event_date_parsed) as max_date,
  COUNT(DISTINCT entity_id_str) as unique_entities
FROM `site-monitoring-421401.job_data_export.job_performance_details_combined_fixed`;

-- Step 3: Test query performance (should be FAST!)
SELECT *
FROM `site-monitoring-421401.job_data_export.job_performance_details_combined_fixed`
WHERE event_date_parsed >= '2024-12-01'
LIMIT 10;

-- Step 4: Test join with metadata table
SELECT
  events.entity_id_str,
  events.event_date_parsed,
  events.event_name,
  events.importer_ID,
  events.upgrades,
  metadata.title,
  metadata.occupational_fields,
  metadata.locations
FROM `site-monitoring-421401.job_data_export.job_performance_details_combined_fixed` AS events
LEFT JOIN `site-monitoring-421401.job_data_export.job_metadata` AS metadata
  ON events.entity_id_str = metadata.entity_id
WHERE events.event_date_parsed >= '2024-12-01'
LIMIT 10;

-- Once verified, you can rename the tables:
-- See end of file for rename commands (commented out for safety)

/*
-- Step 5: Backup and rename (UNCOMMENT AND RUN ONE AT A TIME after verification):

-- Backup original table
CREATE TABLE IF NOT EXISTS `site-monitoring-421401.job_data_export.job_performance_details_combined_backup`
AS SELECT * FROM `site-monitoring-421401.job_data_export.job_performance_details_combined`;

-- Drop original
DROP TABLE `site-monitoring-421401.job_data_export.job_performance_details_combined`;

-- Rename fixed table to original name
-- Note: You may need to do this in the UI or recreate with the original name
*/
