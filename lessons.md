# Lessons Learned

## Google Sheets + BigQuery service account access

When a Google Sheet is used both as a BigQuery external table (read) AND written to by a Python script (gspread append), the service account needs **Editor** access on the Sheet — not just Viewer. Viewer is sufficient for BigQuery external table reads alone, but gspread `append_rows` requires write permissions.

## BigQuery needs Drive scope to read Google Sheets external tables

When a BigQuery client reads from a Google Sheets-backed external table, the service account credentials must include `https://www.googleapis.com/auth/drive.readonly` in addition to the BigQuery scope. Without it, you get "Permission denied while getting Drive credentials".
