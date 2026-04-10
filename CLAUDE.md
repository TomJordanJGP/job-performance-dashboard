# Job Performance Dashboard — Project Instructions

Inherits from parent `../CLAUDE.md`. This file adds project-specific context.

## Environment Setup

### Python virtual environment

**Always use the venv** — the system Python is missing required packages.

```bash
# Activate (or prefix commands with venv/bin/python)
source venv/bin/activate

# Or run scripts directly:
venv/bin/python scripts/daily_refresh.py
```

### Required credentials

- `service_account.json` — Google Cloud service account key (gitignored, never commit)
  - Needs BigQuery Admin + Drive readonly scopes
  - Must have **Editor** access on any Google Sheet used as an external table or written to by gspread
  - The service account email is in the JSON under `client_email`

### Key dependencies (beyond requirements.txt)

- `gspread` — Google Sheets read/write (used by `export_unmatched_to_sheet.py`)
- `google-auth-oauthlib` — OAuth support for gspread
- `google-cloud-bigquery` — BigQuery client
- `openpyxl` — Excel read/write (used by analysis scripts)

Install all:
```bash
venv/bin/pip install -r requirements.txt gspread google-auth-oauthlib openpyxl
```

### Verify environment is working

```bash
venv/bin/python -c "from google.cloud import bigquery; import gspread; print('OK')"
```

## Project Structure

### Data pipeline (`scripts/`)

The daily refresh runs 9 steps in order. Run with:
```bash
venv/bin/python scripts/daily_refresh.py          # full run
venv/bin/python scripts/daily_refresh.py --dry-run # preview only
```

Pipeline order:
1. `incremental_sync_combined.sql` — Append new GA4 events
2. `sync_feeds.py` — Update job_metadata from XML feeds
3. `sync_location_additions.sql` — MERGE approved locations from Google Sheet into location_lookup
4. `refresh_vacancy_locations.sql` — Rebuild exploded location table
5. `enrich_from_hq.sql` — Backfill HQ region/county on job_metadata
6. `refresh_enriched_table.sql` — Rebuild enriched table (4-tier region fallback)
7. `create_aggregated_tables.sql` — Pre-compute dashboard summary tables
8. `create_reconciliation_tables.sql` — Rebuild missing_external_ids
9. `export_unmatched_to_sheet.py` — Detect + append unmatched towns to review Sheet

### Region resolution — 4-tier fallback

The `refresh_enriched_table.sql` resolves UK regions via:
1. **Tier 1:** Canonical region normalisation (`region_canonical` table)
2. **Tier 2:** HQ region from `job_metadata.hq_region` (via `enrich_from_hq.sql`)
3. **Tier 3:** Vacancy location lookup (`location_lookup` table, matched on town_city)
4. **Tier 4:** Direct `client_hq_addresses` JOIN at enriched table level

### Self-healing location review queue

- Google Sheet ID: `1YPfZMxK2Rdl91JjAKd60xtjNinDfBe0DHpa5euFwmDc`
- Pipeline appends new unmatched towns to the Sheet (step 9)
- User reviews, marks `done` column as `TRUE`
- Pipeline MERGEs approved rows into `location_lookup` (step 3)

### Dashboard app (`app.py`)

```bash
venv/bin/streamlit run app.py
```

### BigQuery project

- Project: `site-monitoring-421401`
- Dataset: `job_data_export`
- Location: `EU`

## Key files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit dashboard |
| `data/loader.py` | BigQuery data loading |
| `data/filters.py` | Region/org/date filtering |
| `data/regions.py` | Country → region hierarchy |
| `utils/region_parser.py` | UK region extraction from addresses |
| `scripts/daily_refresh.py` | Orchestrates the full pipeline |
| `scripts/refresh_enriched_table.sql` | Core enrichment query (4-tier regions) |
| `scripts/refresh_vacancy_locations.sql` | Explodes locations, joins lookup |
| `scripts/enrich_from_hq.sql` | HQ region/county backfill |
| `scripts/sync_location_additions.sql` | Sheet → location_lookup MERGE |
| `scripts/export_unmatched_to_sheet.py` | Unmatched town detection + Sheet append |
| `lessons.md` | Mistakes and fixes — read at start of every session |

## When modifying pipeline SQL

- Always test with `--dry-run` first
- After running, verify by querying the output table — don't assume success
- The enriched table and aggregated tables are fully rebuilt each run (CREATE OR REPLACE), not incremental
- BigQuery location is EU — queries must run in that region
