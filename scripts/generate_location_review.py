#!/usr/bin/env python3
"""Generate a review spreadsheet for unmatched locations.

Reads unmatched_locations.csv (310 towns not in location_lookup) and auto-suggests
UK regions using multiple strategies:
1. London Borough name detection → Greater London
2. County-to-region mapping (e.g., "Cheshire" → North West)
3. Keyword matching from region_parser.py UK_REGIONS dict
4. Postcode extraction from malformed entries
5. Country_region field as hint (e.g., "Northern Ireland")

Outputs an Excel file with columns:
  town_city, country_region, suggested_region, suggested_county, confidence,
  source, vacancy_count, done

This file is exported to Google Sheets for user review. Rows marked done=TRUE
are synced into location_lookup on the next refresh.
"""

import re
import sys
import os

import pandas as pd

# Add parent directory so we can import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.region_parser import UK_REGIONS, POSTCODE_REGIONS

# --- London Borough → Greater London ---
LONDON_BOROUGHS = {
    'barking and dagenham', 'barnet', 'bexley', 'brent', 'bromley', 'camden',
    'city of london', 'croydon', 'ealing', 'enfield', 'greenwich', 'hackney',
    'hammersmith and fulham', 'haringey', 'harrow', 'havering', 'hillingdon',
    'hounslow', 'islington', 'kensington and chelsea', 'kingston upon thames',
    'lambeth', 'lewisham', 'merton', 'newham', 'redbridge', 'richmond upon thames',
    'southwark', 'sutton', 'tower hamlets', 'waltham forest', 'wandsworth',
    'westminster',
}

# Towns commonly within Greater London that aren't in the main lookup
LONDON_TOWNS = {
    'romford', 'wembley', 'hornchurch', 'ilford', 'enfield', 'harrow',
    'uxbridge', 'rainham', 'dagenham', 'edgware', 'stratford', 'sidcup',
    'twickenham', 'orpington', 'feltham', 'erith', 'greenford', 'barking',
    'bexleyheath', 'chingford', 'catford', 'tottenham', 'brixton', 'dulwich',
    'peckham', 'bermondsey', 'woolwich', 'eltham', 'lewisham', 'deptford',
    'norwood', 'wimbledon', 'mitcham', 'tooting', 'clapham', 'balham',
    'putney', 'fulham', 'hammersmith', 'chiswick', 'acton', 'ealing',
    'hanwell', 'northolt', 'ruislip', 'pinner', 'stanmore', 'hendon',
    'finchley', 'muswell hill', 'wood green', 'palmers green', 'southgate',
    'barnet', 'whetstone', 'mill hill', 'colindale', 'kingsbury', 'willesden',
    'kilburn', 'hampstead', 'highgate', 'holloway', 'islington', 'hackney',
    'clapton', 'leyton', 'leytonstone', 'walthamstow', 'woodford', 'wanstead',
    'plaistow', 'east ham', 'manor park', 'canning town', 'beckton',
    'thamesmead', 'abbey wood', 'plumstead', 'charlton', 'blackheath',
    'lee', 'grove park', 'bromley', 'beckenham', 'penge', 'crystal palace',
    'sydenham', 'forest hill', 'brockley', 'new cross', 'surbiton',
    'new malden', 'tolworth', 'kingston', 'hampton', 'teddington',
    'richmond', 'kew', 'mortlake', 'barnes', 'roehampton', 'battersea',
    'nine elms', 'vauxhall', 'kennington', 'camberwell', 'walworth',
    'rotherhithe', 'isle of dogs', 'poplar', 'bow', 'mile end', 'bethnal green',
    'whitechapel', 'stepney', 'limehouse', 'shadwell', 'wapping',
    'shoreditch', 'hoxton', 'dalston', 'stoke newington', 'stamford hill',
    'south woodford', 'chigwell', 'buckhurst hill', 'loughton',
    'upminster', 'cranham', 'harold wood', 'harold hill', 'collier row',
    'chadwell heath', 'goodmayes', 'seven kings', 'barkingside',
    'hainault', 'fairlop', 'gants hill',
}

# County name → region from CSV (loaded below)
COUNTY_TO_REGION = {}

# Known non-UK locations
NON_UK_COUNTRIES = {'us', 'de', 'fr', 'at', 'ie', 'nl', 'be', 'es', 'it', 'au', 'ca', 'nz'}

# Supplementary town → region mapping for well-known towns not in location_lookup.
# These are towns identified from unmatched_locations.csv with high vacancy counts.
SUPPLEMENTARY_TOWNS = {
    # Greater London towns
    'hayes': 'Greater London',
    'southall': 'Greater London',
    'festival walk': 'Greater London',  # Hayes, Hillingdon
    'great warley': 'Greater London',
    'south bank': 'Greater London',

    # North West
    'ellesmere port': 'North West',
    'wirral': 'North West',
    'blacon': 'North West',
    'sefton': 'North West',
    'thornton hough': 'North West',
    'sandiway': 'North West',
    'church lawton': 'North West',
    'barrow-in-furness': 'North West',
    'neston': 'North West',

    # East Midlands
    'newark-on-trent': 'East Midlands',
    'glenfield': 'East Midlands',
    'sutton-in-ashfield': 'East Midlands',
    'whatton': 'East Midlands',

    # East of England
    'castle point': 'East of England',  # Essex district
    'uttlesford': 'East of England',  # Essex district

    # South East
    'staines-upon-thames': 'South East',
    'lancing': 'South East',
    'college town': 'South East',  # Sandhurst, Berkshire
    'owlsmoor': 'South East',  # Sandhurst, Berkshire
    'rushmoor district': 'South East',  # Hampshire
    'weald': 'South East',
    'romney marsh': 'South East',  # Kent
    'bucks horn oak': 'South East',  # Hampshire
    'borough of swale': 'South East',  # Kent

    # South West
    'porton down': 'South West',  # Wiltshire
    'blandford camp': 'South West',  # Dorset
    'saint leonards': 'South West',  # Dorset (St Leonards)

    # Hampshire / South East
    'titchfield': 'South East',  # Hampshire

    # North East
    'thornaby': 'North East',  # Teesside
    'north shields': 'North East',
    'houghton le spring': 'North East',

    # Yorkshire and The Humber
    'old whittington': 'Yorkshire and The Humber',

    # West Midlands
    'hasland': 'West Midlands',

    # Wales
    'duffryn': 'Wales',  # Newport area
    'coety': 'Wales',

    # Northern Ireland
    'bangor': 'Northern Ireland',  # NI Bangor (not Welsh)
    'crumlin': 'Northern Ireland',

    # East of England
    'benfleet': 'East of England',  # Essex

    # North West
    'thurstaston': 'North West',  # Wirral
    'blundellsands': 'North West',  # Sefton, Merseyside
    'seaforth': 'North West',  # Sefton, Merseyside
    'metropolitan borough of knowsley': 'North West',
    'metropolitan borough of sefton': 'North West',
    'stapeley': 'North West',  # Cheshire
    'wincle': 'North West',  # Cheshire

    # East Midlands
    'doe lea': 'East Midlands',  # Derbyshire
    'glen parva': 'East Midlands',  # Leicestershire
    'langwith': 'East Midlands',  # Derbyshire
    'mastin moor': 'East Midlands',  # Derbyshire
    'fineshade': 'East Midlands',  # Northamptonshire

    # South East
    'wainscott': 'South East',  # Kent
    'naphill': 'South East',  # Buckinghamshire
    'earley': 'South East',  # Berkshire
    'bexhill': 'South East',  # East Sussex
    'westbere': 'South East',  # Kent
    'sandgate': 'South East',  # Kent
    'isleworth': 'Greater London',  # Hounslow

    # North East
    'fir tree': 'North East',  # County Durham

    # South West
    'larkhill': 'South West',  # Wiltshire
    'r a f saint mawgan': 'South West',  # Cornwall
    'lew': 'South West',  # Devon

    # Yorkshire
    'everthorpe': 'Yorkshire and The Humber',  # East Riding
    'tangham': 'South East',  # Suffolk/Norfolk area — actually Tangham near Woodbridge, Suffolk
}


def load_county_mapping(project_dir):
    """Load county_to_region_mapping.csv."""
    path = os.path.join(project_dir, 'county_to_region_mapping.csv')
    df = pd.read_csv(path)
    return {row['county'].lower(): row['uk_region'] for _, row in df.iterrows()}


def extract_london_borough(town):
    """Check if town is or contains a London Borough name."""
    town_lower = town.lower().strip()

    # Direct match against borough set
    if town_lower in LONDON_BOROUGHS:
        return True

    # "London Borough of X" pattern
    m = re.match(r'london borough of (.+)', town_lower)
    if m:
        borough = m.group(1).strip()
        if borough in LONDON_BOROUGHS:
            return True
        # Partial match — "London Borough of" prefix is strong signal
        return True

    # "Royal Borough of X" pattern
    m = re.match(r'royal borough of (.+)', town_lower)
    if m:
        return True

    return False


def extract_postcode(text):
    """Extract UK postcode area from text."""
    if not text or pd.isna(text):
        return None
    match = re.search(r'\b([A-Z]{1,2}\d{1,2}[A-Z]?)\s*\d[A-Z]{2}\b', str(text).upper())
    if match:
        area = match.group(1)
        area = re.sub(r'\d.*', '', area)  # Keep only letter prefix
        return area
    return None


def suggest_region(row, county_to_region, lookup_index):
    """Apply multi-strategy region suggestion for a single unmatched location row."""
    town = str(row['town_city']).strip() if pd.notna(row['town_city']) else ''
    country_region = str(row['country_region']).strip() if pd.notna(row['country_region']) else ''
    country_code = str(row['country_code']).strip().upper() if pd.notna(row['country_code']) else ''
    town_lower = town.lower()
    cr_lower = country_region.lower()

    # --- Strategy 0: Non-UK detection ---
    if country_code in NON_UK_COUNTRIES:
        return 'Non-UK', None, 'high', 'country_code'

    # Non-UK via country_region field (US states, foreign regions)
    non_uk_regions = {
        'ma', 'massachusetts', 'california', 'buenos aires province',
        'hauts-de-france', 'limassol', 'kl', 'victoria', 'nordrhein-westfalen',
        'famagusta', 'laikipia county', 'washington',
    }
    if cr_lower in non_uk_regions:
        return 'Non-UK', None, 'high', 'non_uk_region'

    # --- Strategy 1: London Borough detection ---
    if extract_london_borough(town):
        return 'Greater London', 'Greater London', 'high', 'london_borough'

    # --- Strategy 2: Known London town ---
    if town_lower in LONDON_TOWNS:
        return 'Greater London', 'Greater London', 'high', 'london_town'

    # --- Strategy 2b: Supplementary town mapping ---
    if town_lower in SUPPLEMENTARY_TOWNS:
        return SUPPLEMENTARY_TOWNS[town_lower], None, 'high', 'supplementary_town'

    # --- Strategy 3: County name used as town ---
    if town_lower in county_to_region:
        return county_to_region[town_lower], town, 'high', 'county_match'

    # --- Strategy 4: Region name used as town (e.g., "South East England") ---
    region_patterns = {
        'south east england': 'South East',
        'south west england': 'South West',
        'north west england': 'North West',
        'north east england': 'North East',
        'east midlands': 'East Midlands',
        'west midlands': 'West Midlands',
        'east of england': 'East of England',
        'greater london': 'Greater London',
        'yorkshire': 'Yorkshire and The Humber',
    }
    for pattern, region in region_patterns.items():
        if pattern in town_lower:
            return region, None, 'high', 'region_name'

    # --- Strategy 5: Keyword matching from UK_REGIONS ---
    for region, keywords in UK_REGIONS.items():
        for keyword in keywords:
            if keyword == town_lower or keyword in town_lower:
                return region, None, 'medium', 'keyword_match'

    # --- Strategy 6: Postcode extraction from garbage data ---
    postcode_area = extract_postcode(town)
    if postcode_area and postcode_area in POSTCODE_REGIONS:
        return POSTCODE_REGIONS[postcode_area], None, 'medium', 'postcode'

    # Also try postcode from country_region field
    postcode_area = extract_postcode(country_region)
    if postcode_area and postcode_area in POSTCODE_REGIONS:
        return POSTCODE_REGIONS[postcode_area], None, 'low', 'postcode_country_region'

    # --- Strategy 7: country_region field hints ---
    if 'northern ireland' in cr_lower:
        return 'Northern Ireland', None, 'medium', 'country_region_hint'
    if 'scotland' in cr_lower:
        return 'Scotland', None, 'medium', 'country_region_hint'
    if 'wales' in cr_lower:
        return 'Wales', None, 'medium', 'country_region_hint'

    # --- Strategy 8: Fuzzy match against location_lookup ---
    # Strip hyphens and "on/upon/in/le" suffixes for partial matching
    simplified = re.sub(r'\b(on|upon|in|le|la)\b', '', town_lower)
    simplified = re.sub(r'[-]', ' ', simplified).strip()
    simplified = re.sub(r'\s+', ' ', simplified)
    first_word = simplified.split()[0] if simplified else ''
    if first_word and len(first_word) > 3 and first_word in lookup_index:
        region = lookup_index[first_word]
        return region, None, 'low', 'fuzzy_lookup'

    # --- Strategy 9: Malformed data detection ---
    if len(town) > 80 or '\n' in town:
        return 'MALFORMED', None, 'review', 'long_text'

    return None, None, 'review', 'no_match'


def main():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(project_dir, 'unmatched_locations.csv')

    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)

    county_to_region = load_county_mapping(project_dir)

    # Build lookup index: first word of town → region (for fuzzy matching)
    lookup_path = os.path.join(project_dir, 'location_lookup_with_regions.csv')
    lookup_index = {}
    if os.path.exists(lookup_path):
        lookup_df = pd.read_csv(lookup_path)
        for _, r in lookup_df.iterrows():
            town = str(r['town_city']).lower().strip()
            region = str(r['region']).strip()
            first_word = town.split()[0] if town else ''
            if first_word and len(first_word) > 3 and first_word not in lookup_index:
                lookup_index[first_word] = region

    df = pd.read_csv(csv_path)

    print(f"Processing {len(df)} unmatched locations...")

    results = []
    for _, row in df.iterrows():
        region, county, confidence, source = suggest_region(row, county_to_region, lookup_index)
        results.append({
            'town_city': row['town_city'],
            'country_region': row['country_region'],
            'country_code': row['country_code'],
            'vacancy_count': row['vacancy_count'],
            'suggested_region': region,
            'suggested_county': county,
            'confidence': confidence,
            'source': source,
            'done': '',
        })

    out = pd.DataFrame(results)

    # Sort: high confidence first, then by vacancy count descending
    confidence_order = {'high': 0, 'medium': 1, 'low': 2, 'review': 3}
    out['_sort'] = out['confidence'].map(confidence_order)
    out = out.sort_values(['_sort', 'vacancy_count'], ascending=[True, False])
    out = out.drop(columns=['_sort'])

    # Summary stats
    total = len(out)
    high = len(out[out['confidence'] == 'high'])
    medium = len(out[out['confidence'] == 'medium'])
    low = len(out[out['confidence'] == 'low'])
    review = len(out[out['confidence'] == 'review'])
    non_uk = len(out[out['suggested_region'] == 'Non-UK'])
    malformed = len(out[out['suggested_region'] == 'MALFORMED'])

    print(f"\nResults:")
    print(f"  High confidence:   {high:>3} ({high/total*100:.0f}%)")
    print(f"  Medium confidence: {medium:>3} ({medium/total*100:.0f}%)")
    print(f"  Low confidence:    {low:>3} ({low/total*100:.0f}%)")
    print(f"  Needs review:      {review:>3} ({review/total*100:.0f}%)")
    print(f"  Non-UK:            {non_uk:>3}")
    print(f"  Malformed data:    {malformed:>3}")

    vacancies_covered = out[out['suggested_region'].notna() &
                           ~out['suggested_region'].isin(['MALFORMED'])]['vacancy_count'].sum()
    total_vacancies = out['vacancy_count'].sum()
    print(f"\n  Vacancies with suggestions: {vacancies_covered:,} / {total_vacancies:,} "
          f"({vacancies_covered/total_vacancies*100:.1f}%)")

    # Write Excel
    out_path = os.path.join(project_dir, 'location_review.xlsx')
    out.to_excel(out_path, index=False, sheet_name='Review')
    print(f"\nWritten to: {out_path}")
    print("Upload this to Google Sheets, review, and mark 'done' column for approved rows.")


if __name__ == '__main__':
    main()
