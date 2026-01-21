-- Partition the job_performance_details_combined table by event_date
-- This will dramatically improve query performance by only scanning relevant partitions
-- Run this SQL in BigQuery console: https://console.cloud.google.com/bigquery

-- NOTE: event_date is stored as INT64 (YYYYMMDD format, e.g., 20240121)
-- We'll use INTEGER RANGE partitioning with yearly buckets

-- Step 1: Create a new partitioned table using RANGE partitioning on the integer event_date
CREATE TABLE IF NOT EXISTS `site-monitoring-421401.job_data_export.job_performance_details_combined_partitioned`
PARTITION BY RANGE_BUCKET(event_date, GENERATE_ARRAY(20200101, 20301231, 10000))
CLUSTER BY event_date, entity_id
AS SELECT * FROM `site-monitoring-421401.job_data_export.job_performance_details_combined`;

-- Step 2: Verify the new table
SELECT
  COUNT(*) as total_rows,
  MIN(event_date) as min_date,
  MAX(event_date) as max_date
FROM `site-monitoring-421401.job_data_export.job_performance_details_combined_partitioned`;

-- Step 3: Test query performance on partitioned table (should be fast!)
SELECT *
FROM `site-monitoring-421401.job_data_export.job_performance_details_combined_partitioned`
WHERE event_date >= 20241201
LIMIT 10;

-- You should see "Bytes processed" is much smaller than querying the original table

-- Step 4: Once verified, rename tables (run these one at a time):
--
-- -- Backup original table
-- CREATE TABLE IF NOT EXISTS `site-monitoring-421401.job_data_export.job_performance_details_combined_backup`
-- AS SELECT * FROM `site-monitoring-421401.job_data_export.job_performance_details_combined`;
--
-- -- Drop original
-- DROP TABLE `site-monitoring-421401.job_data_export.job_performance_details_combined`;
--
-- -- Rename partitioned table to original name
-- ALTER TABLE `site-monitoring-421401.job_data_export.job_performance_details_combined_partitioned`
-- RENAME TO job_performance_details_combined;

-- After partitioning, queries with WHERE event_date >= 'YYYYMMDD' will be 10-100x faster!
