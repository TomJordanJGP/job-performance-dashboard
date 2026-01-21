# Dashboard Filter Guide

## Understanding the Filters

### Company vs Organisation - What's the Difference?

**Company (`organization_name`)**
- Source: BigQuery table (your main event data)
- This is the organization name as recorded in your BigQuery events
- Contains the company information from when events (clicks, applies) were tracked
- May be in a different format or have different naming conventions

**Organisation (Jobiqo) (`organization_name_jobiqo`)**
- Source: Jobiqo daily export CSV file (`jobs-export.csv`)
- This is the organization name as it appears in the Jobiqo system
- Comes from the `organization_profile_name` column in the Jobiqo export
- May be more standardized or have the "official" organization name

**Why have both?**
Sometimes the organization names differ between systems due to:
- Different naming conventions
- Data entry variations
- System-specific formatting

**When to use which?**
- Use **Company** if you want to filter by how organizations appear in your event tracking data
- Use **Organisation (Jobiqo)** if you want to filter by the official organization names from Jobiqo
- You can use both filters together for more precise filtering

## Other Filters

### Importer
- Source: `importer_mapping.csv`
- Maps importer IDs to human-readable names:
  - 1 = Scrape
  - 2 = ATS feed
  - 5 = Civil Service
  - 6 = Backfill
- Tells you how the job vacancy was imported into the system

### Region
- Source: Extracted from `locations` column in `jobs-export.csv`
- Automatically extracts UK regions from job location addresses
- Handles multiple locations (separated by `|`)
- Falls back to "Unknown" if no UK postcode or city/county is found

### Date Range
- Source: `event_date` column in BigQuery
- Filters events by the date they occurred
- Default: Last 90 days (for performance)

## Comparison View - Apply Filters Button

⚠️ **Important:** Due to the large amount of data, filters in the Comparison view require you to click the **"🔄 Apply Filters"** button after making your selections.

**How it works:**
1. Select your filters on Side A
2. Click "🔄 Apply Filters" button under Side A filters
3. Select your filters on Side B
4. Click "🔄 Apply Filters" button under Side B filters
5. The metrics will update based on your applied filters

This prevents the dashboard from trying to recalculate metrics every time you change a filter option, which would be very slow with this much data.

## Tips

- **Start broad, then narrow:** Begin with fewer filters and add more to narrow down results
- **Use Comparison View for A/B testing:** Compare different time periods, regions, or importers
- **Check both Company and Organisation filters:** If you can't find an organization in one filter, try the other
- **Region "Unknown":** Indicates the job location couldn't be matched to a UK region (non-UK jobs, or unusual address format)
