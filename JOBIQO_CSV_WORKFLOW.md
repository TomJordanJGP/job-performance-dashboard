# Jobiqo CSV Workflow

## Daily Workflow

Every morning when you receive the Jobiqo export CSV:

1. Save the CSV file as `jobs-export.csv`
2. Place it in the dashboard directory: `/Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard/`
3. If the dashboard is running, click "🔄 Refresh Data" in the sidebar (or just refresh your browser after 5 minutes)
4. The new data will be loaded automatically

## What Gets Merged

From the `jobs-export.csv`, the dashboard uses:

| CSV Column | Dashboard Uses As | Shows In |
|-----------|-------------------|----------|
| `job_id` | Joins with BigQuery `entity_id` | Job ID |
| `title` | Job title | Vacancy View - Title |
| `publishing_date` | Start date | Vacancy View - Start Date |
| `expiration_date` | End date | Vacancy View - End Date |
| `organization_profile_name` | Organization name | Vacancy View - Organisation |
| `locations` | Full location | (UK region extracted from this) |

## File Location

Make sure the file is at:
```
/Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard/jobs-export.csv
```

## Automatic Update Script (Optional)

If you want to automate this, you can create a script that:
1. Downloads/moves the CSV to the dashboard directory
2. Renames it to `jobs-export.csv`
3. Replaces the old one

Example bash script (`update-jobiqo.sh`):

```bash
#!/bin/bash

# Update Jobiqo export data
# Usage: ./update-jobiqo.sh /path/to/downloaded/export.csv

SOURCE_FILE="$1"
DEST_DIR="/Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard"
DEST_FILE="$DEST_DIR/jobs-export.csv"

if [ -z "$SOURCE_FILE" ]; then
    echo "Usage: $0 /path/to/export.csv"
    exit 1
fi

if [ ! -f "$SOURCE_FILE" ]; then
    echo "Error: File not found: $SOURCE_FILE"
    exit 1
fi

# Backup old file
if [ -f "$DEST_FILE" ]; then
    mv "$DEST_FILE" "$DEST_DIR/jobs-export-backup-$(date +%Y%m%d).csv"
    echo "✅ Backed up old export"
fi

# Copy new file
cp "$SOURCE_FILE" "$DEST_FILE"
echo "✅ Updated jobs-export.csv"
echo ""
echo "Dashboard will pick up the new data within 5 minutes"
echo "Or click 'Refresh Data' in the dashboard sidebar"
```

Make it executable:
```bash
chmod +x update-jobiqo.sh
```

Use it:
```bash
./update-jobiqo.sh ~/Downloads/jobiqo-export-2026-01-20.csv
```

## Data Freshness

- **BigQuery data**: Refreshed via your scheduled export (check your BigQuery schedule)
- **Jobiqo CSV**: Manual update (daily)
- **Dashboard cache**: 5 minutes (auto-refresh) or manual refresh button

## Troubleshooting

### "jobs-export.csv not found"
- File not in the correct directory
- File named differently (must be exactly `jobs-export.csv`)

### Start/End dates still showing "N/A"
- Check column names in CSV match: `publishing_date`, `expiration_date`
- CSV might have different date format
- No matching `job_id` between BigQuery and Jobiqo export

### Jobs not matching
- The `job_id` in Jobiqo CSV must match `entity_id` in BigQuery data
- Check a few examples to ensure they match

### Want to check what's loaded?
Add this to see what columns the CSV has:
```python
# In Python console or Jupyter
import pandas as pd
df = pd.read_csv('jobs-export.csv')
print(df.columns.tolist())
print(df.head())
```

## Benefits of CSV Approach

✅ **Simple** - Just replace a file
✅ **Fast** - No Google Sheets API calls
✅ **Flexible** - Easy to update anytime
✅ **Version Control** - Can keep backups with dates
✅ **No Permissions** - No Google Sheets access needed

Enjoy your automated reporting! 🎉
