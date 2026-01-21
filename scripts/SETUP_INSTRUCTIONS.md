# Setup Instructions: Move to BigQuery Metadata Join

## Overview

Instead of loading `jobs-export.csv` in the dashboard, we'll:
1. Create a `job_metadata` table in BigQuery
2. Load the CSV data into that table (one-time)
3. Update the dashboard query to JOIN with metadata table
4. Remove CSV loading code from dashboard

**Result:** Faster dashboard, cleaner code, all data in BigQuery!

---

## Step-by-Step Setup

### Step 1: Create and Populate Metadata Table

```bash
cd /Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard
python3 scripts/create_job_metadata_table.py
```

This will:
- Create `job-board-analytics-444710.job_board_events.job_metadata` table
- Load all 27k+ jobs from `jobs-export.csv`
- Test the table with a sample query

**Expected output:**
```
================================================================================
Creating Job Metadata Table in BigQuery
================================================================================
✅ Created table job-board-analytics-444710.job_board_events.job_metadata
Loading jobs-export.csv...
Found 27086 jobs in CSV
Loading 27086 unique jobs to BigQuery...
✅ Loaded 27086 jobs to job-board-analytics-444710.job_board_events.job_metadata
✅ Table now contains 27086 rows

Testing query...
[Sample data displayed]
✅ Query successful! Retrieved 10 rows

================================================================================
✅ COMPLETE!
================================================================================
```

---

### Step 2: Backup Current app.py

```bash
cp app.py app.py.backup
```

Just in case you need to rollback!

---

### Step 3: Update app.py

Open `scripts/app_updates_for_metadata_join.md` and follow the instructions to:

1. Update `load_data_from_bigquery()` with new JOIN query
2. Delete `load_jobiqo_export()` function
3. Delete `merge_jobiqo_data()` function
4. Remove CSV loading and merge calls from `main()`

**Quick reference - the key changes:**

**BEFORE:**
```python
df = load_data_from_bigquery()
jobiqo_df = load_jobiqo_export()
df = merge_jobiqo_data(df, jobiqo_df)
```

**AFTER:**
```python
df = load_data_from_bigquery()  # Now includes metadata via JOIN!
# That's it - no CSV loading needed
```

---

### Step 4: Test the Dashboard

```bash
streamlit run app.py
```

**What to verify:**
- [ ] Dashboard loads without errors
- [ ] Occupation column shows in Vacancy Performance table
- [ ] Status column shows "published" or "unpublished"
- [ ] Regions are mapping correctly
- [ ] All filters work
- [ ] Performance is faster (no CSV loading delay)

---

### Step 5: Future Updates

When `jobs-export.csv` gets updated with new jobs:

**Option A: Manual refresh via dashboard**
- Add refresh button to sidebar (see app_updates_for_metadata_join.md)
- Click button to reload metadata from CSV

**Option B: Run script directly**
```bash
python3 scripts/create_job_metadata_table.py
```

**Option C: Automate with cron job**
```bash
# Add to crontab to run daily at 2am
0 2 * * * cd /path/to/dashboard && python3 scripts/create_job_metadata_table.py
```

---

## Troubleshooting

### Issue: "Table not found"
**Solution:** Make sure Step 1 completed successfully. Re-run:
```bash
python3 scripts/create_job_metadata_table.py
```

### Issue: "Columns not found" errors in dashboard
**Solution:** The JOIN worked! The columns now have different names. Check that:
- `workflow_state` (not `status`)
- `occupational_fields` (not `occupation`)
- `location_full` (from locations)
- `start_date` (from publishing_date)
- `end_date` (from expiration_date)

### Issue: Dashboard is slow
**Solution:**
1. Check BigQuery query performance in console
2. Verify JOIN is using indexed column (entity_id)
3. Make sure `st.cache_data` is working

### Issue: Missing jobs in dashboard
**Solution:**
- Check that job exists in both tables
- Verify entity_id matches between events and metadata
- Run test query:
```sql
SELECT COUNT(*)
FROM job_events_processed e
LEFT JOIN job_metadata m ON e.entity_id = m.entity_id
WHERE m.entity_id IS NULL
```

---

## Architecture Diagram

### Before (Current):
```
BigQuery (events)  ──────┐
                         ├──> Streamlit Dashboard
jobs-export.csv ─────────┘    (merge happens here)
                              (slow, memory intensive)
```

### After (New):
```
BigQuery (events) ───┐
                     ├──> BigQuery JOIN ───> Streamlit Dashboard
BigQuery (metadata) ─┘    (fast, efficient)  (just displays)
```

---

## Rollback Instructions

If you need to revert:

1. **Restore backup:**
```bash
cp app.py.backup app.py
```

2. **Restart dashboard:**
```bash
streamlit run app.py
```

3. **(Optional) Delete metadata table:**
```sql
DROP TABLE `job-board-analytics-444710.job_board_events.job_metadata`
```

---

## File Structure

```
job-performance-dashboard/
├── app.py                          # Main dashboard (to be updated)
├── app.py.backup                   # Backup before changes
├── jobs-export.csv                 # Source data for metadata table
├── scripts/
│   ├── create_job_metadata_table.py     # Creates and populates table
│   ├── updated_bigquery_query.sql       # Reference SQL query
│   ├── app_updates_for_metadata_join.md # Detailed update instructions
│   └── SETUP_INSTRUCTIONS.md            # This file
```

---

## Questions?

Common questions:

**Q: Do I need to keep jobs-export.csv?**
A: Yes, for now. Use it to refresh the metadata table when needed.

**Q: How often should I refresh the metadata table?**
A: Whenever new jobs are added or job details change. Daily or weekly is typical.

**Q: Will this affect my events data?**
A: No! The events table is read-only in this process. Only the new metadata table is created/updated.

**Q: Can I add more columns to metadata table later?**
A: Yes! Just update the schema in `create_job_metadata_table.py` and re-run.

---

## Ready to Start?

Run this to begin:
```bash
cd /Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard
python3 scripts/create_job_metadata_table.py
```

Then follow Step 3 to update app.py!
