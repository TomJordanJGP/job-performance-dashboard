-- Pre-aggregated tables for fast dashboard loading
-- Reduces ~570K raw event rows (90 days) down to ~20K vacancy rows + ~90 daily rows
-- Run after refresh_enriched_table.sql
--
-- Schedule in BigQuery Console:
--   https://console.cloud.google.com/bigquery/scheduled-queries?project=site-monitoring-421401
--   Frequency: Daily (e.g. 08:00 UTC — after enriched table refresh)
--   Processing location: EU

-- Table 1: Per-vacancy summary (one row per vacancy)
-- Used for: metric cards, importer/region/occupation charts, vacancy table, benchmarks
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.dashboard_vacancy_summary`
AS
SELECT
  entity_id_str,

  -- Date range this vacancy was seen
  MIN(event_date_parsed) as first_event_date,
  MAX(event_date_parsed) as last_event_date,

  -- Event counts
  COUNTIF(event_name = 'job_visit') as clicks,
  COUNTIF(event_name = 'job_apply_start') as applies,

  -- Dimensions (take first non-null value per vacancy)
  ANY_VALUE(title) as title,
  ANY_VALUE(organization_name) as organization_name,
  ANY_VALUE(uk_regions_all) as uk_regions,
  ANY_VALUE(primary_uk_region) as primary_uk_region,
  ANY_VALUE(occupational_fields) as occupational_fields,
  ANY_VALUE(importer_ID) as importer_ID,
  ANY_VALUE(importer_name) as importer_name,
  ANY_VALUE(workflow_state) as workflow_state,
  ANY_VALUE(upgrades) as upgrades,
  ANY_VALUE(publishing_date) as start_date,
  ANY_VALUE(expiration_date) as end_date,
  ANY_VALUE(category) as category,
  ANY_VALUE(contract_type) as contract_type,
  ANY_VALUE(employment_type) as employment_type

FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_name IN ('job_visit', 'job_apply_start')
GROUP BY entity_id_str;


-- Table 2: Daily totals (one row per day)
-- Used for: trend line charts. Lightweight — ~365 rows per year.
-- Filtered trends are computed in the app from vacancy summary.
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.dashboard_daily_totals`
PARTITION BY event_date
AS
SELECT
  event_date_parsed as event_date,
  COUNTIF(event_name = 'job_visit') as clicks,
  COUNTIF(event_name = 'job_apply_start') as applies,
  COUNT(DISTINCT entity_id_str) as active_vacancies
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_name IN ('job_visit', 'job_apply_start')
GROUP BY event_date_parsed;


-- Table 3: Per-vacancy media source breakdown (one row per vacancy + source combo)
-- Used for: Client Report tab — media performance section
-- Shows which traffic sources (organic, PPC, email, etc.) drive views and applies
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.dashboard_media_summary`
AS
SELECT
  entity_id_str,
  importer_ID,
  ANY_VALUE(importer_name) as importer_name,
  source,
  medium,
  campaign,
  COUNTIF(event_name = 'job_visit') as clicks,
  COUNTIF(event_name = 'job_apply_start') as applies
FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
WHERE event_name IN ('job_visit', 'job_apply_start')
GROUP BY entity_id_str, importer_ID, source, medium, campaign;
