-- Sync reviewed vacancy metadata from Google Sheets into job_metadata.
-- Reads from the "Missing IDs" tab of the review Sheet, picks up rows
-- marked done=TRUE, and MERGEs them into job_metadata.
--
-- For MATCHED rows (entity_id already exists): fill blanks only — never
-- overwrites existing feed data.
-- For NOT MATCHED rows (no metadata row): inserts a new row with all
-- provided fields.
--
-- Run as part of daily_refresh.py (before refresh_enriched_table.sql).
--
-- Sheet columns (21):
--   entity_id, title, organization_name, importer_name, first_seen_date,
--   event_count, external_id, organization_id, locations, employment_type,
--   occupational_fields, employer_type, workflow_state, publishing_date,
--   expiration_date, min_salary, max_salary, currency_code, salary_unit,
--   salary_free_text, done
--
-- Context-only columns NOT synced: importer_name, first_seen_date, event_count
-- Field mapping: organization_name → organization_profile_name

-- Step 1: Create/refresh external table backed by the Missing IDs tab.
CREATE OR REPLACE EXTERNAL TABLE `site-monitoring-421401.job_data_export.missing_ids_review_external`
OPTIONS (
  format = 'GOOGLE_SHEETS',
  uris = ['https://docs.google.com/spreadsheets/d/1YPfZMxK2Rdl91JjAKd60xtjNinDfBe0DHpa5euFwmDc'],
  sheet_range = 'Missing IDs',
  skip_leading_rows = 1
);

-- Step 2: MERGE approved rows into job_metadata.
MERGE `site-monitoring-421401.job_data_export.job_metadata` AS target
USING (
  SELECT
    TRIM(CAST(entity_id AS STRING)) AS entity_id,
    TRIM(CAST(external_id AS STRING)) AS external_id,
    TRIM(CAST(title AS STRING)) AS title,
    TRIM(CAST(organization_name AS STRING)) AS organization_profile_name,
    TRIM(CAST(organization_id AS STRING)) AS organization_id,
    TRIM(CAST(locations AS STRING)) AS locations,
    TRIM(CAST(employment_type AS STRING)) AS employment_type,
    TRIM(CAST(occupational_fields AS STRING)) AS occupational_fields,
    TRIM(CAST(employer_type AS STRING)) AS employer_type,
    TRIM(CAST(workflow_state AS STRING)) AS workflow_state,
    SAFE_CAST(TRIM(CAST(publishing_date AS STRING)) AS TIMESTAMP) AS publishing_date,
    SAFE_CAST(TRIM(CAST(expiration_date AS STRING)) AS TIMESTAMP) AS expiration_date,
    SAFE_CAST(TRIM(CAST(min_salary AS STRING)) AS FLOAT64) AS min_salary,
    SAFE_CAST(TRIM(CAST(max_salary AS STRING)) AS FLOAT64) AS max_salary,
    TRIM(CAST(currency_code AS STRING)) AS currency_code,
    TRIM(CAST(salary_unit AS STRING)) AS salary_unit,
    TRIM(CAST(salary_free_text AS STRING)) AS salary_free_text
  FROM `site-monitoring-421401.job_data_export.missing_ids_review_external`
  WHERE UPPER(TRIM(CAST(done AS STRING))) = 'TRUE'
    AND TRIM(CAST(entity_id AS STRING)) IS NOT NULL
    AND TRIM(CAST(entity_id AS STRING)) != ''
) AS source
ON target.entity_id = source.entity_id

WHEN MATCHED THEN UPDATE SET
  target.external_id = IF(target.external_id IS NULL OR TRIM(target.external_id) IN ('', 'nan'), source.external_id, target.external_id),
  target.title = IF(target.title IS NULL OR TRIM(target.title) IN ('', 'nan'), source.title, target.title),
  target.organization_profile_name = IF(target.organization_profile_name IS NULL OR TRIM(target.organization_profile_name) IN ('', 'nan'), source.organization_profile_name, target.organization_profile_name),
  target.organization_id = IF(target.organization_id IS NULL OR TRIM(target.organization_id) IN ('', 'nan'), source.organization_id, target.organization_id),
  target.locations = IF(target.locations IS NULL OR TRIM(target.locations) IN ('', 'nan'), source.locations, target.locations),
  target.employment_type = IF(target.employment_type IS NULL OR TRIM(target.employment_type) IN ('', 'nan'), source.employment_type, target.employment_type),
  target.occupational_fields = IF(target.occupational_fields IS NULL OR TRIM(target.occupational_fields) IN ('', 'nan'), source.occupational_fields, target.occupational_fields),
  target.employer_type = IF(target.employer_type IS NULL OR TRIM(target.employer_type) IN ('', 'nan'), source.employer_type, target.employer_type),
  target.workflow_state = IF(target.workflow_state IS NULL OR TRIM(target.workflow_state) IN ('', 'nan'), source.workflow_state, target.workflow_state),
  target.publishing_date = IF(target.publishing_date IS NULL, source.publishing_date, target.publishing_date),
  target.expiration_date = IF(target.expiration_date IS NULL, source.expiration_date, target.expiration_date),
  target.min_salary = IF(target.min_salary IS NULL, source.min_salary, target.min_salary),
  target.max_salary = IF(target.max_salary IS NULL, source.max_salary, target.max_salary),
  target.currency_code = IF(target.currency_code IS NULL OR TRIM(target.currency_code) IN ('', 'nan'), source.currency_code, target.currency_code),
  target.salary_unit = IF(target.salary_unit IS NULL OR TRIM(target.salary_unit) IN ('', 'nan'), source.salary_unit, target.salary_unit),
  target.salary_free_text = IF(target.salary_free_text IS NULL OR TRIM(target.salary_free_text) IN ('', 'nan'), source.salary_free_text, target.salary_free_text),
  target.last_updated = CURRENT_TIMESTAMP()

WHEN NOT MATCHED THEN
  INSERT (entity_id, external_id, title, organization_profile_name, organization_id,
          locations, employment_type, occupational_fields, employer_type, workflow_state,
          publishing_date, expiration_date, min_salary, max_salary, currency_code,
          salary_unit, salary_free_text, last_updated)
  VALUES (
    source.entity_id,
    IF(source.external_id = '', NULL, source.external_id),
    IF(source.title = '', NULL, source.title),
    IF(source.organization_profile_name = '', NULL, source.organization_profile_name),
    IF(source.organization_id = '', NULL, source.organization_id),
    IF(source.locations = '', NULL, source.locations),
    IF(source.employment_type = '', NULL, source.employment_type),
    IF(source.occupational_fields = '', NULL, source.occupational_fields),
    IF(source.employer_type = '', NULL, source.employer_type),
    IF(source.workflow_state = '', NULL, source.workflow_state),
    source.publishing_date,
    source.expiration_date,
    source.min_salary,
    source.max_salary,
    IF(source.currency_code = '', NULL, source.currency_code),
    IF(source.salary_unit = '', NULL, source.salary_unit),
    IF(source.salary_free_text = '', NULL, source.salary_free_text),
    CURRENT_TIMESTAMP()
  );
