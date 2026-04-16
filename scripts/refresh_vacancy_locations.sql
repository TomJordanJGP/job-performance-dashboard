-- Refresh vacancy_locations by exploding job_metadata.locations into one row per location.
-- Then backfill uk_region from location_lookup table.
-- Run before refresh_enriched_table.sql (which joins on vacancy_locations).
--
-- locations field format: "State, City, CountryCode" pipe-delimited for multi-location
-- Example: "England, London, GB" or "England, Manchester, GB | England, Liverpool, GB"
-- Also handles plain-text locations (e.g. just "London") by using the full string as town_city.

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
    -- Parse "State, City, CountryCode" format.
    -- Plain-text locations (no commas) use the full string as town_city.
    CASE
      WHEN ARRAY_LENGTH(SPLIT(raw_location, ',')) >= 2
      THEN TRIM(SPLIT(raw_location, ',')[SAFE_OFFSET(1)])
      ELSE TRIM(raw_location)
    END as town_city,
    CASE
      WHEN ARRAY_LENGTH(SPLIT(raw_location, ',')) >= 2
      THEN TRIM(SPLIT(raw_location, ',')[SAFE_OFFSET(0)])
      ELSE NULL
    END as country_region
  FROM exploded
  WHERE TRIM(raw_location) != ''
)
SELECT
  p.entity_id,
  p.raw_location,
  p.town_city,
  p.country_region,
  COALESCE(
    rc_raw.canonical_region, loc_raw.region,
    rc_legacy.canonical_region, loc_legacy.region
  ) as uk_region
FROM parsed p
-- Primary: match on full raw_location string
LEFT JOIN `site-monitoring-421401.job_data_export.location_lookup` loc_raw
  ON UPPER(TRIM(p.raw_location)) = UPPER(TRIM(loc_raw.raw_location))
LEFT JOIN `site-monitoring-421401.job_data_export.region_canonical` rc_raw
  ON LOWER(COALESCE(loc_raw.region, '')) = rc_raw.variant
-- Fallback: match on town_city for legacy lookup rows without raw_location
LEFT JOIN `site-monitoring-421401.job_data_export.location_lookup` loc_legacy
  ON loc_raw.raw_location IS NULL
  AND UPPER(TRIM(p.town_city)) = UPPER(TRIM(loc_legacy.town_city))
LEFT JOIN `site-monitoring-421401.job_data_export.region_canonical` rc_legacy
  ON LOWER(COALESCE(loc_legacy.region, '')) = rc_legacy.variant
WHERE p.town_city IS NOT NULL
  AND TRIM(p.town_city) != ''
  AND LOWER(TRIM(p.town_city)) NOT IN ('national', 'various', 'remote', 'flexible', 'uk', 'united kingdom', 'tbc', 'n/a');
