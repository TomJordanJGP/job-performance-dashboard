-- Refresh the enriched table after the combined table has been updated.
-- Joins GA4 events with job_metadata. GA4 is the master for overlapping fields;
-- metadata fills in where GA4 has (none) or blank. Metadata-only fields added as columns.
-- For importer_ID = -1, backfill from feed_jobs_latest if the vacancy matches.
-- Location regions joined from vacancy_locations (exploded table) — concatenated for display.
--
-- Schedule this in BigQuery Console AFTER the incremental sync runs:
--   https://console.cloud.google.com/bigquery/scheduled-queries?project=site-monitoring-421401
--   Frequency: Daily (e.g. 07:00 UTC — 1 hour after the sync)
--   Processing location: EU

CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.job_performance_enriched`
PARTITION BY event_date_parsed
CLUSTER BY entity_id_str, event_date_parsed
AS
SELECT
  -- IDs
  CAST(events.entity_id AS STRING) as entity_id_str,
  PARSE_DATE('%Y%m%d', events.event_date) as event_date_parsed,
  events.entity_id as entity_id_original,
  metadata.external_id,

  -- Event fields (GA4 only)
  events.event_name,
  events.event_date as event_date_original,
  events.hour_of_day,
  events.entity_type,
  events.Events,
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
  events.owner_id,
  events.regions as regions_ga4,

  -- Importer: ID + mapped name (backfill from feed if importer_ID = -1)
  events.importer_ID,
  CASE
    WHEN events.importer_ID = 1 THEN 'Scrape'
    WHEN events.importer_ID = 2 THEN 'ATS feed'
    WHEN events.importer_ID = 5 THEN 'Civil Service'
    WHEN events.importer_ID = 6 THEN 'Backfill'
    WHEN events.importer_ID = -1 AND feed.feed_name IS NOT NULL THEN feed.feed_name
    ELSE 'Unknown/Other'
  END as importer_name,

  -- Overlapping fields: GA4 is master, metadata fills blanks
  -- Title
  IF(events.title IS NOT NULL AND TRIM(events.title) NOT IN ('', '(none)'),
    events.title, metadata.title
  ) as title,

  -- Organisation name
  IF(events.organization_name IS NOT NULL AND TRIM(events.organization_name) NOT IN ('', '(none)'),
    events.organization_name, metadata.organization_profile_name
  ) as organization_name,

  -- Organisation ID
  IF(events.organization_id IS NOT NULL AND events.organization_id NOT IN (0, -1),
    CAST(events.organization_id AS STRING), metadata.organization_id
  ) as organization_id,

  -- Occupations / occupational fields
  IF(events.occupations IS NOT NULL AND TRIM(events.occupations) NOT IN ('', '(none)'),
    events.occupations, metadata.occupational_fields
  ) as occupational_fields,

  -- Employment type
  IF(events.employment_types IS NOT NULL AND TRIM(events.employment_types) NOT IN ('', '(none)'),
    events.employment_types, metadata.employment_type
  ) as employment_type,

  -- Salary low / min
  IF(events.salary_low IS NOT NULL AND events.salary_low != 0,
    CAST(events.salary_low AS FLOAT64), metadata.min_salary
  ) as min_salary,

  -- Salary high / max
  IF(events.salary_high IS NOT NULL AND events.salary_high != 0,
    CAST(events.salary_high AS FLOAT64), metadata.max_salary
  ) as max_salary,

  -- Currency
  IF(events.salary_currency IS NOT NULL AND TRIM(events.salary_currency) NOT IN ('', '(none)'),
    events.salary_currency, metadata.currency_code
  ) as currency_code,

  -- Metadata-only fields (no GA4 equivalent)
  metadata.workflow_state,
  metadata.category,
  metadata.contract_type,
  metadata.employer_type,
  metadata.publishing_date,
  metadata.expiration_date,
  metadata.original_publishing_date,
  metadata.locations,
  metadata.salary_free_text,
  metadata.salary_exact,
  metadata.salary_unit,
  metadata.last_updated as metadata_last_updated,

  -- Location regions: HQ is primary (single-location), vacancy_locations is fallback (multi-location)
  COALESCE(metadata.hq_region, vloc.uk_regions_all) as uk_regions_all,
  COALESCE(metadata.hq_region, vloc.primary_uk_region) as primary_uk_region,
  COALESCE(metadata.hq_county, vloc.primary_town_city) as primary_town_city,
  metadata.hq_region,
  metadata.hq_county

FROM `site-monitoring-421401.job_data_export.job_performance_details_combined` AS events
LEFT JOIN `site-monitoring-421401.job_data_export.job_metadata` AS metadata
  ON CAST(events.entity_id AS STRING) = metadata.entity_id
LEFT JOIN `site-monitoring-421401.job_data_export.feed_jobs_latest` AS feed
  ON metadata.external_id = feed.feed_id
LEFT JOIN (
  SELECT entity_id,
         STRING_AGG(DISTINCT uk_region, ' | ' ORDER BY uk_region) as uk_regions_all,
         ANY_VALUE(uk_region) as primary_uk_region,
         ANY_VALUE(town_city) as primary_town_city
  FROM `site-monitoring-421401.job_data_export.vacancy_locations`
  WHERE uk_region IS NOT NULL AND TRIM(uk_region) != ''
  GROUP BY entity_id
) AS vloc
  ON CAST(events.entity_id AS STRING) = vloc.entity_id;
