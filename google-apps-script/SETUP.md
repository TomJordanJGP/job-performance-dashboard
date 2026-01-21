# Google Apps Script Setup Guide

This script automatically copies data from your BigQuery connected sheet to a regular Google Sheet tab that can be accessed via the API.

## Why This Works

- **BigQuery connected sheets** cannot be read via Google Sheets API (400 error)
- **Regular sheets** work perfectly with the API
- This script **automatically copies** the data every hour
- Keeps **backup copies** of previous syncs (optional)

## Installation Steps

### 1. Open Apps Script Editor

1. Open your Google Sheet: [Job_Performance_Data](https://docs.google.com/spreadsheets/d/1XvVxCV8oo-qwZOwdHfsqMTIljHQ1gHISfZoIvVI8i7U/edit)
2. Click **Extensions** > **Apps Script**
3. If there's any existing code, delete it
4. Copy the entire contents of `Code.gs` (the file in this folder)
5. Paste it into the Apps Script editor
6. Click the **Save** icon (💾) or press Cmd+S

### 2. Run Initial Setup

1. In the Apps Script editor, find the function dropdown at the top
2. Select **`setupTrigger`** from the dropdown
3. Click the **Run** button (▶️)
4. **First time only:** You'll need to authorize the script:
   - Click "Review Permissions"
   - Choose your Google account
   - Click "Advanced" (if you see a warning)
   - Click "Go to [Project Name] (unsafe)" - this is safe, it's your own script
   - Click "Allow"
5. Wait for it to complete (check the execution log)
6. You should see a success alert saying "Automatic data sync is now set up"

### 3. Verify It Worked

1. Go back to your Google Sheet
2. You should see a new tab called **`job_data_copy`**
3. This tab should contain all the data from your BigQuery sheet
4. Check the note on cell A1 (hover over it) - it shows the last update time

### 4. Test the Menu

1. You should now see a new menu called **"BigQuery Sync"** in your Google Sheet menu bar
2. This menu has three options:
   - **Manual Refresh**: Copy data on demand
   - **Setup Auto-Sync**: Run this again if you need to reset the trigger
   - **Remove Auto-Sync**: Stop automatic syncing

## How It Works

### Automatic Sync
- Runs **every hour** automatically
- Copies all data from `job-performance-details_combined_2` to `job_data_copy`
- Keeps the 3 most recent backup copies (configurable)
- Adds a timestamp note to track when data was last updated

### Manual Sync
- Use **BigQuery Sync > Manual Refresh** from the menu
- Or run the `copyBigQueryData()` function directly from Apps Script

### Backups
- Creates timestamped backup sheets: `job_data_copy_backup_2026-01-20_1430`
- Keeps the 3 most recent backups (configurable)
- Automatically deletes older backups

## Configuration

You can customize the script by editing these values at the top of `Code.gs`:

```javascript
const CONFIG = {
  SOURCE_SHEET_NAME: 'job-performance-details_combined_2',  // BigQuery sheet
  DEST_SHEET_NAME: 'job_data_copy',                         // Regular sheet for API
  KEEP_HISTORY: true,                                        // Create backups?
  MAX_HISTORY: 3,                                            // How many backups to keep
  REFRESH_INTERVAL_MINUTES: 60                               // How often to sync (60 = hourly)
};
```

## Update the Dashboard App

Once the script is running, update your dashboard to use the new sheet:

1. Open `app.py` in your dashboard project
2. Find this line (around line 20):
   ```python
   DATA_SHEET_NAME = "job-performance-details_combined_2"
   ```
3. Change it to:
   ```python
   DATA_SHEET_NAME = "job_data_copy"
   ```
4. Remove or comment out the BigQuery configuration (lines 23-26)
5. Restart the dashboard

The dashboard will now read from the regular sheet copy that updates every hour!

## Monitoring

### Check Last Update Time
- Hover over cell A1 in the `job_data_copy` sheet
- The note shows when data was last copied

### View Execution Logs
1. In Apps Script, click **Executions** (clock icon) on the left sidebar
2. See history of all script runs
3. Click on any execution to see detailed logs

### Troubleshooting

**Script not running automatically?**
- Run `setupTrigger` again
- Check Apps Script > Triggers (clock icon) to verify trigger exists
- Check execution log for errors

**"Source sheet not found" error?**
- Verify the sheet name in CONFIG matches exactly
- Sheet names are case-sensitive

**Data not updating?**
- BigQuery sheets refresh on their own schedule (every 3-4 hours typically)
- This script copies whatever is currently in the BigQuery sheet
- To force BigQuery refresh, click "Refresh options" > "Refresh now" in the BigQuery toolbar

**Permission errors?**
- Re-run the authorization process
- Make sure you're logged in with the right Google account

## Advantages of This Approach

✅ **Fully Automated** - No manual copying needed
✅ **No Special Permissions** - Works with standard Google Sheets access
✅ **Reliable** - Uses standard Sheets API that works with regular sheets
✅ **Backup History** - Keeps previous copies in case you need to rollback
✅ **Simple** - No BigQuery permissions or cloud configuration needed
✅ **Free** - Uses Google Apps Script free tier

## Next Steps

After setting this up:

1. ✅ Verify `job_data_copy` sheet exists and has data
2. ✅ Update `app.py` to use `DATA_SHEET_NAME = "job_data_copy"`
3. ✅ Restart your dashboard
4. ✅ Test that data loads correctly

The dashboard should now work perfectly!
