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
-- Includes metadata-only vacancies (no GA4 events) for salary/field analysis
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.dashboard_vacancy_summary`
AS
WITH enriched AS (
  SELECT * FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
  WHERE event_name IN ('job_visit', 'job_apply_start', 'metadata_only')
)
SELECT
  entity_id_str,

  -- Date range this vacancy was seen (metadata-only vacancies use publishing_date)
  MIN(event_date_parsed) as first_event_date,
  MAX(event_date_parsed) as last_event_date,

  -- Event counts (metadata_only rows contribute 0 to both)
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
  ANY_VALUE(employment_type) as employment_type,

  -- Salary fields
  ANY_VALUE(min_salary) as min_salary,
  ANY_VALUE(max_salary) as max_salary,
  ANY_VALUE(currency_code) as currency_code,
  ANY_VALUE(salary_free_text) as salary_free_text,
  ANY_VALUE(salary_exact) as salary_exact,
  ANY_VALUE(salary_unit) as salary_unit

FROM enriched
GROUP BY entity_id_str;


-- Table 2: Daily totals (one row per day)
-- Used for: trend line charts. Lightweight — ~365 rows per year.
-- active_vacancies = vacancies live on the site that day (published and not yet expired),
-- derived from the vacancy summary's start_date/end_date rather than GA4 events.
-- Clicks/applies still come from GA4 events only.
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.dashboard_daily_totals`
PARTITION BY event_date
AS
WITH
-- Clicks and applies from GA4 events per day
daily_events AS (
  SELECT
    event_date_parsed AS event_date,
    COUNTIF(event_name = 'job_visit') AS clicks,
    COUNTIF(event_name = 'job_apply_start') AS applies
  FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
  WHERE event_name IN ('job_visit', 'job_apply_start')
  GROUP BY event_date_parsed
),
-- Date spine: one row for every day from earliest event to today
date_spine AS (
  SELECT d AS event_date
  FROM UNNEST(GENERATE_DATE_ARRAY(
    (SELECT MIN(event_date) FROM daily_events),
    CURRENT_DATE()
  )) AS d
),
-- Count vacancies that were live on each day (published <= day <= expired)
daily_active AS (
  SELECT
    ds.event_date,
    COUNT(DISTINCT vs.entity_id_str) AS active_vacancies
  FROM date_spine ds
  LEFT JOIN `site-monitoring-421401.job_data_export.dashboard_vacancy_summary` vs
    ON ds.event_date >= DATE(vs.start_date)
    AND (ds.event_date <= DATE(vs.end_date) OR vs.end_date IS NULL)
  GROUP BY ds.event_date
)
SELECT
  da.event_date,
  COALESCE(de.clicks, 0) AS clicks,
  COALESCE(de.applies, 0) AS applies,
  da.active_vacancies
FROM daily_active da
LEFT JOIN daily_events de
  ON da.event_date = de.event_date;


-- Table 3: Per-vacancy media source breakdown (one row per vacancy + source combo)
-- Used for: Client Report tab — media performance section
-- Shows which traffic sources (organic, PPC, email, etc.) drive views and applies
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.dashboard_media_summary`
AS
WITH enriched AS (
  SELECT * FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
  WHERE event_name IN ('job_visit', 'job_apply_start')
)
SELECT
  entity_id_str,
  importer_ID,
  ANY_VALUE(importer_name) as importer_name,
  source,
  medium,
  campaign,
  COUNTIF(event_name = 'job_visit') as clicks,
  COUNTIF(event_name = 'job_apply_start') as applies
FROM enriched
GROUP BY entity_id_str, importer_ID, source, medium, campaign;
