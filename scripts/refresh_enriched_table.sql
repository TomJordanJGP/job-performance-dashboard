-- Refresh the enriched table after the combined table has been updated.
-- Joins GA4 events with job_metadata. GA4 is the master for overlapping fields;
-- metadata fills in where GA4 has (none) or blank. Metadata-only fields added as columns.
-- For importer_ID = -1, backfill from feed_jobs_latest if the vacancy matches.
-- Location regions joined from vacancy_locations (exploded table) — concatenated for display.
-- Region names normalised via region_canonical lookup (London -> Greater London, etc.).
--
-- Metadata-only vacancies (no GA4 events) are included via UNION ALL with
-- event_name = 'metadata_only' so they appear in vacancy-level analysis
-- (salary benchmarking, field completeness) even without traffic data.
--
-- Schedule this in BigQuery Console AFTER the incremental sync runs:
--   https://console.cloud.google.com/bigquery/scheduled-queries?project=site-monitoring-421401
--   Frequency: Daily (e.g. 07:00 UTC — 1 hour after the sync)
--   Processing location: EU

CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.job_performance_enriched`
PARTITION BY event_date_parsed
CLUSTER BY entity_id_str, event_date_parsed
AS

-- Part 1: GA4 events enriched with metadata (existing logic)
SELECT
  -- IDs
  CAST(events.entity_id AS STRING) as entity_id_str,
  PARSE_DATE('%Y%m%d', events.event_date) as event_date_parsed,
  metadata.external_id,

  -- Event fields (GA4 only)
  events.event_name,
  events.entity_type,
  events.upgrades,
  events.campaign,
  events.medium,
  events.source,

  -- Importer: ID + mapped name (backfill from feed if importer_ID = -1)
  events.importer_ID,
  CASE
    WHEN events.importer_ID = 1 THEN 'Scrape'
    WHEN events.importer_ID = 2 THEN 'ATS feed'
    WHEN events.importer_ID = 5 THEN 'Civil Service'
    WHEN events.importer_ID = 6 THEN 'Backfill'
    WHEN events.importer_ID = -1 AND feed.feed_name IS NOT NULL THEN feed.feed_name
    ELSE 'Unknown'
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
  metadata.salary_free_text,
  metadata.salary_exact,
  metadata.salary_unit,
  metadata.last_updated as metadata_last_updated,

  -- Location regions: HQ is primary, vacancy_locations is fallback
  -- Normalised via region_canonical to ensure consistent naming
  COALESCE(
    rc_all.canonical_region,
    COALESCE(metadata.hq_region, vloc.uk_regions_all)
  ) as uk_regions_all,
  COALESCE(
    rc_primary.canonical_region,
    COALESCE(metadata.hq_region, vloc.primary_uk_region)
  ) as primary_uk_region,
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
  ON CAST(events.entity_id AS STRING) = vloc.entity_id
-- Normalise uk_regions_all via canonical lookup
LEFT JOIN `site-monitoring-421401.job_data_export.region_canonical` AS rc_all
  ON LOWER(COALESCE(metadata.hq_region, vloc.uk_regions_all)) = rc_all.variant
-- Normalise primary_uk_region via canonical lookup
LEFT JOIN `site-monitoring-421401.job_data_export.region_canonical` AS rc_primary
  ON LOWER(COALESCE(metadata.hq_region, vloc.primary_uk_region)) = rc_primary.variant

UNION ALL

-- Part 2: Metadata-only vacancies (no GA4 events)
-- These vacancies exist in job_metadata but have never received a job_visit
-- or job_apply_start event. They are included for salary benchmarking,
-- field completeness, and vacancy-level analysis.
SELECT
  m.entity_id as entity_id_str,
  DATE(m.publishing_date) as event_date_parsed,
  m.external_id,

  -- Synthetic event marker — filtered out of click/apply counts,
  -- included in vacancy-level aggregations
  'metadata_only' as event_name,
  CAST(NULL AS STRING) as entity_type,
  CAST(NULL AS STRING) as upgrades,
  CAST(NULL AS STRING) as campaign,
  CAST(NULL AS STRING) as medium,
  CAST(NULL AS STRING) as source,

  -- No importer_ID from GA4; infer from feed if possible
  CAST(NULL AS INT64) as importer_ID,
  COALESCE(feed_m.feed_name, 'Unknown') as importer_name,

  -- All fields from metadata only
  m.title,
  m.organization_profile_name as organization_name,
  m.organization_id,
  m.occupational_fields,
  m.employment_type,
  m.min_salary,
  m.max_salary,
  m.currency_code,

  m.workflow_state,
  m.category,
  m.contract_type,
  m.employer_type,
  m.publishing_date,
  m.expiration_date,
  m.original_publishing_date,
  m.salary_free_text,
  m.salary_exact,
  m.salary_unit,
  m.last_updated as metadata_last_updated,

  -- Location regions (same logic as Part 1)
  COALESCE(
    rc_all_m.canonical_region,
    COALESCE(m.hq_region, vloc_m.uk_regions_all)
  ) as uk_regions_all,
  COALESCE(
    rc_primary_m.canonical_region,
    COALESCE(m.hq_region, vloc_m.primary_uk_region)
  ) as primary_uk_region,
  m.hq_region,
  m.hq_county

FROM `site-monitoring-421401.job_data_export.job_metadata` AS m
-- Exclude vacancies that already have GA4 events (covered by Part 1)
LEFT JOIN (
  SELECT DISTINCT CAST(entity_id AS STRING) AS entity_id_str
  FROM `site-monitoring-421401.job_data_export.job_performance_details_combined`
) AS has_events
  ON m.entity_id = has_events.entity_id_str
LEFT JOIN `site-monitoring-421401.job_data_export.feed_jobs_latest` AS feed_m
  ON m.external_id = feed_m.feed_id
LEFT JOIN (
  SELECT entity_id,
         STRING_AGG(DISTINCT uk_region, ' | ' ORDER BY uk_region) as uk_regions_all,
         ANY_VALUE(uk_region) as primary_uk_region
  FROM `site-monitoring-421401.job_data_export.vacancy_locations`
  WHERE uk_region IS NOT NULL AND TRIM(uk_region) != ''
  GROUP BY entity_id
) AS vloc_m
  ON m.entity_id = vloc_m.entity_id
LEFT JOIN `site-monitoring-421401.job_data_export.region_canonical` AS rc_all_m
  ON LOWER(COALESCE(m.hq_region, vloc_m.uk_regions_all)) = rc_all_m.variant
LEFT JOIN `site-monitoring-421401.job_data_export.region_canonical` AS rc_primary_m
  ON LOWER(COALESCE(m.hq_region, vloc_m.primary_uk_region)) = rc_primary_m.variant
WHERE has_events.entity_id_str IS NULL;
