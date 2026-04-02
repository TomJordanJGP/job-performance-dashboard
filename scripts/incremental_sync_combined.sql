-- Incremental sync: Re-sync last 5 days from jobsgopublic source to local combined table.
-- Deletes and re-inserts the 5-day window to catch late-arriving rows in the source.
-- Safe to run repeatedly — delete+insert is idempotent for the lookback window.
--
-- Schedule this in BigQuery Console:
--   https://console.cloud.google.com/bigquery/scheduled-queries?project=site-monitoring-421401
--   Frequency: Daily (e.g. 06:00 UTC)
--   Processing location: EU

-- Step 1: Delete last 5 days from destination
DELETE FROM `site-monitoring-421401.job_data_export.job_performance_details_combined`
WHERE event_date >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 5 DAY));

-- Step 2: Re-insert last 5 days (plus any new dates) from source
INSERT INTO `site-monitoring-421401.job_data_export.job_performance_details_combined`
(
  event_name, event_date, hour_of_day, entity_id, entity_type, entity_subtype,
  organization_name, title, application_type, occupations, regions, employment_types,
  importer_ID, current_user_id, user_role, owner_id, organization_id,
  page_referrer, page_location, upgrades, ats_vacancy_number, ats_account_number,
  salary_currency, salary_low, salary_high, device, operating_system, browser,
  campaign, medium, source, Events, site
)
SELECT
  event_name, event_date, hour_of_day, entity_id, entity_type, entity_subtype,
  organization_name, title, application_type, occupations, regions, employment_types,
  importer_ID, current_user_id, user_role, owner_id, organization_id,
  page_referrer, page_location, upgrades, ats_vacancy_number, ats_account_number,
  salary_currency, salary_low, salary_high, device, operating_system, browser,
  campaign, medium, source, Events, site
FROM `jobsgopublic.Datastudio_scheduled_data_combined.Job-performance-detaile_combined` AS src
WHERE src.event_date >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 5 DAY));
