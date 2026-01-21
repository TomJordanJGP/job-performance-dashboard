-- Updated BigQuery Query with Job Metadata Join
-- This query joins event data with job metadata to include occupation, location, status, etc.

SELECT
    e.entity_id,
    e.event_name,
    e.event_date,
    e.organization_name,
    e.regions,
    e.upgrades,
    e.importer_ID,

    -- Add metadata fields from job_metadata table
    m.title,
    m.workflow_state,
    m.occupational_fields,
    m.locations as location_full,
    m.publishing_date as start_date,
    m.expiration_date as end_date,
    m.organization_profile_name as organization_name_jobiqo,
    m.employment_type

FROM
    `job-board-analytics-444710.job_board_events.job_events_processed` e

LEFT JOIN
    `job-board-analytics-444710.job_board_events.job_metadata` m
    ON e.entity_id = m.entity_id

WHERE
    e.event_name IN ('job_visit', 'job_apply_start')

ORDER BY
    e.event_date DESC
