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

  -- External ID (for cross-referencing with feeds / review queues)
  ANY_VALUE(external_id) as external_id,

  -- Salary fields
  ANY_VALUE(min_salary) as min_salary,
  ANY_VALUE(max_salary) as max_salary,
  ANY_VALUE(currency_code) as currency_code,
  ANY_VALUE(salary_free_text) as salary_free_text,
  ANY_VALUE(salary_exact) as salary_exact,
  ANY_VALUE(salary_unit) as salary_unit,

  -- Sites this vacancy appeared on (pipe-separated, e.g. 'Jobs Go Public | LG Jobs')
  -- NULL for metadata-only vacancies with no GA4 events
  STRING_AGG(DISTINCT site, ' | ' ORDER BY site) as sites

FROM enriched
GROUP BY entity_id_str;


-- Table 1b: Per-vacancy per-region summary (one row per vacancy per region)
-- Used for: regional breakdowns in dashboard charts, benchmark tables, salary analysis.
-- A vacancy in 3 regions produces 3 rows, each carrying the full click/apply counts
-- (GA4 cannot attribute events to a specific location within a multi-location vacancy).
-- Regional totals will intentionally exceed overall vacancy/click totals.
-- raw_location + town_city preserved so individual addresses are visible post-explosion.
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.dashboard_vacancy_region_summary`
AS
SELECT
  vs.entity_id_str,
  vs.external_id,
  COALESCE(vl.uk_region, vs.primary_uk_region, 'Unknown') AS uk_region,
  vl.raw_location,
  vl.town_city,
  vs.first_event_date,
  vs.last_event_date,
  vs.clicks,
  vs.applies,
  vs.title,
  vs.organization_name,
  vs.occupational_fields,
  vs.importer_ID,
  vs.importer_name,
  vs.workflow_state,
  vs.upgrades,
  vs.start_date,
  vs.end_date,
  vs.category,
  vs.contract_type,
  vs.employment_type,
  vs.min_salary,
  vs.max_salary,
  vs.currency_code,
  vs.salary_free_text,
  vs.salary_exact,
  vs.salary_unit,
  vs.sites
FROM `site-monitoring-421401.job_data_export.dashboard_vacancy_summary` vs
LEFT JOIN `site-monitoring-421401.job_data_export.vacancy_locations` vl
  ON vs.entity_id_str = vl.entity_id
  AND vl.uk_region IS NOT NULL
  AND TRIM(vl.uk_region) != '';


-- Table 2: Daily totals (one row per day)
-- Used for: trend line charts (dashboard) and SEO pulse (weekly rollup).
-- Combines GA4 engagement (clicks/applies), GSC search visibility (impressions,
-- avg position, rich results), and live vacancy counts from metadata dates.
-- GSC data comes from the jobsgopublic project's Search Console BigQuery exports.
-- Note: GSC data has a 2-3 day lag — recent dates will show 0 for GSC metrics.
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.dashboard_daily_totals`
PARTITION BY event_date
AS
WITH
-- GA4 clicks and applies per day, split by site
daily_events AS (
  SELECT
    event_date_parsed AS event_date,
    COUNTIF(event_name = 'job_visit') AS clicks,
    COUNTIF(event_name = 'job_visit' AND site = 'Jobs Go Public') AS clicks_jgp,
    COUNTIF(event_name = 'job_visit' AND site = 'LG Jobs') AS clicks_lg,
    COUNTIF(event_name = 'job_apply_start') AS applies,
    COUNTIF(event_name = 'job_apply_start' AND site = 'Jobs Go Public') AS applies_jgp,
    COUNTIF(event_name = 'job_apply_start' AND site = 'LG Jobs') AS applies_lg
  FROM `site-monitoring-421401.job_data_export.job_performance_enriched`
  WHERE event_name IN ('job_visit', 'job_apply_start')
  GROUP BY event_date_parsed
),
-- GSC site-level metrics per day (impressions, clicks, position — total + GB only)
gsc_site_daily AS (
  SELECT
    COALESCE(jgp.data_date, lg.data_date) AS event_date,
    COALESCE(jgp.impressions, 0) AS impressions_jgp,
    COALESCE(lg.impressions, 0) AS impressions_lg,
    COALESCE(jgp.gb_impressions, 0) AS gb_impressions_jgp,
    COALESCE(lg.gb_impressions, 0) AS gb_impressions_lg,
    COALESCE(jgp.clicks, 0) AS gsc_clicks_jgp,
    COALESCE(lg.clicks, 0) AS gsc_clicks_lg,
    COALESCE(jgp.gb_clicks, 0) AS gb_gsc_clicks_jgp,
    COALESCE(lg.gb_clicks, 0) AS gb_gsc_clicks_lg,
    COALESCE(jgp.sum_pos, 0) AS sum_position_jgp,
    COALESCE(lg.sum_pos, 0) AS sum_position_lg
  FROM (
    SELECT
      data_date,
      SUM(impressions) AS impressions,
      SUM(IF(country = 'gbr', impressions, 0)) AS gb_impressions,
      SUM(clicks) AS clicks,
      SUM(IF(country = 'gbr', clicks, 0)) AS gb_clicks,
      SUM(sum_top_position) AS sum_pos
    FROM `jobsgopublic.searchconsole_jobsgopublic.searchdata_site_impression`
    GROUP BY data_date
  ) jgp
  FULL OUTER JOIN (
    SELECT
      data_date,
      SUM(impressions) AS impressions,
      SUM(IF(country = 'gbr', impressions, 0)) AS gb_impressions,
      SUM(clicks) AS clicks,
      SUM(IF(country = 'gbr', clicks, 0)) AS gb_clicks,
      SUM(sum_top_position) AS sum_pos
    FROM `jobsgopublic.searchconsole_lgjobs.searchdata_site_impression`
    GROUP BY data_date
  ) lg ON jgp.data_date = lg.data_date
),
-- GSC URL-level rich result counts per day (job listing + job detail appearances)
gsc_rich_daily AS (
  SELECT
    COALESCE(jgp.data_date, lg.data_date) AS event_date,
    COALESCE(jgp.job_listing_rich, 0) AS job_listing_rich_jgp,
    COALESCE(lg.job_listing_rich, 0) AS job_listing_rich_lg,
    COALESCE(jgp.job_detail_rich, 0) AS job_detail_rich_jgp,
    COALESCE(lg.job_detail_rich, 0) AS job_detail_rich_lg
  FROM (
    SELECT
      data_date,
      SUM(IF(is_job_listing, impressions, 0)) AS job_listing_rich,
      SUM(IF(is_job_details, impressions, 0)) AS job_detail_rich
    FROM `jobsgopublic.searchconsole_jobsgopublic.searchdata_url_impression`
    GROUP BY data_date
  ) jgp
  FULL OUTER JOIN (
    SELECT
      data_date,
      SUM(IF(is_job_listing, impressions, 0)) AS job_listing_rich,
      SUM(IF(is_job_details, impressions, 0)) AS job_detail_rich
    FROM `jobsgopublic.searchconsole_lgjobs.searchdata_url_impression`
    GROUP BY data_date
  ) lg ON jgp.data_date = lg.data_date
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
-- Also count per-site using the sites field (a vacancy on both sites counts toward both)
daily_active AS (
  SELECT
    ds.event_date,
    COUNT(DISTINCT vs.entity_id_str) AS active_vacancies,
    COUNT(DISTINCT IF(vs.sites LIKE '%Jobs Go Public%', vs.entity_id_str, NULL)) AS active_jgp,
    COUNT(DISTINCT IF(vs.sites LIKE '%LG Jobs%', vs.entity_id_str, NULL)) AS active_lg
  FROM date_spine ds
  LEFT JOIN `site-monitoring-421401.job_data_export.dashboard_vacancy_summary` vs
    ON ds.event_date >= DATE(vs.start_date)
    AND (ds.event_date <= DATE(vs.end_date) OR vs.end_date IS NULL)
  GROUP BY ds.event_date
)
SELECT
  da.event_date,
  -- GSC search impressions (total + per site + GB-only)
  COALESCE(gs.impressions_jgp, 0) + COALESCE(gs.impressions_lg, 0) AS impressions,
  COALESCE(gs.impressions_jgp, 0) AS impressions_jgp,
  COALESCE(gs.impressions_lg, 0) AS impressions_lg,
  COALESCE(gs.gb_impressions_jgp, 0) AS gb_impressions_jgp,
  COALESCE(gs.gb_impressions_lg, 0) AS gb_impressions_lg,
  -- GSC search clicks (total + per site + GB-only)
  COALESCE(gs.gsc_clicks_jgp, 0) + COALESCE(gs.gsc_clicks_lg, 0) AS gsc_clicks,
  COALESCE(gs.gsc_clicks_jgp, 0) AS gsc_clicks_jgp,
  COALESCE(gs.gsc_clicks_lg, 0) AS gsc_clicks_lg,
  COALESCE(gs.gb_gsc_clicks_jgp, 0) AS gb_gsc_clicks_jgp,
  COALESCE(gs.gb_gsc_clicks_lg, 0) AS gb_gsc_clicks_lg,
  -- GSC avg position (daily display) + raw sum_position (for weighted weekly rollup)
  ROUND(SAFE_DIVIDE(gs.sum_position_jgp, gs.impressions_jgp), 1) AS avg_position_jgp,
  ROUND(SAFE_DIVIDE(gs.sum_position_lg, gs.impressions_lg), 1) AS avg_position_lg,
  COALESCE(gs.sum_position_jgp, 0) AS sum_position_jgp,
  COALESCE(gs.sum_position_lg, 0) AS sum_position_lg,
  -- GSC rich result impressions
  COALESCE(gr.job_listing_rich_jgp, 0) AS job_listing_rich_jgp,
  COALESCE(gr.job_listing_rich_lg, 0) AS job_listing_rich_lg,
  COALESCE(gr.job_detail_rich_jgp, 0) AS job_detail_rich_jgp,
  COALESCE(gr.job_detail_rich_lg, 0) AS job_detail_rich_lg,
  -- GA4 clicks (job_visit) + applies (job_apply_start)
  COALESCE(de.clicks, 0) AS clicks,
  COALESCE(de.clicks_jgp, 0) AS clicks_jgp,
  COALESCE(de.clicks_lg, 0) AS clicks_lg,
  COALESCE(de.applies, 0) AS applies,
  COALESCE(de.applies_jgp, 0) AS applies_jgp,
  COALESCE(de.applies_lg, 0) AS applies_lg,
  -- Live vacancies (from metadata start_date/end_date)
  da.active_vacancies,
  da.active_jgp,
  da.active_lg
FROM daily_active da
LEFT JOIN daily_events de ON da.event_date = de.event_date
LEFT JOIN gsc_site_daily gs ON da.event_date = gs.event_date
LEFT JOIN gsc_rich_daily gr ON da.event_date = gr.event_date;


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


-- Table 4: Weekly live vacancies (one row per ISO week)
-- Used for: SEO pulse week-over-week comparisons and dashboard weekly view.
-- Aggregated from dashboard_daily_totals so metrics stay consistent.
-- Avg position is a weighted average (sum_position / impressions), not AVG of daily averages.
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.weekly_live_vacancies`
PARTITION BY week_start
AS
SELECT
  DATE_TRUNC(event_date, ISOWEEK) AS week_start,
  -- GSC search impressions
  SUM(impressions) AS impressions,
  SUM(impressions_jgp) AS impressions_jgp,
  SUM(impressions_lg) AS impressions_lg,
  SUM(gb_impressions_jgp) AS gb_impressions_jgp,
  SUM(gb_impressions_lg) AS gb_impressions_lg,
  -- GSC search clicks
  SUM(gsc_clicks) AS gsc_clicks,
  SUM(gsc_clicks_jgp) AS gsc_clicks_jgp,
  SUM(gsc_clicks_lg) AS gsc_clicks_lg,
  SUM(gb_gsc_clicks_jgp) AS gb_gsc_clicks_jgp,
  SUM(gb_gsc_clicks_lg) AS gb_gsc_clicks_lg,
  -- GSC avg position (weighted average across the week)
  ROUND(SAFE_DIVIDE(SUM(sum_position_jgp), SUM(impressions_jgp)), 1) AS avg_position_jgp,
  ROUND(SAFE_DIVIDE(SUM(sum_position_lg), SUM(impressions_lg)), 1) AS avg_position_lg,
  -- GSC rich results
  SUM(job_listing_rich_jgp) AS job_listing_rich_jgp,
  SUM(job_listing_rich_lg) AS job_listing_rich_lg,
  SUM(job_detail_rich_jgp) AS job_detail_rich_jgp,
  SUM(job_detail_rich_lg) AS job_detail_rich_lg,
  -- GA4 clicks + applies
  SUM(clicks) AS clicks,
  SUM(clicks_jgp) AS clicks_jgp,
  SUM(clicks_lg) AS clicks_lg,
  SUM(applies) AS applies,
  SUM(applies_jgp) AS applies_jgp,
  SUM(applies_lg) AS applies_lg,
  -- Live vacancies (daily average across the week)
  CAST(ROUND(AVG(active_vacancies)) AS INT64) AS active_vacancies,
  CAST(ROUND(AVG(active_jgp)) AS INT64) AS active_jgp,
  CAST(ROUND(AVG(active_lg)) AS INT64) AS active_lg,
  COUNT(*) AS days_in_week
FROM `site-monitoring-421401.job_data_export.dashboard_daily_totals`
GROUP BY DATE_TRUNC(event_date, ISOWEEK);


-- Table 5+: SEO Pulse dataset — clean copies for SEO reporting
-- Placed last so all job_data_export tables succeed even if this fails.
CREATE SCHEMA IF NOT EXISTS `site-monitoring-421401.SEO_pulse`
OPTIONS(location = 'EU');

CREATE OR REPLACE TABLE `site-monitoring-421401.SEO_pulse.daily_live_vacancies`
PARTITION BY event_date
AS
SELECT * FROM `site-monitoring-421401.job_data_export.dashboard_daily_totals`;

CREATE OR REPLACE TABLE `site-monitoring-421401.SEO_pulse.weekly_live_vacancies`
PARTITION BY week_start
AS
SELECT * FROM `site-monitoring-421401.job_data_export.weekly_live_vacancies`;
