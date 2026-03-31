-- One-time fix: Backfill blank country_region and uk_region in vacancy_locations
-- For multi-location vacancies where town_city is populated but country_region is blank
-- (e.g., ", Stratford-upon-Avon, GB")
--
-- Run manually in BigQuery Console:
--   https://console.cloud.google.com/bigquery?project=site-monitoring-421401

-- Step 1: Check how many rows have blank country_region but populated town_city
SELECT
  COUNT(*) as blank_country_region_with_town,
  COUNT(DISTINCT entity_id) as affected_vacancies
FROM `site-monitoring-421401.job_data_export.vacancy_locations`
WHERE (country_region IS NULL OR TRIM(country_region) = '')
  AND town_city IS NOT NULL AND TRIM(town_city) != '';

-- Step 2: Backfill from location_lookup
UPDATE `site-monitoring-421401.job_data_export.vacancy_locations` vl
SET vl.country_region = loc.county,
    vl.uk_region = loc.region
FROM `site-monitoring-421401.job_data_export.location_lookup` loc
WHERE (vl.country_region IS NULL OR TRIM(vl.country_region) = '')
  AND vl.town_city IS NOT NULL AND TRIM(vl.town_city) != ''
  AND UPPER(TRIM(vl.town_city)) = UPPER(TRIM(loc.town_city));

-- Step 3: Verify remaining NULLs
SELECT
  COUNT(*) as still_blank_after_fix,
  COUNT(DISTINCT entity_id) as affected_vacancies
FROM `site-monitoring-421401.job_data_export.vacancy_locations`
WHERE (country_region IS NULL OR TRIM(country_region) = '')
  AND town_city IS NOT NULL AND TRIM(town_city) != '';

-- Step 4: List unmatched towns for manual review
SELECT
  town_city,
  COUNT(DISTINCT entity_id) as vacancy_count
FROM `site-monitoring-421401.job_data_export.vacancy_locations`
WHERE (uk_region IS NULL OR TRIM(uk_region) = '')
  AND town_city IS NOT NULL AND TRIM(town_city) != ''
GROUP BY town_city
ORDER BY vacancy_count DESC
LIMIT 50;
