-- Create enriched job performance table with metadata and parsed location regions
-- This combines GA4 events with Jobiqo metadata and adds proper UK regions
-- Run this SQL in BigQuery console: https://console.cloud.google.com/bigquery

-- Step 1: Create enriched table with location parsing and region lookup
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.job_performance_enriched`
PARTITION BY event_date_parsed
CLUSTER BY entity_id_str, event_date_parsed
AS
WITH parsed_locations AS (
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
    metadata.last_updated as metadata_last_updated,

    -- Parse location from locations_export field
    -- Format: "Country, Town/City, GB" or "Country, Town/City, GB | Country, Town2, GB"
    -- Extract all three components from the first location (before the first |)

    -- Extract Country (first element)
    TRIM(
      SPLIT(
        SPLIT(metadata.locations, '|')[SAFE_OFFSET(0)],  -- Get first location before |
        ','
      )[SAFE_OFFSET(0)]  -- Get first element (country)
    ) as location_country_export,

    -- Extract Town/City (second element)
    TRIM(
      SPLIT(
        SPLIT(metadata.locations, '|')[SAFE_OFFSET(0)],  -- Get first location before |
        ','
      )[SAFE_OFFSET(1)]  -- Get second element (town/city)
    ) as location_town_export,

    -- Extract Geographic Area code (third element, usually GB)
    TRIM(
      SPLIT(
        SPLIT(metadata.locations, '|')[SAFE_OFFSET(0)],  -- Get first location before |
        ','
      )[SAFE_OFFSET(2)]  -- Get third element (GB)
    ) as location_geo_area_export

  FROM `site-monitoring-421401.job_data_export.job_performance_details_combined` AS events
  LEFT JOIN `site-monitoring-421401.job_data_export.job_metadata` AS metadata
    ON CAST(events.entity_id AS STRING) = metadata.entity_id
)

SELECT
  pl.*,

  -- Add region lookup from location_lookup table by matching town/city
  loc.county as location_county_matched,
  loc.region as location_region_matched

FROM parsed_locations pl
LEFT JOIN `site-monitoring-421401.job_data_export.location_lookup` AS loc
  ON UPPER(TRIM(pl.location_town_export)) = UPPER(TRIM(loc.town_city));

-- Step 2: Verify the enriched table
SELECT
  COUNT(*) as total_rows,
  MIN(event_date_parsed) as min_date,
  MAX(event_date_parsed) as max_date,
  COUNT(DISTINCT entity_id_str) as unique_entities,
  COUNT(DISTINCT CASE WHEN title_export IS NOT NULL THEN entity_id_str END) as entities_with_metadata,
  COUNT(DISTINCT CASE WHEN location_region_matched IS NOT NULL THEN entity_id_str END) as entities_with_region,
  ROUND(COUNT(DISTINCT CASE WHEN title_export IS NOT NULL THEN entity_id_str END) * 100.0 / COUNT(DISTINCT entity_id_str), 2) as metadata_match_rate,
  ROUND(COUNT(DISTINCT CASE WHEN location_region_matched IS NOT NULL THEN entity_id_str END) * 100.0 / COUNT(DISTINCT entity_id_str), 2) as region_match_rate
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`;

-- Step 3: Test query performance and location parsing
SELECT
  entity_id_str,
  event_date_parsed,
  event_name,
  title_export,
  locations_export,
  location_country_export,
  location_town_export,
  location_geo_area_export,
  location_county_matched,
  location_region_matched,
  workflow_state
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_date_parsed >= '2024-12-01'
LIMIT 20;

-- Step 4: Check region distribution in data
SELECT
  location_region_matched,
  COUNT(DISTINCT entity_id_str) as unique_jobs,
  COUNT(*) as total_events
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_date_parsed >= '2024-12-01'
  AND location_region_matched IS NOT NULL
GROUP BY location_region_matched
ORDER BY total_events DESC;

-- Step 5: Check location parsing success rate
SELECT
  'Total jobs' as metric,
  COUNT(DISTINCT entity_id_str) as count
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_date_parsed >= '2024-12-01'

UNION ALL

SELECT
  'Jobs with locations_export' as metric,
  COUNT(DISTINCT entity_id_str) as count
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_date_parsed >= '2024-12-01'
  AND locations_export IS NOT NULL

UNION ALL

SELECT
  'Jobs with parsed town/city' as metric,
  COUNT(DISTINCT entity_id_str) as count
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_date_parsed >= '2024-12-01'
  AND location_town_export IS NOT NULL

UNION ALL

SELECT
  'Jobs with region matched' as metric,
  COUNT(DISTINCT entity_id_str) as count
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_date_parsed >= '2024-12-01'
  AND location_region_matched IS NOT NULL;

-- Once verified, you can set up a scheduled query to refresh this table daily
-- Go to: https://console.cloud.google.com/bigquery/scheduled-queries
-- Use the CREATE OR REPLACE statement (Step 1 only) and schedule it for daily refresh
