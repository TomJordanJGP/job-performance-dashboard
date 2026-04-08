-- Refresh vacancy_locations by exploding job_metadata.locations into one row per location.
-- Then backfill uk_region from location_lookup table.
-- Run before refresh_enriched_table.sql (which joins on vacancy_locations).
--
-- locations field format: "State, City, CountryCode" pipe-delimited for multi-location
-- Example: "England, London, GB" or "England, Manchester, GB | England, Liverpool, GB"

CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.vacancy_locations` AS

WITH exploded AS (
  SELECT
    entity_id,
    TRIM(loc) as raw_location
  FROM `site-monitoring-421401.job_data_export.job_metadata`,
  UNNEST(SPLIT(locations, '|')) AS loc
  WHERE locations IS NOT NULL AND TRIM(locations) != ''
),
parsed AS (
  SELECT
    entity_id,
    raw_location,
    -- Parse "State, City, CountryCode" format
    CASE
      WHEN ARRAY_LENGTH(SPLIT(raw_location, ',')) >= 2
      THEN TRIM(SPLIT(raw_location, ',')[SAFE_OFFSET(1)])
      ELSE NULL
    END as town_city,
    CASE
      WHEN ARRAY_LENGTH(SPLIT(raw_location, ',')) >= 1
      THEN TRIM(SPLIT(raw_location, ',')[SAFE_OFFSET(0)])
      ELSE NULL
    END as country_region
  FROM exploded
  WHERE TRIM(raw_location) != ''
)
SELECT
  p.entity_id,
  p.town_city,
  p.country_region,
  COALESCE(rc.canonical_region, loc.region) as uk_region
FROM parsed p
LEFT JOIN `site-monitoring-421401.job_data_export.location_lookup` loc
  ON UPPER(TRIM(p.town_city)) = UPPER(TRIM(loc.town_city))
LEFT JOIN `site-monitoring-421401.job_data_export.region_canonical` rc
  ON LOWER(COALESCE(loc.region, '')) = rc.variant
WHERE p.town_city IS NOT NULL AND TRIM(p.town_city) != '';
