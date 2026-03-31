"""
Add official UK regions to the location lookup by mapping counties to regions
"""

import pandas as pd

print("=" * 80)
print("Adding UK Regions to Location Lookup")
print("=" * 80)

# Load the location lookup
print("\n1. Loading location lookup...")
df_locations = pd.read_csv('/Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard/location_lookup.csv')
print(f"   ✅ Loaded {len(df_locations):,} towns/cities")

# Load the county to region mapping
print("\n2. Loading county-to-region mapping...")
df_mapping = pd.read_csv('/Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard/county_to_region_mapping.csv')
print(f"   ✅ Loaded {len(df_mapping)} county mappings")

# Join to add UK region
print("\n3. Joining to add UK regions...")
df_enriched = df_locations.merge(
    df_mapping,
    left_on='region',  # This is the county from the postcode file
    right_on='county',
    how='left'
)

# Select and rename columns for clarity
df_enriched = df_enriched[['country_code', 'town_city', 'country', 'region', 'uk_region']]
df_enriched = df_enriched.rename(columns={
    'region': 'county',
    'uk_region': 'region'
})

# Check how many have regions
matched = df_enriched['region'].notna().sum()
total = len(df_enriched)
match_rate = (matched / total) * 100

print(f"   ✅ Matched {matched:,} / {total:,} towns ({match_rate:.1f}%)")

# Show unmatched counties
if df_enriched['region'].isna().any():
    unmatched = df_enriched[df_enriched['region'].isna()]
    unmatched_counties = unmatched['county'].value_counts()
    print(f"\n⚠️  Warning: {len(unmatched_counties)} unique counties not mapped:")
    print(unmatched_counties.head(10))

# Save enriched file
output_file = '/Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard/location_lookup_with_regions.csv'
df_enriched.to_csv(output_file, index=False)

print(f"\n4. ✅ Saved enriched lookup to: {output_file}")

# Show statistics
print("\n" + "=" * 80)
print("Statistics:")
print("=" * 80)
print("\nTowns by Region:")
print(df_enriched['region'].value_counts())

print("\n\nSample data:")
print(df_enriched.head(20))

print("\n" + "=" * 80)
print("✅ COMPLETE!")
print("=" * 80)
print("\nNext steps:")
print("1. Upload location_lookup_with_regions.csv to Google Sheets")
print("2. Use it in BigQuery to enrich job locations")
