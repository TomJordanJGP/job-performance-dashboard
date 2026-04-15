-- One-off cleanup: Deduplicate job_metadata rows that share an external_id.
--
-- Context:
-- Prior to the fix in sync_external_id_additions.sql (MERGE now matches on
-- external_id when target.entity_id is NULL), every Sheet-fill for a vacancy
-- already in the feed inserted a NEW row with the entity_id, leaving the
-- pre-existing feed row in place with entity_id = NULL. Result: 636 duplicate
-- pairs — one "rich feed twin" (no entity_id, full salary/dates/contract) and
-- one "sparse Sheet twin" (entity_id filled, Jobiqo-formatted, most fields NULL).
--
-- Goal: collapse each pair into a single row that has the feed's rich data
-- PLUS the entity_id. Feed is source of truth for all fields other than
-- entity_id.
--
-- Approach:
--   Step 1: UPDATE the rich feed twin — copy entity_id in from the sparse twin
--           (keyed on external_id).
--   Step 2: DELETE the sparse twin (now superseded — both rows share the same
--           entity_id, feed row has the later last_updated).
--
-- RUN ONCE manually in BigQuery Console (EU location).
-- Do NOT wire into daily_refresh.py — the MERGE fix is expected to prevent
-- any new duplicates from being created.
--
-- Verification query (should return 0 after running):
--   SELECT COUNT(*) FROM (
--     SELECT external_id
--     FROM `site-monitoring-421401.job_data_export.job_metadata`
--     WHERE external_id IS NOT NULL AND external_id != ''
--     GROUP BY external_id
--     HAVING COUNTIF(entity_id IS NOT NULL AND entity_id != '') > 0
--        AND COUNTIF(entity_id IS NULL OR entity_id = '') > 0
--   );

-- Step 1: Fill entity_id on the rich feed twin.
-- Only touches rows whose external_id currently has both a filled AND an unfilled
-- row (i.e. a known duplicate pair). The `src` subquery picks the entity_id
-- from the sparse twin.
UPDATE `site-monitoring-421401.job_data_export.job_metadata` AS target
SET
  entity_id = src.entity_id,
  last_updated = CURRENT_TIMESTAMP()
FROM (
  SELECT
    external_id,
    ANY_VALUE(entity_id) AS entity_id
  FROM `site-monitoring-421401.job_data_export.job_metadata`
  WHERE entity_id IS NOT NULL AND entity_id != ''
    AND external_id IS NOT NULL AND external_id != ''
    AND external_id IN (
      SELECT external_id
      FROM `site-monitoring-421401.job_data_export.job_metadata`
      WHERE external_id IS NOT NULL AND external_id != ''
      GROUP BY external_id
      HAVING COUNTIF(entity_id IS NOT NULL AND entity_id != '') > 0
         AND COUNTIF(entity_id IS NULL  OR  entity_id = '') > 0
    )
  GROUP BY external_id
) AS src
WHERE target.external_id = src.external_id
  AND (target.entity_id IS NULL OR target.entity_id = '');

-- Step 2: Delete the sparse twin — now identified by (external_id, entity_id)
-- matching another row whose last_updated is strictly greater (the feed twin
-- we just updated has last_updated = CURRENT_TIMESTAMP() from Step 1).
DELETE FROM `site-monitoring-421401.job_data_export.job_metadata` AS t
WHERE t.external_id IS NOT NULL
  AND t.external_id != ''
  AND t.entity_id IS NOT NULL
  AND t.entity_id != ''
  AND EXISTS (
    SELECT 1
    FROM `site-monitoring-421401.job_data_export.job_metadata` AS other
    WHERE other.external_id = t.external_id
      AND other.entity_id = t.entity_id
      AND other.last_updated > t.last_updated
  );
