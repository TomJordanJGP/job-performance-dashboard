# Grant BigQuery Access to Service Account

Since you're the admin of the `site-monitoring-421401` project, you can easily grant access to your service account.

## Step 1: Find Your Service Account Email

Open your `service_account.json` file and find the `client_email` field. It will look something like:

```
"client_email": "your-service-account@site-monitoring-421401.iam.gserviceaccount.com"
```

Copy that email address.

## Step 2: Grant BigQuery Access

### Option A: Using Google Cloud Console (Easiest)

1. Go to https://console.cloud.google.com/iam-admin/iam?project=site-monitoring-421401
2. Click **"Grant Access"** (or **"+ GRANT ACCESS"**)
3. In "New principals", paste your service account email
4. Click **"Select a role"**
5. Add these two roles:
   - Search for **"BigQuery Data Viewer"** and select it
   - Click **"Add another role"**
   - Search for **"BigQuery Job User"** and select it
6. Click **"Save"**

### Option B: Using gcloud CLI

If you have `gcloud` installed:

```bash
# Set your service account email
SERVICE_ACCOUNT="your-service-account@site-monitoring-421401.iam.gserviceaccount.com"

# Grant BigQuery Data Viewer role
gcloud projects add-iam-policy-binding site-monitoring-421401 \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/bigquery.dataViewer"

# Grant BigQuery Job User role (needed to run queries)
gcloud projects add-iam-policy-binding site-monitoring-421401 \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/bigquery.jobUser"
```

## Step 3: Test the Dashboard

Once you've granted access, run:

```bash
cd /Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard
./run.sh
```

The dashboard should now:
- ✅ Connect to BigQuery in your project
- ✅ Query the `job_performance_details_combined` table
- ✅ Load all 945K rows (or whatever you set as limit)
- ✅ Display the data with all filters and visualizations
- ✅ Load importer mapping from Google Sheets

## What the Roles Do

- **BigQuery Data Viewer**: Allows reading data from BigQuery tables (read-only)
- **BigQuery Job User**: Allows running queries (needed to execute SELECT statements)

Both are safe, read-only permissions - perfect for a dashboard.

## Troubleshooting

### "Permission denied" error
- Double-check the service account email is correct
- Verify you granted both roles
- Wait 1-2 minutes for permissions to propagate

### "Table not found" error
- Verify your scheduled export has completed
- Check the table exists at: https://console.cloud.google.com/bigquery?project=site-monitoring-421401&d=job_data_export&t=job_performance_details_combined&page=table

### Still having issues?
- Make sure you're in the right project (`site-monitoring-421401`)
- Check the dataset name is exactly `job_data_export`
- Check the table name is exactly `job_performance_details_combined`

## Performance with Large Dataset

With 945K rows, the dashboard uses a 5-minute cache. First load might take 10-30 seconds, but subsequent views will be instant until the cache expires.

If you want to limit the data for better performance, you can edit `app.py` and add a LIMIT clause to the SQL query (around line 74).

## Next Steps

After granting access:
1. ✅ Run `./run.sh`
2. ✅ Wait for BigQuery to load data
3. ✅ Test all filters and visualizations
4. ✅ Export some reports to verify everything works!

Your dashboard is now fully automated with scheduled BigQuery exports! 🎉
