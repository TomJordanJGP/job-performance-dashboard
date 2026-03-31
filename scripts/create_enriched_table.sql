-- Create enriched job performance table with metadata from Jobiqo export
-- This combines GA4 events with Jobiqo metadata for complete job information
-- Run this SQL in BigQuery console: https://console.cloud.google.com/bigquery

-- Step 1: Create enriched table with JOIN, proper data types, and partitioning
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.job_performance_enriched`
PARTITION BY event_date_parsed
CLUSTER BY entity_id_str, event_date_parsed
AS
SELECT
  -- Converted fields for proper types and joining
  CAST(events.entity_id AS STRING) as entity_id_str,
  PARSE_DATE('%Y%m%d', events.event_date) as event_date_parsed,

  -- Original event fields
  events.event_name,
  events.event_date as event_date_original,
  events.hour_of_day,
  events.entity_id as entity_id_original,
  events.entity_type,
  events.organization_name,
  events.title as title_ga4,
  events.occupations as occupations_ga4,
  events.regions as regions_ga4,
  events.employment_types,
  events.importer_ID,
  events.owner_id,
  events.organization_id,
  events.page_referrer,
  events.page_location,
  events.upgrades,
  events.ats_vacancy_number,
  events.ats_account_number,
  events.device,
  events.operating_system,
  events.browser,
  events.campaign,
  events.medium,
  events.source,
  events.Events,

  -- Metadata from Jobiqo export (with _export suffix for comparison)
  metadata.title as title_export,
  metadata.workflow_state,
  metadata.occupational_fields as occupational_fields_export,
  metadata.locations as locations_export,
  metadata.publishing_date,
  metadata.expiration_date,
  metadata.organization_profile_name,
  metadata.employment_type as employment_type_export,
  metadata.last_updated as metadata_last_updated

FROM `site-monitoring-421401.job_data_export.job_performance_details_combined` AS events
LEFT JOIN `site-monitoring-421401.job_data_export.job_metadata` AS metadata
  ON CAST(events.entity_id AS STRING) = metadata.entity_id;

-- Step 2: Verify the enriched table
SELECT
  COUNT(*) as total_rows,
  MIN(event_date_parsed) as min_date,
  MAX(event_date_parsed) as max_date,
  COUNT(DISTINCT entity_id_str) as unique_entities,
  COUNT(DISTINCT CASE WHEN title_export IS NOT NULL THEN entity_id_str END) as entities_with_metadata,
  ROUND(COUNT(DISTINCT CASE WHEN title_export IS NOT NULL THEN entity_id_str END) * 100.0 / COUNT(DISTINCT entity_id_str), 2) as metadata_match_rate
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`;

-- Step 3: Test query performance (should be FAST with partitioning!)
SELECT
  entity_id_str,
  event_date_parsed,
  event_name,
  title_ga4,
  title_export,
  occupations_ga4,
  occupational_fields_export,
  regions_ga4,
  locations_export,
  workflow_state
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_date_parsed >= '2024-12-01'
LIMIT 20;

-- Step 4: Compare GA4 vs Export data quality
SELECT
  'title' as field,
  COUNT(CASE WHEN title_ga4 IS NOT NULL AND title_ga4 != '' THEN 1 END) as ga4_populated,
  COUNT(CASE WHEN title_export IS NOT NULL AND title_export != '' THEN 1 END) as export_populated
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_date_parsed >= '2024-12-01'

UNION ALL

SELECT
  'occupations/fields' as field,
  COUNT(CASE WHEN occupations_ga4 IS NOT NULL AND occupations_ga4 != '' THEN 1 END) as ga4_populated,
  COUNT(CASE WHEN occupational_fields_export IS NOT NULL AND occupational_fields_export != '' THEN 1 END) as export_populated
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_date_parsed >= '2024-12-01'

UNION ALL

SELECT
  'regions/locations' as field,
  COUNT(CASE WHEN regions_ga4 IS NOT NULL AND regions_ga4 != '' THEN 1 END) as ga4_populated,
  COUNT(CASE WHEN locations_export IS NOT NULL AND locations_export != '' THEN 1 END) as export_populated
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_date_parsed >= '2024-12-01';

-- Once verified, you can set up a scheduled query to refresh this table daily
-- Go to: https://console.cloud.google.com/bigquery/scheduled-queries
-- Use the CREATE OR REPLACE statement above and schedule it for daily refresh
