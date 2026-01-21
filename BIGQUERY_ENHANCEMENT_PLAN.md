# BigQuery Enhancement Plan: Add Occupation and Location

## Current Situation

**Problem:**
- `occupational_fields` and `locations` are only available in the `jobs-export.csv` file
- BigQuery table doesn't have these fields
- Dashboard currently merges data from CSV, which is:
  - Slower (loading 27k+ rows from CSV each time)
  - Not real-time (CSV needs manual updates)
  - Prone to sync issues

**Goal:**
Add `occupational_fields` and `locations` to the BigQuery table so all data is in one place.

---

## Option 1: Add Columns to Existing BigQuery Table (RECOMMENDED)

### Steps:

1. **Alter BigQuery table to add new columns:**
```sql
ALTER TABLE `job-board-analytics-444710.job_board_events.job_events_processed`
ADD COLUMN occupation STRING,
ADD COLUMN location STRING;
```

2. **Backfill data from jobs-export.csv:**
   - Load the CSV into a temporary BigQuery table
   - Run UPDATE query to populate the new columns based on `entity_id` join

3. **Update data pipeline:**
   - Modify your ETL/pipeline to include occupation and location when inserting new events
   - Source: Wherever you're currently getting the data for BigQuery

### Pros:
- ✅ All data in one place
- ✅ Faster dashboard performance (no CSV merge needed)
- ✅ Real-time updates
- ✅ Better data quality control
- ✅ Can filter/query by occupation and location directly in SQL

### Cons:
- ⚠️ Requires updating the data pipeline
- ⚠️ Need to backfill historical data

---

## Option 2: Create a Lookup Table in BigQuery

### Steps:

1. **Create a new BigQuery table for job metadata:**
```sql
CREATE TABLE `job-board-analytics-444710.job_board_events.job_metadata` (
  entity_id STRING,
  title STRING,
  occupation STRING,
  location STRING,
  workflow_state STRING,
  organization_name STRING,
  start_date DATE,
  end_date DATE,
  importer_id INT64
);
```

2. **Load data from jobs-export.csv into this table**

3. **Update dashboard to join with this table:**
   - Modify the BigQuery query to LEFT JOIN with job_metadata
   - All metadata in one query, no CSV needed

### Pros:
- ✅ Cleaner separation (events vs metadata)
- ✅ Easier to update job information without touching events
- ✅ Still faster than loading CSV
- ✅ No need to modify existing table structure

### Cons:
- ⚠️ Requires maintaining two tables
- ⚠️ More complex queries (need JOIN)

---

## Option 3: Keep CSV but Optimize (TEMPORARY SOLUTION)

### If you can't modify BigQuery right now:

1. **Cache the CSV data more aggressively:**
   - Increase TTL from 300 seconds to 3600 (1 hour)
   - Only reload when CSV file changes

2. **Optimize CSV loading:**
   - Only load columns we actually need
   - Filter rows in CSV load (if possible)

### Update in app.py:
```python
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_jobiqo_export():
    """Load Jobiqo export data from CSV file."""
    try:
        # Only load columns we need
        usecols = ['job_id', 'title', 'workflow_state', 'occupational_fields',
                   'locations', 'publishing_date', 'expiration_date',
                   'organization_profile_name']
        jobiqo_df = pd.read_csv('jobs-export.csv', low_memory=False, usecols=usecols)
        return jobiqo_df
    except Exception:
        return pd.DataFrame()
```

### Pros:
- ✅ Quick fix, no BigQuery changes needed
- ✅ Works immediately

### Cons:
- ❌ Still slow on first load
- ❌ Still requires manual CSV updates
- ❌ Not a long-term solution

---

## Recommended Approach: Option 1 (Add Columns to BigQuery)

### Implementation Plan:

#### Phase 1: Backfill Historical Data (One-time)
```python
# Script: backfill_occupation_location.py

from google.cloud import bigquery
import pandas as pd

# 1. Load jobs-export.csv
jobs_df = pd.read_csv('jobs-export.csv')

# 2. Prepare data for BigQuery
jobs_df['occupation'] = jobs_df['occupational_fields']
jobs_df['location'] = jobs_df['locations']

# Select only needed columns
update_df = jobs_df[['job_id', 'occupation', 'location']].rename(columns={'job_id': 'entity_id'})

# 3. Load to temp BigQuery table
client = bigquery.Client()
table_id = 'job-board-analytics-444710.job_board_events.job_metadata_temp'
job = client.load_table_from_dataframe(update_df, table_id)
job.result()

# 4. Update main table with merge
update_query = """
MERGE `job-board-analytics-444710.job_board_events.job_events_processed` T
USING `job-board-analytics-444710.job_board_events.job_metadata_temp` S
ON T.entity_id = S.entity_id
WHEN MATCHED THEN
  UPDATE SET
    T.occupation = S.occupation,
    T.location = S.location
"""
client.query(update_query).result()

# 5. Drop temp table
client.delete_table(table_id)
print("Backfill complete!")
```

#### Phase 2: Update Data Pipeline
- Add `occupation` and `location` fields to your data ingestion process
- Ensure new events include these fields

#### Phase 3: Update Dashboard
```python
# Remove CSV loading
# Remove merge_jobiqo_data() calls
# Update BigQuery query to include occupation and location
```

---

## Testing Checklist

After implementing:

- [ ] Verify all historical records have occupation/location
- [ ] Check for NULL values and handle appropriately
- [ ] Test dashboard performance (should be faster)
- [ ] Verify occupation filtering works correctly
- [ ] Test region mapping with new location data
- [ ] Compare results with old CSV-based approach

---

## Next Steps

1. **Choose your approach** (Recommendation: Option 1)
2. **Backup your BigQuery table** before making changes
3. **Test on a small dataset** first
4. **Implement backfill script**
5. **Update data pipeline**
6. **Update dashboard code**
7. **Remove CSV dependency**

---

## Questions to Answer:

1. **Where does the BigQuery data come from?**
   - What's the source system?
   - How often is it updated?
   - Can we add occupation/location at the source?

2. **Do we need historical backfill?**
   - How far back do we need data?
   - Is the jobs-export.csv complete for historical data?

3. **Data quality:**
   - Are there jobs in BigQuery that aren't in the CSV?
   - Are there jobs in CSV that aren't in BigQuery?
   - How do we handle mismatches?

4. **Who maintains the data pipeline?**
   - Do you have access to modify it?
   - Or do we need to request changes from another team?
