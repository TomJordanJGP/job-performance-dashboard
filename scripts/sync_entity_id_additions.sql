-- Sync reviewed entity_id / Jobiqo-only fields from the "Missing Entity IDs"
-- tab of the review Sheet into job_metadata.
--
-- Counterpart to sync_external_id_additions.sql, keyed the other direction:
--   sync_external_id_additions.sql  — matches on entity_id (or external_id
--                                     fallback); fills Jobiqo metadata onto
--                                     GA4-only vacancies.
--   THIS SCRIPT                     — matches on external_id; fills the
--                                     Jobiqo entity_id onto feed-only rows.
--
-- Sheet layout (10 cols) — see scripts/export_missing_entity_ids_to_sheet.py
-- for the source of truth:
--   external_id, title, organization_profile_name, locations, workflow_state,
--   publishing_date,                                    ← context (read-only)
--   entity_id, employer_type, original_publishing_date, ← Jobiqo-only fills
--   done                                                ← user marker
--
-- Context columns (title, organization_profile_name, locations, workflow_state,
-- publishing_date) are NOT synced — feed is source of truth for these.
--
-- Run as part of daily_refresh.py (after sync_external_id_additions.sql,
-- before refresh_enriched_table.sql).

-- Step 1: Create/refresh external table backed by the Missing Entity IDs tab.
CREATE OR REPLACE EXTERNAL TABLE `site-monitoring-421401.job_data_export.missing_entity_ids_review_external` (
  external_id STRING,
  title STRING,
  organization_profile_name STRING,
  locations STRING,
  workflow_state STRING,
  publishing_date STRING,
  entity_id STRING,
  employer_type STRING,
  original_publishing_date STRING,
  done STRING
)
OPTIONS (
  format = 'GOOGLE_SHEETS',
  uris = ['https://docs.google.com/spreadsheets/d/1YPfZMxK2Rdl91JjAKd60xtjNinDfBe0DHpa5euFwmDc'],
  sheet_range = 'Missing Entity IDs',
  skip_leading_rows = 1
);

-- Step 2: MERGE approved rows into job_metadata.
-- Keyed on external_id — the feed runs first in the pipeline, so the target
-- row already exists with external_id populated and entity_id NULL.
--
-- No WHEN NOT MATCHED branch on purpose: if a Sheet row's external_id doesn't
-- match any job_metadata row, the feed row was unpublished between export and
-- fill — silently skip rather than insert a ghost.
MERGE `site-monitoring-421401.job_data_export.job_metadata` AS target
USING (
  SELECT
    TRIM(CAST(external_id AS STRING)) AS external_id,
    TRIM(CAST(entity_id AS STRING)) AS entity_id,
    TRIM(CAST(employer_type AS STRING)) AS employer_type,
    -- Sheet cells in UK locale display as DD/MM/YYYY HH:MM. SAFE_CAST AS TIMESTAMP
    -- only understands ISO, so try DD/MM patterns first (in Europe/London to handle
    -- BST), then fall back to ISO for cells the export script wrote raw.
    COALESCE(
      SAFE.PARSE_TIMESTAMP('%d/%m/%Y %H:%M',    TRIM(CAST(original_publishing_date AS STRING)), 'Europe/London'),
      SAFE.PARSE_TIMESTAMP('%d/%m/%Y %H:%M:%S', TRIM(CAST(original_publishing_date AS STRING)), 'Europe/London'),
      SAFE.PARSE_TIMESTAMP('%d/%m/%Y',          TRIM(CAST(original_publishing_date AS STRING)), 'Europe/London'),
      SAFE_CAST(TRIM(CAST(original_publishing_date AS STRING)) AS TIMESTAMP)
    ) AS original_publishing_date
  FROM `site-monitoring-421401.job_data_export.missing_entity_ids_review_external`
  WHERE UPPER(TRIM(CAST(done AS STRING))) = 'TRUE'
    AND TRIM(CAST(entity_id AS STRING)) IS NOT NULL
    AND TRIM(CAST(entity_id AS STRING)) != ''
    AND TRIM(CAST(external_id AS STRING)) IS NOT NULL
    AND TRIM(CAST(external_id AS STRING)) != ''
) AS source
ON target.external_id = source.external_id
   AND target.external_id IS NOT NULL
   AND target.external_id != ''

-- Blank-fill only — never overwrite a pre-existing value. The feed is source
-- of truth for everything else, so we only touch the 3 Jobiqo-only columns.
WHEN MATCHED THEN UPDATE SET
  target.entity_id = IF(target.entity_id IS NULL OR target.entity_id = '', source.entity_id, target.entity_id),
  target.employer_type = IF(target.employer_type IS NULL OR TRIM(target.employer_type) IN ('', 'nan'), source.employer_type, target.employer_type),
  target.original_publishing_date = IF(target.original_publishing_date IS NULL, source.original_publishing_date, target.original_publishing_date),
  target.last_updated = CURRENT_TIMESTAMP();
