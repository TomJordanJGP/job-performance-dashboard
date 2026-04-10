# Lessons Learned

## Environment

### Always use the project venv

The system Python does NOT have BigQuery or gspread installed. Always run scripts with:
```
venv/bin/python scripts/whatever.py
```
Not `python3 scripts/whatever.py`.

### gspread must be in requirements.txt

The `export_unmatched_to_sheet.py` script requires `gspread` and `google-auth-oauthlib`. These are installed in the venv but were initially missing from `requirements.txt`. Always check that new dependencies are added to requirements.txt when introduced.

## Google Sheets + BigQuery Integration

### Service account needs Editor access on Sheets

When a Google Sheet is used both as a BigQuery external table (read) AND written to by a Python script (gspread append), the service account needs **Editor** access on the Sheet — not just Viewer. Viewer is sufficient for BigQuery external table reads alone, but gspread `append_rows` requires write permissions.

### BigQuery needs Drive scope to read Google Sheets external tables

When a BigQuery client reads from a Google Sheets-backed external table, the service account credentials must include `https://www.googleapis.com/auth/drive.readonly` in addition to the BigQuery scope. Without it, you get "Permission denied while getting Drive credentials". This is configured in `daily_refresh.py` `get_client()`.

### BigQuery external table URIs need the full Google Sheets URL

The `uris` field in `CREATE EXTERNAL TABLE` takes the full `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit...` URL. The Python `gspread` client takes just the Sheet ID (the part between `/d/` and `/edit`). Don't confuse the two formats.

## Data Pipeline

### Location field format from Jobiqo

Jobiqo exports locations as `"State, City, CountryCode"` pipe-delimited for multi-location. Example: `"England, London, GB | England, Manchester, GB"`. The city (index 1 after comma split) is what gets matched against `location_lookup`. Many London borough towns (Romford, Wembley, etc.) aren't in the standard UK towns dataset and need to be added manually.

### enrich_from_hq.sql only covers job_metadata vacancies

The HQ enrichment script (`enrich_from_hq.sql`) runs UPDATE on `job_metadata`, so it only enriches vacancies that exist in that table. GA4-only vacancies (events with no metadata match) never get Tier 2 HQ enrichment. That's why Tier 4 was added as a direct JOIN in `refresh_enriched_table.sql`.

### Central government orgs are multi-site — don't force a single region

MoD, MoJ, UKHSA, ONS etc. have vacancies across the UK. Assigning them a single HQ region would be misleading. These are the remaining ~670 vacancies without a region and that's an acceptable gap unless/until their locations are properly parsed.

## Streamlit Cloud Deployment

### kaleido is pinned for a reason

`kaleido==0.2.1` is pinned in requirements.txt because newer versions break on Streamlit Cloud. Don't upgrade it.

### Don't add heavy dependencies without checking Streamlit Cloud compatibility

Always verify new dependencies work on Streamlit Cloud before adding. The deployment environment is Linux-based with limited system packages.
