# Extract Method Setup Guide

## The Problem

BigQuery DATASOURCE sheets cannot be accessed programmatically - neither by:
- Google Sheets API ❌
- Google Apps Script ❌

This is a Google limitation for connected data source sheets.

## The Solution: Use Extract + Monitor

Google Sheets provides an **"Extract"** button in the BigQuery toolbar that creates a snapshot of the data as a regular sheet. We monitor for these extracts and copy them to a stable sheet name.

### Workflow

```
1. Click "Extract" in BigQuery toolbar (manual or scheduled)
   ↓
2. Google Sheets creates "Extract of [sheet name]"
   ↓
3. Apps Script detects the extract (runs every 30 min)
   ↓
4. Script copies extract to "job_data_copy" (stable name)
   ↓
5. Dashboard reads from "job_data_copy"
   ↓
6. Extract is archived with timestamp
```

## Setup Instructions

### Step 1: Create Initial Extract (One-time, 2 minutes)

1. Open your [Google Sheet](https://docs.google.com/spreadsheets/d/1XvVxCV8oo-qwZOwdHfsqMTIljHQ1gHISfZoIvVI8i7U/edit)
2. Click on the **`job-performance-details_combined_2`** tab (the BigQuery sheet)
3. Look for the BigQuery toolbar at the top (has buttons like "Chart", "Pivot table", **"Extract"**)
4. Click the **"Extract"** button
5. Wait for it to complete (may take a minute for large datasets)
6. You should now see a new sheet tab called **"Extract of job-performance-details_combined_2"**

### Step 2: Install Apps Script (5 minutes)

1. In your Google Sheet, go to **Extensions** > **Apps Script**
2. Delete any existing code
3. Copy the entire contents of `ExtractMonitor.gs`
4. Paste it into the Apps Script editor
5. Click **Save** (💾 icon)

### Step 3: Run Setup (1 minute)

1. In Apps Script, select **`setupMonitor`** from the function dropdown
2. Click **Run** (▶️)
3. Authorize the script (first time only):
   - Click "Review Permissions"
   - Choose your account
   - Click "Advanced" → "Go to [Project Name] (unsafe)"
   - Click "Allow"
4. You should see a success message
5. Go back to your Google Sheet
6. You should now see a **`job_data_copy`** sheet with your data!

### Step 4: Run Dashboard

The dashboard is already configured. Just run:

```bash
cd /Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard
./run.sh
```

## How It Works

### Automatic Monitoring
- Script checks every **30 minutes** for new extract sheets
- When found, automatically copies to `job_data_copy`
- Archives the extract with a timestamp
- Keeps 5 most recent backups

### When to Extract
You need to manually click "Extract" when you want fresh data:

1. **On-Demand**: Click "Extract" whenever you need current data
2. **After BigQuery Refresh**: The BigQuery sheet refreshes every 3-4 hours. After it refreshes, click "Extract"
3. **Before Important Reports**: Extract fresh data before generating reports

### BigQuery Scheduled Extracts (Optional - Advanced)

If you have access to the BigQuery connection settings, you can schedule automatic extracts:

1. Click "Connection settings" in the BigQuery toolbar
2. Look for "Extract schedule" or "Refresh schedule" options
3. Set up automatic extract (e.g., daily at 9 AM)

**Note:** This may require permissions from your vendor. If not available, just extract manually as needed.

## Usage

### Manual Extract + Process
1. Click on BigQuery sheet tab
2. Click "Extract" button
3. Wait for extract to appear
4. Use menu: **BigQuery Sync** > **Process Extract**
5. Data is copied to `job_data_copy`
6. Dashboard automatically picks up new data (refreshes every 5 minutes)

### Check Status
- Hover over cell A1 in `job_data_copy` to see last update time
- Check **Executions** in Apps Script to see processing history

## Customization

Edit `CONFIG` in `ExtractMonitor.gs`:

```javascript
const CONFIG = {
  SOURCE_EXTRACT_NAME: 'Extract of job-performance-details_combined_2',
  DEST_SHEET_NAME: 'job_data_copy',
  KEEP_HISTORY: true,
  MAX_HISTORY: 5,
  CHECK_INTERVAL_MINUTES: 30
};
```

## Comparison: Extract Method vs. Direct Copy

| Feature | Extract Method ✅ | Direct Copy ❌ |
|---------|------------------|----------------|
| Works with DATASOURCE sheets | Yes | No |
| Automated | Semi (need to click Extract) | Would be fully automated |
| Speed | Fast (once extracted) | N/A (doesn't work) |
| Reliability | High | N/A |
| Setup complexity | Medium | N/A |

## Troubleshooting

### "No extract found"
- Make sure you clicked "Extract" in the BigQuery toolbar
- Check the extract sheet name matches exactly
- Extract might still be processing - wait and try again

### Script not running
- Check **Apps Script** > **Triggers** (clock icon)
- Verify trigger exists for `processExtract`
- Check execution log for errors

### Data seems old
- Click "Extract" to get fresh data from BigQuery
- Remember: BigQuery sheet itself only refreshes every 3-4 hours
- The extract is a snapshot - it won't update until you extract again

### Can I automate the Extract click?
- Not with standard Apps Script (Google doesn't allow programmatic clicks)
- Options:
  1. Manually click Extract when needed
  2. Ask your vendor about scheduled extracts in BigQuery settings
  3. Use a browser automation tool (advanced, not recommended)

## Advantages

✅ **Works with DATASOURCE sheets** - Only method that works
✅ **Automated monitoring** - Script handles the rest after you extract
✅ **Backup history** - Keeps previous versions
✅ **Free** - Uses Google Apps Script free tier
✅ **Simple** - Just click Extract button
✅ **Reliable** - Uses standard Sheets functionality

## Trade-offs

⚠️ **Semi-manual** - Need to click Extract button for fresh data
⚠️ **Snapshot-based** - Data is from time of extract, not real-time
⚠️ **Dependent on BigQuery refresh** - Can only extract what's in the BigQuery sheet

## Workflow Recommendations

### Daily reporting:
1. Morning: Click "Extract" to get overnight data
2. Script processes automatically within 30 min
3. Dashboard shows updated data
4. Afternoon: Extract again if needed

### Weekly reporting:
1. Extract on Monday morning
2. Use that data for the week
3. Extract again next Monday

### On-demand:
1. Extract whenever you need current data
2. Script processes within 30 minutes
3. Or use manual "Process Extract" to process immediately

## Next Steps

1. ✅ Click "Extract" in BigQuery toolbar
2. ✅ Install `ExtractMonitor.gs` script
3. ✅ Run `setupMonitor()` function
4. ✅ Verify `job_data_copy` exists
5. ✅ Run dashboard: `./run.sh`
6. ✅ Set reminder to extract data regularly!

The dashboard will now work with extracted data!
