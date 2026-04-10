# Region Fallback — Location Gap Fix

## Code Changes (Done)
- [x] Generate location_review.xlsx with 310 unmatched towns + auto-suggested regions (99.2% vacancy coverage)
- [x] Create `scripts/generate_location_review.py` — one-time review spreadsheet generator
- [x] Create `scripts/sync_location_additions.sql` — Sheet → location_lookup MERGE
- [x] Add Tier 4 direct HQ lookup to `scripts/refresh_enriched_table.sql` (both Part 1 + Part 2)
- [x] Create `scripts/export_unmatched_to_sheet.py` — detect + append unmatched towns to Sheet
- [x] Wire new steps into `scripts/daily_refresh.py` (steps 2.1 + 6)

## Manual Steps (User)
- [ ] Upload `location_review.xlsx` to Google Sheets
- [ ] Review suggested regions, correct if needed, mark `done` column for approved rows
- [ ] Update `SHEET_ID` in `scripts/sync_location_additions.sql` (replace `REPLACE_WITH_SHEET_ID`)
- [ ] Update `SHEET_ID` in `scripts/export_unmatched_to_sheet.py` (or set `LOCATION_REVIEW_SHEET_ID` env var)
- [ ] Run `sync_location_additions.sql` in BigQuery to load approved rows into location_lookup
- [ ] Run full pipeline (`python scripts/daily_refresh.py`) and verify region completeness improvement
