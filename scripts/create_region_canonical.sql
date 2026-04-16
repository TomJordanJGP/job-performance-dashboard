-- Create canonical region lookup table.
-- Maps every known variant to one of the 12 ONS statistical regions.
-- Used by refresh_enriched_table.sql to normalise primary_uk_region.
--
-- To add a new variant: INSERT a row with (lower-cased variant, canonical name).
-- Run once to create, then re-run only when adding new variants.

CREATE OR REPLACE TABLE `site-monitoring-421401.job_data_export.region_canonical` AS

WITH variants AS (
  -- 12 canonical ONS regions (self-mapping)
  SELECT 'north east' AS variant, 'North East' AS canonical_region UNION ALL
  SELECT 'north west', 'North West' UNION ALL
  SELECT 'yorkshire and the humber', 'Yorkshire and The Humber' UNION ALL
  SELECT 'east midlands', 'East Midlands' UNION ALL
  SELECT 'west midlands', 'West Midlands' UNION ALL
  SELECT 'east of england', 'East of England' UNION ALL
  SELECT 'greater london', 'Greater London' UNION ALL
  SELECT 'south east', 'South East' UNION ALL
  SELECT 'south west', 'South West' UNION ALL
  SELECT 'wales', 'Wales' UNION ALL
  SELECT 'scotland', 'Scotland' UNION ALL
  SELECT 'northern ireland', 'Northern Ireland' UNION ALL

  -- London variants -> Greater London
  SELECT 'london', 'Greater London' UNION ALL
  SELECT 'london borough', 'Greater London' UNION ALL
  SELECT 'city of london', 'Greater London' UNION ALL
  SELECT 'inner london', 'Greater London' UNION ALL
  SELECT 'outer london', 'Greater London' UNION ALL

  -- Yorkshire case variants
  SELECT 'yorkshire and the humber', 'Yorkshire and The Humber' UNION ALL
  SELECT 'yorkshire & the humber', 'Yorkshire and The Humber' UNION ALL
  SELECT 'yorkshire', 'Yorkshire and The Humber' UNION ALL
  SELECT 'humber', 'Yorkshire and The Humber' UNION ALL
  SELECT 'humberside', 'Yorkshire and The Humber' UNION ALL

  -- Scottish sub-regions -> Scotland
  SELECT 'north east scotland', 'Scotland' UNION ALL
  SELECT 'south west scotland', 'Scotland' UNION ALL
  SELECT 'highland and islands', 'Scotland' UNION ALL
  SELECT 'scottish borders', 'Scotland' UNION ALL
  SELECT 'west coast of scotland', 'Scotland' UNION ALL
  SELECT 'north scotland', 'Scotland' UNION ALL
  SELECT 'central lowlands', 'Scotland' UNION ALL
  SELECT 'lothian', 'Scotland' UNION ALL
  SELECT 'west central scotland', 'Scotland' UNION ALL
  SELECT 'south east scotland', 'Scotland' UNION ALL
  SELECT 'far north of scotland', 'Scotland' UNION ALL
  SELECT 'north highlands', 'Scotland' UNION ALL
  SELECT 'highlands', 'Scotland' UNION ALL
  SELECT 'highlands and islands', 'Scotland' UNION ALL
  SELECT 'grampian', 'Scotland' UNION ALL
  SELECT 'tayside', 'Scotland' UNION ALL
  SELECT 'fife', 'Scotland' UNION ALL
  SELECT 'strathclyde', 'Scotland' UNION ALL
  SELECT 'central scotland', 'Scotland' UNION ALL
  SELECT 'dumfries and galloway', 'Scotland' UNION ALL

  -- Welsh variants
  SELECT 'south wales', 'Wales' UNION ALL
  SELECT 'north wales', 'Wales' UNION ALL
  SELECT 'mid wales', 'Wales' UNION ALL
  SELECT 'west wales', 'Wales' UNION ALL

  -- East of England variants
  SELECT 'east anglia', 'East of England' UNION ALL
  SELECT 'eastern', 'East of England' UNION ALL
  SELECT 'east', 'East of England' UNION ALL

  -- London hyphenated variant
  SELECT 'greater-london', 'Greater London' UNION ALL

  -- North West variant
  SELECT 'north west england', 'North West' UNION ALL

  -- Overseas territories
  SELECT 'overseas territory', 'Overseas Territory' UNION ALL
  SELECT 'british overseas territory', 'Overseas Territory' UNION ALL

  -- Crown dependencies
  SELECT 'jersey', 'Overseas Territory' UNION ALL
  SELECT 'guernsey', 'Overseas Territory' UNION ALL
  SELECT 'isle of man', 'Overseas Territory'
)

SELECT variant, canonical_region
FROM variants;
