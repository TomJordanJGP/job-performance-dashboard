# Jobiqo Export Setup

## What's New

The dashboard now includes:
1. **Vacancy View** - Aggregated view with clicks, applies, and ratios
2. **UK Region Extraction** - Automatically extracts UK regions from addresses
3. **Jobiqo Export Integration** - Merges start/end dates from daily export

## Setup Steps

### 1. Create Jobiqo Export Sheet

1. Open your Google Sheet: https://docs.google.com/spreadsheets/d/1XvVxCV8oo-qwZOwdHfsqMTIljHQ1gHISfZoIvVI8i7U/edit
2. Create a new tab (click + at bottom)
3. Name it exactly: **`jobiqo_export`**
4. Add these columns in the first row:
   - `entity_id` (or whatever matches your job ID column)
   - `start_date`
   - `end_date`
   - Any other columns from Jobiqo export you want to include

### 2. Upload Daily Export

Every morning, when you get the Jobiqo CSV export:

1. Open the CSV file
2. Copy all the data (including headers)
3. Go to the `jobiqo_export` sheet in your Google Sheet
4. Paste, replacing the old data

**OR** you can automate this:
- Use Google Sheets' built-in CSV import: `File` → `Import` → select CSV
- OR use a script to auto-upload the CSV

### 3. Column Mapping

Make sure these columns exist in your Jobiqo export and match:

| Jobiqo Export Column | Dashboard Uses For |
|---------------------|-------------------|
| `entity_id` or `job_id` | Joining with BigQuery data |
| `start_date` | Vacancy view - Start Date column |
| `end_date` | Vacancy view - End Date column |
| `title` (optional) | Better job titles |

## How It Works

1. **BigQuery Data** (945K rows) - All events (clicks, applies, etc.)
2. **Jobiqo Export** (smaller, ~few thousand vacancies) - Metadata about each vacancy
3. **Dashboard** - Joins them on `entity_id`/`job_id`

## Vacancy View Features

The new Vacancy View shows:

| Column | Description |
|--------|-------------|
| Title | Job title |
| Organisation | Hiring organization |
| Job ID | Unique identifier |
| Start Date | From Jobiqo export |
| End Date | From Jobiqo export |
| Location (Region) | UK region (auto-extracted from address) |
| Total Clicks | Count of `job_visit` events |
| Total Apply Start | Count of `job_apply_start` events |
| Apply Click Ratio (%) | (Applies ÷ Clicks) × 100 |

## UK Region Extraction

The dashboard automatically extracts UK regions from addresses using:
- **Postcode matching** (e.g., "SW1A" → London)
- **City/area matching** (e.g., "Manchester" → North West)

Supported regions:
- London
- South East
- South West
- East of England
- East Midlands
- West Midlands
- Yorkshire and the Humber
- North West
- North East
- Scotland
- Wales
- Northern Ireland

## Testing

After setup, run the dashboard:

```bash
cd /Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard
./run.sh
```

Check:
1. ✅ Overview tab loads with UK regions
2. ✅ Vacancy View tab shows aggregated data
3. ✅ Start/End dates appear (if Jobiqo export is loaded)
4. ✅ Regions show as UK region names (not full addresses)

## Troubleshooting

### "Could not load Jobiqo export"
- Check the sheet is named exactly `jobiqo_export`
- Verify service account has access to the Google Sheet

### Start/End dates showing "N/A"
- Jobiqo export sheet hasn't been created yet (normal for first run)
- Column names don't match - check they're exactly `start_date` and `end_date`

### Regions showing "Unknown"
- Address format doesn't match UK patterns
- Address column is empty
- You can manually add region column to your data if needed

### Filter error
- Fixed! We now use `create_bqstorage_client=False` to avoid permission issues
- Dashboard uses standard REST API instead of BigQuery Storage API

## Daily Workflow

1. Morning: Receive Jobiqo CSV export
2. Copy/paste into `jobiqo_export` sheet
3. Dashboard automatically picks up new data (5-minute cache)
4. Generate reports from Vacancy View

Enjoy your new vacancy-level reporting! 🎉
