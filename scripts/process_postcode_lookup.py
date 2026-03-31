"""
Process GB postcode file to create a Town/City to Region lookup table
Extracts columns: Country Code, Town/City, Country, Region
Removes duplicates to create a clean lookup for job locations
"""

import pandas as pd
import os

# Input and output paths
input_file = '/Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard/GB_full 2.txt'
output_file = '/Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard/location_lookup.csv'

print("=" * 80)
print("Processing GB Postcode Lookup File")
print("=" * 80)

# Read the tab-separated file
print(f"\nReading file: {input_file}")
df = pd.read_csv(
    input_file,
    sep='\t',
    header=None,
    names=['country_code', 'postcode', 'town_city', 'country', 'country_code_short',
           'region', 'col_g', 'district', 'district_code', 'lat', 'lon', 'accuracy'],
    dtype=str
)

print(f"✅ Loaded {len(df):,} postcodes")

# Select only the columns we need: A, C, D, F, G
# Note: Column G appears to be empty in the data, but including it as requested
df_selected = df[['country_code', 'town_city', 'country', 'region', 'col_g']].copy()

# Clean town/city names (remove extra whitespace)
df_selected['town_city'] = df_selected['town_city'].str.strip()

# Remove duplicates - keep first occurrence of each town/city
# This gives us a unique town -> region mapping
print(f"\nRemoving duplicate towns/cities...")
df_unique = df_selected.drop_duplicates(subset=['town_city'], keep='first')

print(f"✅ Reduced to {len(df_unique):,} unique towns/cities")

# Sort by town/city for easier lookup
df_unique = df_unique.sort_values('town_city')

# Rename columns for clarity
df_unique.columns = ['country_code', 'town_city', 'country', 'region', 'empty_col']

# Show sample of data
print("\nSample of processed data:")
print(df_unique.head(10))

# Save to CSV
print(f"\nSaving to: {output_file}")
df_unique.to_csv(output_file, index=False)

print(f"✅ Saved {len(df_unique):,} rows to {output_file}")

# Show statistics
print("\n" + "=" * 80)
print("Statistics:")
print("=" * 80)
print(f"Total unique towns/cities: {len(df_unique):,}")
print(f"Countries: {df_unique['country'].unique().tolist()}")
print(f"Number of regions: {df_unique['region'].nunique()}")
print("\nTop 10 regions by number of towns:")
print(df_unique['region'].value_counts().head(10))

print("\n" + "=" * 80)
print("✅ COMPLETE!")
print("=" * 80)
print("\nNext steps:")
print("1. Upload location_lookup.csv to Google Sheets")
print("2. Create BigQuery external table pointing to the sheet")
print("3. Use it to enrich job locations with regions")
