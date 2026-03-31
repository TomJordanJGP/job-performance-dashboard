"""
Create a mapping from counties to official UK regions
Maps the counties in the postcode file to proper government regions
"""

import pandas as pd

# Define the county to region mapping
# Based on official UK government regions
county_to_region = {
    # ENGLAND - 9 Official Regions

    # North East
    'Durham': 'North East',
    'Northumberland': 'North East',
    'Tyne and Wear': 'North East',

    # North West
    'Cheshire': 'North West',
    'Cumbria': 'North West',
    'Greater Manchester': 'North West',
    'Lancashire': 'North West',
    'Merseyside': 'North West',

    # Yorkshire and The Humber
    'East Riding of Yorkshire': 'Yorkshire and The Humber',
    'North Yorkshire': 'Yorkshire and The Humber',
    'South Yorkshire': 'Yorkshire and The Humber',
    'West Yorkshire': 'Yorkshire and The Humber',

    # East Midlands
    'Derbyshire': 'East Midlands',
    'Leicestershire': 'East Midlands',
    'Lincolnshire': 'East Midlands',
    'Northamptonshire': 'East Midlands',
    'Nottinghamshire': 'East Midlands',
    'Rutland': 'East Midlands',

    # West Midlands
    'Herefordshire': 'West Midlands',
    'Shropshire': 'West Midlands',
    'Staffordshire': 'West Midlands',
    'Warwickshire': 'West Midlands',
    'West Midlands': 'West Midlands',
    'Worcestershire': 'West Midlands',

    # East of England
    'Bedfordshire': 'East of England',
    'Cambridgeshire': 'East of England',
    'Essex': 'East of England',
    'Hertfordshire': 'East of England',
    'Norfolk': 'East of England',
    'Suffolk': 'East of England',

    # London
    'Greater London': 'London',

    # South East
    'Berkshire': 'South East',
    'Buckinghamshire': 'South East',
    'East Sussex': 'South East',
    'Hampshire': 'South East',
    'Isle of Wight': 'South East',
    'Kent': 'South East',
    'Oxfordshire': 'South East',
    'Surrey': 'South East',
    'West Sussex': 'South East',

    # South West
    'Bristol': 'South West',
    'Cornwall': 'South West',
    'Devon': 'South West',
    'Dorset': 'South West',
    'Gloucestershire': 'South West',
    'Somerset': 'South West',
    'Wiltshire': 'South West',

    # SCOTLAND - Keep as Scotland (or use Scottish regions if needed)
    'Aberdeenshire': 'Scotland',
    'Angus': 'Scotland',
    'Argyll and Bute': 'Scotland',
    'Ayrshire and Arran': 'Scotland',
    'Dumfries and Galloway': 'Scotland',
    'Dunbartonshire': 'Scotland',
    'East Lothian': 'Scotland',
    'Edinburgh': 'Scotland',
    'Fife': 'Scotland',
    'Glasgow': 'Scotland',
    'Inverness': 'Scotland',
    'Lanarkshire': 'Scotland',
    'Midlothian': 'Scotland',
    'Moray': 'Scotland',
    'Perth and Kinross': 'Scotland',
    'Renfrewshire': 'Scotland',
    'Scottish Borders': 'Scotland',
    'Stirling and Falkirk': 'Scotland',
    'West Lothian': 'Scotland',

    # WALES - Keep as Wales (or use Welsh regions if needed)
    'Clwyd': 'Wales',
    'Dyfed': 'Wales',
    'Gwent': 'Wales',
    'Gwynedd': 'Wales',
    'Mid Glamorgan': 'Wales',
    'Powys': 'Wales',
    'South Glamorgan': 'Wales',
    'West Glamorgan': 'Wales',

    # NORTHERN IRELAND
    'Antrim': 'Northern Ireland',
    'Armagh': 'Northern Ireland',
    'Down': 'Northern Ireland',
    'Fermanagh': 'Northern Ireland',
    'Londonderry': 'Northern Ireland',
    'Tyrone': 'Northern Ireland',
}

# Create DataFrame
df_mapping = pd.DataFrame([
    {'county': county, 'uk_region': region}
    for county, region in county_to_region.items()
])

# Sort by region then county
df_mapping = df_mapping.sort_values(['uk_region', 'county'])

# Save to CSV
output_file = '/Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard/county_to_region_mapping.csv'
df_mapping.to_csv(output_file, index=False)

print("=" * 80)
print("County to Region Mapping")
print("=" * 80)
print(f"\n✅ Created mapping for {len(df_mapping)} counties")
print(f"✅ Saved to: {output_file}")

print("\n\nRegions breakdown:")
print(df_mapping['uk_region'].value_counts())

print("\n\nSample mappings:")
print(df_mapping.head(20))
