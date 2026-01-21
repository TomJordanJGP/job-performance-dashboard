# App.py Updates for Metadata Join Approach

## Changes Needed

After creating the `job_metadata` table in BigQuery, update `app.py` to:
1. Remove CSV loading
2. Update BigQuery query to include JOIN
3. Remove merge_jobiqo_data calls

---

## Step 1: Update `load_data_from_bigquery()` function

**Current code (line ~50-73):**
```python
@st.cache_data(ttl=300)
def load_data_from_bigquery():
    """Load data from BigQuery."""
    try:
        creds = Credentials.from_service_account_file('service_account.json')
        client = bigquery.Client(credentials=creds, project=creds.project_id)

        query = """
        SELECT *
        FROM `job-board-analytics-444710.job_board_events.job_events_processed`
        WHERE event_name IN ('job_visit', 'job_apply_start')
        """

        df = client.query(query).to_dataframe()
        return df
    except Exception as e:
        st.error(f"❌ Error loading data from BigQuery: {str(e)}")
        st.stop()
```

**NEW code:**
```python
@st.cache_data(ttl=300)
def load_data_from_bigquery():
    """Load data from BigQuery with job metadata joined."""
    try:
        creds = Credentials.from_service_account_file('service_account.json')
        client = bigquery.Client(credentials=creds, project=creds.project_id)

        query = """
        SELECT
            e.entity_id,
            e.event_name,
            e.event_date,
            e.organization_name,
            e.regions,
            e.upgrades,
            e.importer_ID,

            -- Job metadata fields
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
        """

        df = client.query(query).to_dataframe()
        return df
    except Exception as e:
        st.error(f"❌ Error loading data from BigQuery: {str(e)}")
        st.stop()
```

---

## Step 2: Remove CSV loading functions

**DELETE these functions (lines ~94-101):**
```python
@st.cache_data(ttl=300)
def load_jobiqo_export():
    """Load Jobiqo export data from CSV file."""
    try:
        jobiqo_df = pd.read_csv('jobs-export.csv', low_memory=False)
        return jobiqo_df
    except Exception:
        return pd.DataFrame()
```

**DELETE this function (lines ~149-181):**
```python
def merge_jobiqo_data(df, jobiqo_df):
    """Merge Jobiqo export data with main data."""
    # ... entire function can be deleted
```

---

## Step 3: Update main() function

**Current code (line ~900-920):**
```python
def main():
    st.title("📊 Job Performance Dashboard")

    # Load data
    df = load_data_from_bigquery()
    importer_mapping = load_importer_mapping()
    jobiqo_df = load_jobiqo_export()  # <-- REMOVE THIS LINE

    # Process data
    df = parse_date_column(df)
    df = merge_jobiqo_data(df, jobiqo_df)  # <-- REMOVE THIS LINE
    df = add_uk_regions(df)
    df = parse_upgrades(df)
    df = parse_dates_in_jobiqo(df)
    df = apply_importer_mapping(df, importer_mapping)
```

**NEW code:**
```python
def main():
    st.title("📊 Job Performance Dashboard")

    # Load data (now includes metadata from JOIN)
    df = load_data_from_bigquery()
    importer_mapping = load_importer_mapping()

    # Process data
    df = parse_date_column(df)
    # No need to merge - data already joined in BigQuery!
    df = add_uk_regions(df)
    df = parse_upgrades(df)
    df = parse_dates_in_jobiqo(df)
    df = apply_importer_mapping(df, importer_mapping)
```

---

## Step 4: (Optional) Add metadata refresh function

Add this function to allow manual refresh of metadata table:

```python
def refresh_metadata_table():
    """Refresh job metadata table from CSV (admin function)."""
    try:
        creds = Credentials.from_service_account_file('service_account.json')
        client = bigquery.Client(credentials=creds, project=creds.project_id)

        # Load CSV
        df = pd.read_csv('jobs-export.csv', low_memory=False)

        # Prepare data
        df_clean = pd.DataFrame({
            'entity_id': df['job_id'].astype(str),
            'title': df['title'],
            'workflow_state': df['workflow_state'],
            'occupational_fields': df['occupational_fields'],
            'locations': df['locations'],
            'publishing_date': pd.to_datetime(df['publishing_date'], errors='coerce'),
            'expiration_date': pd.to_datetime(df['expiration_date'], errors='coerce'),
            'organization_profile_name': df['organization_profile_name'],
            'organization_id': df.get('organization_id', ''),
            'employment_type': df.get('employment_type', ''),
            'last_updated': pd.Timestamp.now()
        })

        # Remove duplicates
        df_clean = df_clean.drop_duplicates(subset=['entity_id'], keep='last')

        # Load to BigQuery
        table_id = "job-board-analytics-444710.job_board_events.job_metadata"
        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")

        job = client.load_table_from_dataframe(df_clean, table_id, job_config=job_config)
        job.result()

        st.success(f"✅ Refreshed metadata for {len(df_clean)} jobs")
        st.cache_data.clear()  # Clear cache to reload data

    except Exception as e:
        st.error(f"❌ Error refreshing metadata: {e}")
```

Then add this to your sidebar:

```python
# In sidebar
with st.sidebar:
    st.markdown("---")
    if st.button("🔄 Refresh Metadata"):
        with st.spinner("Refreshing job metadata from CSV..."):
            refresh_metadata_table()
```

---

## Benefits of This Approach

1. **Performance:** JOIN happens in BigQuery (much faster than pandas merge)
2. **Simplicity:** No CSV loading in dashboard
3. **Maintainability:** Update metadata table separately from events
4. **Scalability:** BigQuery handles millions of rows efficiently
5. **Fresh Data:** Can refresh metadata table without touching events

---

## Testing Checklist

After making changes:

- [ ] Run `create_job_metadata_table.py` to create and populate the table
- [ ] Update `app.py` with new query and remove CSV loading
- [ ] Test dashboard loads successfully
- [ ] Verify occupation column appears in vacancy table
- [ ] Verify status column appears and shows "published"/"unpublished"
- [ ] Check regions are mapping correctly
- [ ] Test performance (should be faster than before)
- [ ] Verify filters work correctly
- [ ] Check all tabs display properly

---

## Rollback Plan

If something goes wrong:

1. Keep a backup of current `app.py`
2. The metadata table doesn't affect existing events table
3. Can easily switch back to CSV loading if needed
4. Can delete metadata table with: `DROP TABLE job-board-analytics-444710.job_board_events.job_metadata`
