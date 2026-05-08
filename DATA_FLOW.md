# Data Flow: Job Performance Dashboard

How data moves from external sources to dashboard display. Every step, field, and fallback documented from the verified production pipeline.

---

## Pipeline at a glance

```
EXTERNAL SOURCES                        BIGQUERY TABLES                      STREAMLIT APP
================                        ===============                      =============

GA4 Events (KING)                       job_performance_                     app.py / app_v2.py
  jobsgopublic remote BQ     ──Step 1──>  details_combined                     │
                                              │                                │
XML Feeds (3 feeds)          ──Step 2──>  job_metadata ◄── CSV Export          │
                                              │            (manual backfill)   │
HQ Addresses lookup          ─Step 2.5─>  job_metadata                         │
                                          (adds hq_region)                     │
                                              │                                │
                                         ┌────┴────┐                           │
                                         │  Step 3 │                           │
                                         │  JOIN:  │                           │
                                         │  events │                           │
                                         │ +meta   │                           │
                                         │ +feeds  │                           │
                                         │ +vloc   │                           │
                                         └────┬────┘                           │
                                              │                                │
                                    job_performance_enriched                    │
                                              │                                │
                                         ┌────┴────┐                           │
                                         │  Step 4 │                           │
                                         │ GROUP BY│                           │
                                         └──┬─┬─┬──┘                           │
                                            │ │ │                              │
               dashboard_vacancy_summary ◄──┘ │ └──► dashboard_media_summary   │
               dashboard_daily_totals    ◄────┘                                │
                                            │                                  │
                                            └──────── load_all_data() ─────────┘
                                                             │
                                                      Python transforms
                                                      (5-6 steps)
                                                             │
                                                      Dashboard tabs
                                                      (3 prod / 7 dev)
```

---

## 1. External Sources

### KING: GA4 Events

The only source of **event data** (user interactions). Everything else enriches vacancy metadata.

| Attribute | Value |
|-----------|-------|
| **Remote table** | `jobsgopublic.Datastudio_scheduled_data_combined.Job-performance-detaile_combined` |
| **Local table** | `site-monitoring-421401.job_data_export.job_performance_details_combined` |
| **Grain** | One row per user interaction |
| **Event types** | `job_visit` (page view), `job_apply_start` (apply click) |
| **Sync** | Daily 06:00 UTC, 5-day lookback window |

**33 raw fields:**

| Category | Fields |
|----------|--------|
| IDs | `entity_id`, `entity_type`, `entity_subtype`, `owner_id`, `organization_id` |
| Event | `event_name`, `event_date` (YYYYMMDD), `hour_of_day`, `Events` |
| Vacancy | `title`, `organization_name`, `application_type`, `occupations`, `regions`, `employment_types`, `upgrades` |
| ATS | `importer_ID`, `ats_vacancy_number`, `ats_account_number` |
| Traffic | `source`, `medium`, `campaign`, `page_referrer`, `page_location` |
| Salary | `salary_currency`, `salary_low`, `salary_high` |
| Device | `device`, `operating_system`, `browser` |
| User | `current_user_id`, `user_role`, `site` |

### Supplementary 1: XML Feeds

Three feeds providing vacancy metadata for feed-sourced jobs.

| Feed | URL | Importer ID |
|------|-----|-------------|
| Scrape | `storage.googleapis.com/.../jgp_scraping_feed.xml` | 1 |
| Civil Service | `storage.googleapis.com/.../civil_service_jobs_uk.xml` | 5 |
| ATS | `storage.googleapis.com/.../jgp_ats_feed.xml` | 2 |

**Field mapping from feeds to `job_metadata`:**

| Feed field | job_metadata field | Notes |
|------------|-------------------|-------|
| `id` (hash) | `external_id` | Primary match key |
| `title` | `title` | |
| `organization_id` | `organization_id` | Scrape/ATS: from feed; Civil Service: jobiqo_id |
| `organization_name` | `organization_profile_name` | Scrape/ATS only |
| `job_location` / `location` | `locations` | |
| `working_pattern` | `employment_type` | |
| `category` | `occupational_fields` | |
| `occupation` | `category` | |
| `contract_type` | `contract_type` | |
| `start_date` | `publishing_date` | |
| `close_date` | `expiration_date` | |
| salary fields | `min_salary`, `max_salary`, `salary_exact`, `currency_code`, `salary_unit`, `salary_free_text` | |

**Behaviour:** Upsert -- inserts new rows, updates existing ones by `external_id`. Also marks jobs removed from feeds as unpublished. Records latest snapshot in `feed_jobs_latest`.

### Supplementary 2: Jobiqo CSV Export (manual)

Periodic manual upload via `scripts/upload_csv_export.py`.

- **Match keys:** `external_id` (primary), then `entity_id` (secondary)
- **Strategy:** Fill-blanks-only -- never overwrites existing feed data
- **Always backfills:** `entity_id` (the Jobiqo internal ID)
- **CSV-only fields:** `employer_type`, `original_publishing_date`
- **Column mapping:** `job_id` -> `entity_id`, `External ID` -> `external_id`, strips `N_` prefix from external_id

### Supplementary 3: Google Sheet (one-time setup, NOT daily)

- Sheet ID: `1eREp6EfdS4Tm4c-GUZQ4GdFH1LFZfBpx20ZbkSTiyZE`
- Was used once to initially populate `job_metadata` via `scripts/load_from_sheets.sql`
- **Not part of the daily pipeline** -- the sheet was the original source before feeds were set up

### Lookup Tables

| Table | Location | Purpose | How populated |
|-------|----------|---------|---------------|
| `client_hq_addresses` | BigQuery | org_id/name -> hq_region, hq_county | Manual upload of client addresses |
| `vacancy_locations` | BigQuery | entity_id -> exploded UK regions (one row per location) | Built from `job_metadata.locations` + `location_lookup` |
| `location_lookup` | BigQuery + CSV (16K rows) | town/city -> country, county, region | One-time upload from `location_lookup_with_regions.csv` |
| `importer_mapping.csv` | Local file (6 rows) | importer_ID -> name | Manual, checked into repo |
| `feed_jobs_latest` | BigQuery | Latest snapshot of each XML feed | Written by `sync_feeds.py` |

---

## 2. Daily Pipeline

**Orchestrator:** `scripts/daily_refresh.py`
**Schedule:** `.github/workflows/daily-refresh.yml` -- cron `0 6 * * *` (06:00 UTC daily)
**Can also be run manually:** `python scripts/daily_refresh.py` or `--dry-run`

### Step 1: Sync GA4 Events

**Script:** `scripts/incremental_sync_combined.sql`
**Pipeline behaviour:** ABORT if fails

```
Source: jobsgopublic remote table
  |
  | DELETE last 5 days from local table
  | INSERT last 5 days from source
  v
Target: job_performance_details_combined
```

Why 5 days? GA4 events can arrive late. The delete+reinsert window catches stragglers while being idempotent (safe to re-run).

### Step 2: Sync XML Feeds

**Script:** `scripts/sync_feeds.py`
**Pipeline behaviour:** WARNING on failure, continues with existing data

```
3 XML feeds (Scrape, Civil Service, ATS)
  |
  | Parse XML, map fields
  | Upsert into job_metadata by external_id
  | Mark removed jobs as unpublished
  | Record snapshot in feed_jobs_latest
  v
Target: job_metadata, feed_jobs_latest
```

### Step 2.5: Enrich from HQ Addresses

**Script:** `scripts/enrich_from_hq.sql`
**Pipeline behaviour:** WARNING on failure, continues with existing data

```
job_metadata  +  client_hq_addresses
  |
  | Pass 1: Match on organization_id
  |   -> Sets hq_region, hq_county
  |   -> Fills org_name if blank
  |
  | Pass 2: Match on organization_profile_name (case-insensitive)
  |   -> For vacancies still without HQ data after pass 1
  |   -> Sets hq_region, hq_county
  |   -> Fills organization_id if blank
  v
Target: job_metadata (hq_region, hq_county columns updated)
```

**Constraints:**
- Only targets single-location vacancies (no pipe `|` in `locations` field)
- Fill-blanks-only -- never overwrites existing `hq_region`

### Step 3: Build Enriched Table

**Script:** `scripts/refresh_enriched_table.sql`
**Pipeline behaviour:** ABORT if fails

This is where GA4 events get joined with all metadata. CREATE OR REPLACE -- full rebuild each day.

```
job_performance_details_combined (GA4 events)
  |
  |  LEFT JOIN job_metadata ON entity_id
  |  LEFT JOIN feed_jobs_latest ON external_id  (for importer_name when ID=-1)
  |  LEFT JOIN vacancy_locations ON entity_id   (STRING_AGG distinct regions)
  v
Target: job_performance_enriched
  - Partitioned by event_date_parsed
  - Clustered by entity_id_str, event_date_parsed
```

**Field priority logic (GA4 is king, metadata fills blanks):**

For overlapping fields, the SQL uses this pattern:
```sql
IF(events.field IS NOT NULL AND TRIM(events.field) NOT IN ('', '(none)'),
   events.field,
   metadata.field
) as field
```

This applies to: `title`, `organization_name`, `organization_id`, `occupational_fields`, `employment_type`, `min_salary`, `max_salary`, `currency_code`.

**Importer name resolution:**
```sql
CASE
  WHEN importer_ID = 1  THEN 'Scrape'
  WHEN importer_ID = 2  THEN 'ATS feed'
  WHEN importer_ID = 5  THEN 'Civil Service'
  WHEN importer_ID = 6  THEN 'Backfill'
  WHEN importer_ID = -1 AND feed.feed_name IS NOT NULL THEN feed.feed_name
  ELSE 'Unknown/Other'
END
```

**Region resolution:**
```sql
COALESCE(metadata.hq_region, vloc.uk_regions_all)    as uk_regions_all
COALESCE(metadata.hq_region, vloc.primary_uk_region)  as primary_uk_region
COALESCE(metadata.hq_county, vloc.primary_town_city)  as primary_town_city
```
HQ address wins. Vacancy locations (parsed from `locations` field) is fallback.

**Metadata-only fields** (no GA4 equivalent, come straight from `job_metadata`):
`workflow_state`, `category`, `contract_type`, `employer_type`, `publishing_date`, `expiration_date`, `original_publishing_date`, `locations`, `salary_free_text`, `salary_exact`, `salary_unit`

### Step 4: Build Aggregated Tables

**Script:** `scripts/create_aggregated_tables.sql`
**Pipeline behaviour:** ABORT if fails

Reduces ~570K event rows (90 days) to ~20K vacancy rows + ~365 daily rows.

**Table 1: `dashboard_vacancy_summary`** -- one row per vacancy

```
job_performance_enriched
  |
  | WHERE event_name IN ('job_visit', 'job_apply_start')
  | GROUP BY entity_id_str
  v
Fields:
  entity_id_str
  first_event_date     = MIN(event_date_parsed)
  last_event_date      = MAX(event_date_parsed)
  clicks               = COUNTIF(event_name = 'job_visit')
  applies              = COUNTIF(event_name = 'job_apply_start')
  title                = ANY_VALUE(title)
  organization_name    = ANY_VALUE(organization_name)
  uk_regions           = ANY_VALUE(uk_regions_all)
  primary_uk_region    = ANY_VALUE(primary_uk_region)
  occupational_fields  = ANY_VALUE(occupational_fields)
  importer_ID          = ANY_VALUE(importer_ID)
  importer_name        = ANY_VALUE(importer_name)
  workflow_state       = ANY_VALUE(workflow_state)
  upgrades             = ANY_VALUE(upgrades)
  start_date           = ANY_VALUE(publishing_date)
  end_date             = ANY_VALUE(expiration_date)
  category             = ANY_VALUE(category)
  contract_type        = ANY_VALUE(contract_type)
  employment_type      = ANY_VALUE(employment_type)
```

**Table 2: `dashboard_daily_totals`** -- one row per day

```
job_performance_enriched
  |
  | WHERE event_name IN ('job_visit', 'job_apply_start')
  | GROUP BY event_date_parsed
  v
Fields:
  event_date           = event_date_parsed
  clicks               = COUNTIF(event_name = 'job_visit')
  applies              = COUNTIF(event_name = 'job_apply_start')
  active_vacancies     = COUNT(DISTINCT entity_id_str)
```

**Table 3: `dashboard_media_summary`** -- one row per vacancy + traffic source

```
job_performance_enriched
  |
  | WHERE event_name IN ('job_visit', 'job_apply_start')
  | GROUP BY entity_id_str, importer_ID, source, medium, campaign
  v
Fields:
  entity_id_str, importer_ID
  importer_name        = ANY_VALUE(importer_name)
  source, medium, campaign
  clicks               = COUNTIF(event_name = 'job_visit')
  applies              = COUNTIF(event_name = 'job_apply_start')
```

---

## 3. App-Level Data Loading

### Production app (`app.py`) -- 2 queries

| Query | Table | Filter | Cache |
|-------|-------|--------|-------|
| Vacancy summary | `dashboard_vacancy_summary` | `WHERE last_event_date >= cutoff` | 4h TTL |
| Daily totals | `dashboard_daily_totals` | `WHERE event_date >= cutoff` | 4h TTL |

Returns: `(vacancy_df, daily_df)`

### Development app (`app_v2.py`) -- 3 queries + 1 extra

| Query | Table | Filter | Cache |
|-------|-------|--------|-------|
| Vacancy summary | `dashboard_vacancy_summary` | `WHERE last_event_date >= cutoff` | 4h TTL |
| Daily totals | `dashboard_daily_totals` | `WHERE event_date >= cutoff` | 4h TTL |
| Media summary | `dashboard_media_summary` | None (full table) | 4h TTL |
| Launch timing | `job_performance_enriched` (direct) | `WHERE event_date_parsed >= cutoff` | 4h TTL |

Returns: `(vacancy_df, daily_df, media_df)` + separate `launch_timing_df`

### Importer mapping (both apps)

Loaded from `importer_mapping.csv` with 5-minute cache:
```
1  -> Scrape
2  -> ATS feed
5  -> Civil Service
6  -> Backfill
-1 -> Unknown/Other
```

---

## 4. Python Transformation Chain

Applied sequentially after loading. Both apps use the same order (steps 1-5). Step 6 is v2-only.

### Step 1: `prepare_enriched_data(df)` -- `data/processing.py:259`

Renames `entity_id_str` -> `entity_id` for dashboard compatibility.

### Step 2: `apply_importer_mapping(df, mapping)` -- `data/processing.py:6`

Fills blank importer names with cascading fallbacks:

```
BigQuery importer_name (from enriched table CASE statement)
  |
  | If NULL or blank:
  v
CSV mapping (importer_mapping.csv)
  |
  | If still unmapped:
  v
"ID: {importer_id_str}"
  |
  | If no importer_ID at all:
  v
"Unknown"
```

### Step 3: `parse_upgrades(df)` -- `data/processing.py:34`

```
Input:  upgrades = "Featured|Highlight|Bump"
Output: upgrades_list = ["Featured", "Highlight", "Bump"]

Input:  upgrades = NaN
Output: upgrades_list = []
```

### Step 4: `parse_dates_in_jobiqo(df)` -- `data/processing.py:281`

Converts four columns from strings to timezone-naive datetimes:
- `first_event_date`
- `last_event_date`
- `start_date` (publishing_date)
- `end_date` (expiration_date)

Uses `pd.to_datetime(errors='coerce', utc=True).dt.tz_localize(None)` -- invalid dates become NaT.

### Step 5: `add_occupation_column(df)` -- `data/processing.py:270`

```
Input:  occupational_fields = "Social Care|Health|Education"
Output: occupation = "Social Care"  (first value, title-cased)

Input:  occupational_fields = NaN
Output: occupation = "Unknown"
```

### Step 6 (v2 only): `apply_media_categories(media_df)` -- `data/processing.py:247`

Classifies each source/medium/campaign combination into one of 20 traffic channels. Applied to `media_df` for the Client Report tab.

**20 categories in priority order:**

| # | Category | Key rule |
|---|----------|----------|
| 1 | Google Jobs | source contains "google_jobs_apply" |
| 2 | Client Career Page | ATS subdomain `.jgp.co.uk` or applyforthis.com |
| 3 | AI Chatbot | chatgpt.com, copilot.com, claude.ai, perplexity, etc. |
| 4 | Direct | source="(direct)" AND medium="(none)" |
| 5 | Email / Job Alerts | medium="email" or source="job_alert" or sendgrid |
| 6 | Paid Search | medium in (cpc,ppc) with Google/Bing/Microsoft source |
| 7 | Audio / Streaming | medium="audio" |
| 8 | LinkedIn Job Slots | medium in (job-slot, job-board) |
| 9 | Social Media (Paid) | social medium WITH campaign name |
| 10 | Social Media (Organic) | social medium WITHOUT campaign name |
| 11 | Job Aggregator | talent.com, jobrapido, appcast, idibu |
| 12 | Indeed | source or campaign = "indeed" |
| 13 | JGP Partner Site | 13 specific partner domains |
| 14 | Other Job Board | totaljobs, adzuna, ziprecruiter, etc. |
| 15 | Niche / Sector Job Board | artsjobs, healthcareers, etc. |
| 16 | Social Media (Organic) | facebook, linkedin, instagram, reddit, etc. |
| 17 | School Website | *.sch.uk domains |
| 18 | University / Careers Service | *.ac.uk domains + career portals |
| 19 | Government / Council | *.gov.uk domains |
| 20 | Organic Search | Google, Bing, Yahoo with medium="organic" |
| -- | Referral (Other) | Everything else |

---

## 5. Backfill Priority Table

How each field resolves when the primary source is blank.

| Field | Primary (king) | Fallback 1 | Fallback 2 | Default |
|-------|---------------|------------|------------|---------|
| **title** | GA4 `events.title` | `job_metadata.title` | -- | NULL |
| **organization_name** | GA4 `events.organization_name` | `job_metadata.organization_profile_name` | -- | NULL |
| **organization_id** | GA4 `events.organization_id` (if not 0/-1) | `job_metadata.organization_id` | -- | NULL |
| **occupational_fields** | GA4 `events.occupations` | `job_metadata.occupational_fields` | -- | NULL |
| **employment_type** | GA4 `events.employment_types` | `job_metadata.employment_type` | -- | NULL |
| **min_salary** | GA4 `events.salary_low` (if not 0) | `job_metadata.min_salary` | -- | NULL |
| **max_salary** | GA4 `events.salary_high` (if not 0) | `job_metadata.max_salary` | -- | NULL |
| **currency_code** | GA4 `events.salary_currency` | `job_metadata.currency_code` | -- | NULL |
| **uk_regions_all** | `job_metadata.hq_region` | `vacancy_locations` (STRING_AGG) | -- | NULL |
| **primary_uk_region** | `job_metadata.hq_region` | `vacancy_locations` (ANY_VALUE) | -- | NULL |
| **importer_name** | CASE on `importer_ID` (1/2/5/6) | `feed_jobs_latest.feed_name` (for -1) | CSV mapping -> "Unknown" | "Unknown" |
| **occupation** (app) | First value from `occupational_fields` | -- | -- | "Unknown" |
| **workflow_state** | `job_metadata` only | -- | -- | NULL |
| **category** | `job_metadata` only | -- | -- | NULL |
| **contract_type** | `job_metadata` only | -- | -- | NULL |
| **employer_type** | `job_metadata` only | -- | -- | NULL |
| **start_date** | `job_metadata.publishing_date` | -- | -- | NULL |
| **end_date** | `job_metadata.expiration_date` | -- | -- | NULL |

**"Blank" means:** NULL, empty string, or the GA4 placeholder `(none)`.

---

## 6. Derived Metrics

Calculated at display time from the loaded DataFrames. Not stored in BigQuery.

### Core metrics (`data/calculations.py`)

| Metric | Formula |
|--------|---------|
| Total Vacancies | `len(df)` |
| Total Clicks | `SUM(clicks)` |
| Total Applies | `SUM(applies)` |
| Apply/Click Ratio | `(total_applies / total_clicks) * 100` |
| Mean Clicks/Vacancy | `total_clicks / num_vacancies` |
| Mean Applies/Vacancy | `total_applies / num_vacancies` |
| Median Clicks/Vacancy | `MEDIAN(clicks)` |
| Median Applies/Vacancy | `MEDIAN(applies)` |

### Quartile breakdown

Vacancies ranked by clicks, split into 3 buckets:
- **Top 25%:** clicks >= Q3 threshold
- **Middle 50%:** clicks between Q1 and Q3
- **Bottom 25%:** clicks < Q1 threshold

Each bucket gets: vacancies, total clicks, total applies, apply/click %, clicks/vacancy, applies/vacancy.

### Outlier removal (IQR method)

Used in certain visualisations to remove extreme values:
```
Lower bound = Q1 - (1.5 * IQR)
Upper bound = Q3 + (1.5 * IQR)
```

### v2 tab-specific calculations

| Metric | Used in | Logic |
|--------|---------|-------|
| Sector benchmarks | Sales Intelligence | Mean/median clicks and applies per occupation (min 5 vacancies) |
| Upgrade ROI | Sales Intelligence | % uplift of each upgrade vs "No Upgrade" baseline, by occupation |
| Client scorecards | Sales Intelligence | Client avg vs sector avg, per occupation |
| Underperformer alerts | Sales Intelligence | Published vacancies below 25th percentile for their occupation |
| Launch timing curves | Launch Timing | Per-vacancy per-day event counts from enriched table, offset from first event |
| Benchmark comparison | Client Report | Client vacancy performance vs platform-wide averages by occupation |
| Media channel performance | Client Report | Avg views/applies by traffic source category |
| Advertising ROI | Client Report | Cost per job/view/apply using user-entered annual spend |

---

## 7. Final Display

### Production app (`app.py`) -- 3 tabs

**Overview:**
- KPI cards (vacancies, clicks, applies, apply/click ratio)
- Quartile breakdown (Top 25%, Middle 50%, Bottom 25%)
- Daily trend chart (clicks, applies, active vacancies over time)
- Performance by Importer (grouped bar chart)
- Performance by Region (grouped bar chart, regions exploded from pipe-separated)
- Conversion Funnel (Vacancies -> Clicks -> Applies)

**Vacancy Performance:**
- Summary metrics row
- Full vacancy table: Title, Company, Job ID, Status, Start Date, End Date, Days Active, Region, Occupation, Importer, Upgrades, Clicks, Applies, Ratio %, Clicks/Day, Applies/Day
- CSV download

**Compare:**
- Side-by-side filtered comparison (Side A vs Side B)
- 6 comparison metrics with % change
- Grouped bar chart

### Development app (`app_v2.py`) -- adds 4 more tabs

**Deep Dive:**
- Benchmark table grouped by selectable dimension (Importer, Region, Occupation, Company)
- Region x Importer performance heatmap (selectable metric)
- CSV download

**Sales Intelligence:**
- Upgrade ROI tables by occupation (absolute values or % uplift mode)
- Client scorecards with per-occupation sector comparison
- Underperforming vacancy alerts (below 25th percentile)
- Sector benchmark reference table

**Launch Timing:**
- Performance curve chart (Day 0-30, avg clicks/applies per vacancy)
- Performance by launch day of week (7 lines)
- First 7 days summary table
- Occupation filter

**Client Report:**
- Client/importer selector + date range
- Optional cost data entry (annual spend, rate card price)
- Benchmarking scatter plot (views/applies difference from benchmark)
- Benchmarking summary with KPI cards and bar charts
- Job postings by type chart
- Advertising ROI (if spend entered): cost per job/view/apply, cost vs rate card
- Media performance table and chart (by traffic channel category)
- PDF export (6-page report with embedded charts)

---

## 8. Available Filters

Applied via `data/filters.py` before any tab renders.

| Filter | Logic | Field used |
|--------|-------|------------|
| Date Range | Overlap: `first_event_date <= end AND last_event_date >= start` | `first_event_date`, `last_event_date` |
| Importer | Multiselect exact match | `importer_name` |
| Company | Multiselect exact match | `organization_name` |
| Region | Set intersection on pipe-separated values; hierarchical (Country -> Region) | `uk_regions` |
| Occupation | Multiselect exact match | `occupation` (derived) |
| Upgrades | ANY match -- vacancy included if any selected upgrade is present | `upgrades_list` (derived) |
| Job Title | Case-insensitive substring search | `title` |

---

## 9. Scripts Reference

Which scripts are production, which are one-time setup, which are superseded.

### Production (run daily by `daily_refresh.py`)

| Script | Step | Purpose |
|--------|------|---------|
| `incremental_sync_combined.sql` | 1 | Sync GA4 events (5-day lookback) |
| `sync_feeds.py` | 2 | Update job_metadata from XML feeds |
| `enrich_from_hq.sql` | 2.5 | Add hq_region/county from HQ addresses |
| `refresh_enriched_table.sql` | 3 | Build enriched table (full rebuild) |
| `create_aggregated_tables.sql` | 4 | Build 3 dashboard summary tables |

### Manual (run as needed)

| Script | Purpose |
|--------|---------|
| `upload_csv_export.py` | Backfill job_metadata from Jobiqo CSV export |

### One-time setup (not scheduled)

| Script | Purpose | Status |
|--------|---------|--------|
| `load_from_sheets.sql` | Initial load from Google Sheet into job_metadata | Done |
| `create_table.sql` | Create job_metadata schema | Done |
| `create_job_metadata_table.py` | Python setup for job_metadata | Done |
| `partition_table.sql` | Partition job_performance_details_combined | Done |
| `load_location_lookup.sql` | Load location_lookup from CSV | Done |
| `create_location_lookup_table.sql` | Create location_lookup schema | Done |
| `upload_location_lookup_to_bq.py` | Upload location CSV to BigQuery | Done |
| `add_regions_to_lookup.py` | Add region data to location lookup | Done |
| `create_county_to_region_mapping.py` | Create county -> region CSV | Done |
| `process_postcode_lookup.py` | Process postcode data | Done |
| `upload_job_export_to_bq.py` | Early CSV upload script | Done |

### Superseded (not used)

| Script | Replaced by | Why |
|--------|-------------|-----|
| `create_enriched_table.sql` (Jan 21) | `refresh_enriched_table.sql` | No HQ enrichment, no feed backfill, no vacancy_locations |
| `create_enriched_table_with_regions.sql` (Jan 21) | `refresh_enriched_table.sql` | Used location_lookup direct join -- abandoned in favour of HQ address approach |
| `updated_bigquery_query.sql` | Nothing | Points to wrong project (`job-board-analytics-444710`), never used |
| `fix_blank_country_region.sql` | Superseded by HQ enrichment | Was a one-off patch for vacancy_locations gaps |
| `fix_data_types.sql` | N/A | One-off data type corrections, not needed again |

---

## 10. How to Rebuild From Scratch

If you needed to recreate the entire pipeline:

1. **Create tables:** Run `create_table.sql`, `create_location_lookup_table.sql`, `partition_table.sql`
2. **Load lookup data:** Upload `location_lookup_with_regions.csv`, `client_hq_addresses`, `importer_mapping.csv`
3. **Initial metadata load:** Run `load_from_sheets.sql` or `upload_csv_export.py` to populate `job_metadata`
4. **Run daily pipeline:** `python scripts/daily_refresh.py` -- this runs all 5 steps in order
5. **Start app:** `streamlit run app.py` (production) or `streamlit run app_v2.py` (development)

For ongoing operation, only step 4 runs daily (automated via GitHub Actions).
