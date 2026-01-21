# BigQuery Access Setup

The dashboard now queries BigQuery directly, which solves the issue with BigQuery connected sheets.

## What Changed

Instead of reading from the Google Sheet (which fails for BigQuery connected sheets), the app now:
1. Queries BigQuery directly using the BigQuery Python client
2. Still reads the importer_mapping from Google Sheets (which is a regular sheet)

## Required Permissions

Your service account needs:
1. **Google Sheets API** access (already set up) - for importer mapping
2. **BigQuery** access - NEW requirement

## How to Grant BigQuery Access

### Option 1: Using Google Cloud Console (Recommended)

1. Go to https://console.cloud.google.com/
2. Select the project: **jobsgopublic**
3. Go to **IAM & Admin** > **IAM**
4. Find your service account (the email from service_account.json)
5. Click **Edit** (pencil icon)
6. Click **Add Another Role**
7. Add role: **BigQuery Data Viewer**
8. Click **Save**

### Option 2: Using gcloud CLI

```bash
# Get the service account email from your JSON file
SERVICE_ACCOUNT_EMAIL="your-service-account@jobsgopublic.iam.gserviceaccount.com"

# Grant BigQuery Data Viewer role
gcloud projects add-iam-policy-binding jobsgopublic \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.dataViewer"

# Grant BigQuery Job User role (needed to run queries)
gcloud projects add-iam-policy-binding jobsgopublic \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.jobUser"
```

## BigQuery Connection Details

The app connects to:
- **Project**: jobsgopublic
- **Dataset**: Datastudio_scheduled_data_combined
- **Table**: Job-performance-details_combined

These are configured in `app.py` at the top:
```python
BQ_PROJECT_ID = "jobsgopublic"
BQ_DATASET_ID = "Datastudio_scheduled_data_combined"
BQ_TABLE_ID = "Job-performance-details_combined"
```

## Testing

Once you've granted BigQuery access:

```bash
cd job-performance-dashboard
./run.sh
```

The dashboard should now load data directly from BigQuery!

## Advantages of This Approach

1. **Automated** - No manual copying of data
2. **Real-time** - Always queries the latest BigQuery data
3. **Reliable** - No API limitations with connected sheets
4. **Scalable** - Can handle large datasets efficiently
5. **Flexible** - Can add custom SQL queries if needed

## Troubleshooting

### "Permission denied" or "Access Denied"
- Make sure the service account has BigQuery Data Viewer and Job User roles
- Check you're granting access in the correct project (jobsgopublic)

### "Table not found"
- Verify the table exists in BigQuery
- Check the project/dataset/table names in app.py match exactly

### "Quota exceeded"
- BigQuery has generous free tier
- If you hit limits, you may need to enable billing on the project
