-- Incremental sync: Append new data from jobsgopublic source to local combined table
-- Only inserts rows with event_date > the latest date already in the destination.
-- Safe to run repeatedly — will never create duplicates for the same date.
--
-- Schedule this in BigQuery Console:
--   https://console.cloud.google.com/bigquery/scheduled-queries?project=site-monitoring-421401
--   Frequency: Daily (e.g. 06:00 UTC)
--   Processing location: EU

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
WHERE src.event_date > (
  SELECT COALESCE(MAX(event_date), '00000000')
  FROM `site-monitoring-421401.job_data_export.job_performance_details_combined`
);
