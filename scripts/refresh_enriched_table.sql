-- Refresh the enriched table after the combined table has been updated.
-- This rebuilds the full enriched table (with metadata joins and region lookups).
--
-- Schedule this in BigQuery Console AFTER the incremental sync runs:
--   https://console.cloud.google.com/bigquery/scheduled-queries?project=site-monitoring-421401
--   Frequency: Daily (e.g. 07:00 UTC — 1 hour after the sync)
--   Processing location: EU

CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.job_performance_enriched`
PARTITION BY event_date_parsed
CLUSTER BY entity_id_str, event_date_parsed
AS
WITH parsed_locations AS (
  SELECT
    CAST(events.entity_id AS STRING) as entity_id_str,
    PARSE_DATE('%Y%m%d', events.event_date) as event_date_parsed,

    events.event_name,
    events.event_date as event_date_original,
    events.hour_of_day,
    events.entity_id as entity_id_original,
    events.entity_type,
    events.organization_name,
    events.title as title_ga4,
    events.occupations as occupations_ga4,
    events.regions as regions_ga4,
    events.employment_types,
    events.importer_ID,
    events.owner_id,
    events.organization_id,
    events.page_referrer,
    events.page_location,
    events.upgrades,
    events.ats_vacancy_number,
    events.ats_account_number,
    events.device,
    events.operating_system,
    events.browser,
    events.campaign,
    events.medium,
    events.source,
    events.Events,

    metadata.title as title_export,
    metadata.workflow_state,
    metadata.occupational_fields as occupational_fields_export,
    metadata.locations as locations_export,
    metadata.publishing_date,
    metadata.expiration_date,
    metadata.organization_profile_name,
    metadata.employment_type as employment_type_export,
    metadata.last_updated as metadata_last_updated,

    TRIM(SPLIT(SPLIT(metadata.locations, '|')[SAFE_OFFSET(0)], ',')[SAFE_OFFSET(0)]) as location_country_export,
    TRIM(SPLIT(SPLIT(metadata.locations, '|')[SAFE_OFFSET(0)], ',')[SAFE_OFFSET(1)]) as location_town_export,
    TRIM(SPLIT(SPLIT(metadata.locations, '|')[SAFE_OFFSET(0)], ',')[SAFE_OFFSET(2)]) as location_geo_area_export

  FROM `site-monitoring-421401.job_data_export.job_performance_details_combined` AS events
  LEFT JOIN `site-monitoring-421401.job_data_export.job_metadata` AS metadata
    ON CAST(events.entity_id AS STRING) = metadata.entity_id
)

SELECT
  pl.*,
  loc.county as location_county_matched,
  loc.region as location_region_matched
FROM parsed_locations pl
LEFT JOIN `site-monitoring-421401.job_data_export.location_lookup` AS loc
  ON UPPER(TRIM(pl.location_town_export)) = UPPER(TRIM(loc.town_city));
