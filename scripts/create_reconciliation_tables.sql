-- Reconciliation tables for tracking ID match quality across sync operations.
-- Run once to create; sync scripts append rows after each run.
--
-- id_reconciliation_log: One row per sync run per source — tracks match rates over time.
-- missing_external_ids: Vacancies in GA4 events with no external_id in job_metadata.

-- Table 1: Match rate log
CREATE TABLE IF NOT EXISTS `site-monitoring-421401.job_data_export.id_reconciliation_log` (
  run_date DATE,
  run_timestamp TIMESTAMP,
  source STRING,
  total_records INT64,
  matched_external_id INT64,
  matched_entity_id INT64,
  unmatched INT64,
  match_rate FLOAT64
);

-- Table 2: Missing external IDs
-- Populated by comparing GA4 entity_ids against job_metadata.
-- Refreshed after each enriched table build.
CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.missing_external_ids` AS
SELECT
  CAST(events.entity_id AS STRING) as entity_id_str,
  ANY_VALUE(
    IF(events.title IS NOT NULL AND TRIM(events.title) NOT IN ('', '(none)'),
      events.title, NULL)
  ) as title,
  ANY_VALUE(
    IF(events.organization_name IS NOT NULL AND TRIM(events.organization_name) NOT IN ('', '(none)'),
      events.organization_name, NULL)
  ) as organization_name,
  ANY_VALUE(
    CASE
      WHEN events.importer_ID = 1 THEN 'Scrape'
      WHEN events.importer_ID = 2 THEN 'ATS feed'
      WHEN events.importer_ID = 5 THEN 'Civil Service'
      WHEN events.importer_ID = 6 THEN 'Backfill'
      ELSE 'Unknown'
    END
  ) as importer_name,
  MIN(PARSE_DATE('%Y%m%d', events.event_date)) as first_seen_date,
  MAX(PARSE_DATE('%Y%m%d', events.event_date)) as last_seen_date,
  COUNT(*) as event_count
FROM `site-monitoring-421401.job_data_export.job_performance_details_combined` AS events
LEFT JOIN `site-monitoring-421401.job_data_export.job_metadata` AS metadata
  ON CAST(events.entity_id AS STRING) = metadata.entity_id
WHERE metadata.entity_id IS NULL
GROUP BY CAST(events.entity_id AS STRING);
