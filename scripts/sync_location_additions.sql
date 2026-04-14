-- Sync reviewed location additions from Google Sheets into location_lookup.
-- Reads from the "Review" Google Sheet tab, picks up rows marked done=TRUE,
-- and MERGEs them into location_lookup so they resolve on subsequent refreshes.
--
-- Run as part of daily_refresh.py (before refresh_vacancy_locations.sql).
--
-- Sheet columns expected (10):
--   raw_location, town_city, country_region, country_code, vacancy_count,
--   suggested_region, suggested_county, confidence, source, done
--
-- Lookup key is raw_location (the full feed location string after pipe-split).
-- Only rows where done = TRUE and suggested_region is not blank/MALFORMED/Non-UK
-- are synced into location_lookup.

-- Step 1: Create/refresh external table backed by the Google Sheet.
-- Explicit schema avoids auto-detection failures when columns (e.g. done) are empty.
CREATE OR REPLACE EXTERNAL TABLE `site-monitoring-421401.job_data_export.location_review_external` (
  raw_location STRING,
  town_city STRING,
  country_region STRING,
  country_code STRING,
  vacancy_count INT64,
  suggested_region STRING,
  suggested_county STRING,
  confidence STRING,
  source STRING,
  done STRING
)
OPTIONS (
  format = 'GOOGLE_SHEETS',
  uris = ['https://docs.google.com/spreadsheets/d/1YPfZMxK2Rdl91JjAKd60xtjNinDfBe0DHpa5euFwmDc/edit?gid=1663440124#gid=1663440124'],
  skip_leading_rows = 1
);

-- Step 2: MERGE approved rows into location_lookup.
-- Matches on raw_location (full feed location string).
-- Skips Non-UK, MALFORMED, and blank region entries.
MERGE `site-monitoring-421401.job_data_export.location_lookup` AS target
USING (
  SELECT
    UPPER(TRIM(CAST(raw_location AS STRING))) AS raw_location,
    UPPER(TRIM(CAST(town_city AS STRING))) AS town_city,
    'GB' AS country_code,
    CASE
      WHEN TRIM(CAST(country_region AS STRING)) IN ('England', 'Scotland', 'Wales', 'Northern Ireland')
      THEN TRIM(CAST(country_region AS STRING))
      ELSE 'England'  -- default for entries where country_region is a town/region name
    END AS country,
    COALESCE(TRIM(CAST(suggested_county AS STRING)), '') AS county,
    TRIM(CAST(suggested_region AS STRING)) AS region
  FROM `site-monitoring-421401.job_data_export.location_review_external`
  WHERE UPPER(TRIM(CAST(done AS STRING))) = 'TRUE'
    AND TRIM(CAST(suggested_region AS STRING)) IS NOT NULL
    AND TRIM(CAST(suggested_region AS STRING)) != ''
    AND TRIM(CAST(suggested_region AS STRING)) NOT IN ('MALFORMED', 'Non-UK')
) AS source
ON UPPER(TRIM(target.raw_location)) = source.raw_location
WHEN NOT MATCHED THEN
  INSERT (country_code, raw_location, town_city, country, county, region)
  VALUES (source.country_code, source.raw_location, source.town_city, source.country, source.county, source.region);
