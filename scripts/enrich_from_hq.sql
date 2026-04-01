-- Enrich job_metadata with HQ region/county from client_hq_addresses.
-- Runs after feed sync, before enriched table rebuild.
-- Only targets single-location vacancies (no pipe in locations field).
-- Two passes: (1) match on org_id, (2) match on org_name for remainder.
-- Fill-blanks-only for org_name (pass 1) and org_id (pass 2).

-- Pass 1: Match on organization_id
-- Sets hq_region, hq_county. Fills org_name if blank.
UPDATE `site-monitoring-421401.job_data_export.job_metadata` m
SET
  m.hq_region = hq.region,
  m.hq_county = hq.county,
  m.organization_profile_name = IF(
    m.organization_profile_name IS NULL OR TRIM(m.organization_profile_name) = '',
    hq.organisation_name,
    m.organization_profile_name
  )
FROM `site-monitoring-421401.job_data_export.client_hq_addresses` hq
WHERE SAFE_CAST(REGEXP_REPLACE(m.organization_id, r'\.0$', '') AS INT64) = hq.organisation_id
  AND (STRPOS(m.locations, '|') = 0 OR m.locations IS NULL OR TRIM(m.locations) = '')
  AND (m.hq_region IS NULL OR TRIM(m.hq_region) = '');

-- Pass 2: Match on organization_profile_name (case-insensitive)
-- For vacancies still without HQ data after pass 1.
-- Sets hq_region, hq_county. Fills org_id if blank.
UPDATE `site-monitoring-421401.job_data_export.job_metadata` m
SET
  m.hq_region = hq.region,
  m.hq_county = hq.county,
  m.organization_id = IF(
    m.organization_id IS NULL OR TRIM(m.organization_id) = '',
    CAST(hq.organisation_id AS STRING),
    m.organization_id
  )
FROM `site-monitoring-421401.job_data_export.client_hq_addresses` hq
WHERE LOWER(TRIM(m.organization_profile_name)) = LOWER(TRIM(hq.organisation_name))
  AND (STRPOS(m.locations, '|') = 0 OR m.locations IS NULL OR TRIM(m.locations) = '')
  AND (m.hq_region IS NULL OR TRIM(m.hq_region) = '')
