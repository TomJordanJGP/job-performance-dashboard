"""Map UK region and county for all rows in the Review tab.

Reads the review data, applies multiple matching strategies,
and outputs a CSV with suggested_region and suggested_county for each row.
Does NOT update the Google Sheet directly.
"""

import csv
import json
import re

# ── 0. Normalize non-canonical region names to the 12 official ones ──────────
REGION_NORMALIZE = {
    'London': 'Greater London',
    'Central Lowlands': 'Scotland',
    'Lothian': 'Scotland',
    'Far North of Scotland': 'Scotland',
    'Highland and Islands': 'Scotland',
    'North East Scotland': 'Scotland',
    'North Highlands': 'Scotland',
    'North Scotland': 'Scotland',
    'South East Scotland': 'Scotland',
    'South West Scotland': 'Scotland',
    'West Central Scotland': 'Scotland',
    'West Coast Of Scotland': 'Scotland',
    'Scottish Borders': 'Scotland',
    'Guernsey': 'Non-UK',
    'Jersey': 'Non-UK',
    'Isle of Man': 'Non-UK',
}


def normalize_region(region):
    """Normalize a region name to one of the 12 canonical UK regions."""
    return REGION_NORMALIZE.get(region, region)


# ── 1. Load location lookup CSV ──────────────────────────────────────────────
def load_location_lookup():
    """Build town_city -> (county, region, country) from the 16K CSV."""
    lookup = {}
    with open('location_lookup_with_regions.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            town = row['town_city'].strip().upper()
            county = row.get('county', '').strip()
            region = normalize_region(row.get('region', '').strip())
            country = row.get('country', '').strip()
            if town and (county or region):
                # Don't let wrong entries overwrite correct ones
                # (e.g. a "London" in Essex overwriting the real London)
                if town in lookup:
                    # Keep the entry with Greater London county for LONDON
                    if town == 'LONDON' and county != 'Greater London':
                        continue
                lookup[town] = {
                    'county': county,
                    'region': region,
                    'country': country,
                }

    # Manual overrides for known wrong entries
    lookup['LONDON'] = {'county': 'Greater London', 'region': 'Greater London', 'country': 'England'}
    return lookup

# ── 2. County to region mapping ──────────────────────────────────────────────
def load_county_to_region():
    """Load county -> region from CSV."""
    mapping = {}
    with open('county_to_region_mapping.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            county = row['county'].strip()
            region = row['uk_region'].strip()
            mapping[county.upper()] = {'county': county, 'region': region}
    return mapping

# ── 3. Postcode area -> (county, region) ─────────────────────────────────────
POSTCODE_MAP = {
    'AB': ('Aberdeenshire', 'Scotland'),
    'AL': ('Hertfordshire', 'East of England'),
    'B':  ('West Midlands', 'West Midlands'),
    'BA': ('Somerset', 'South West'),
    'BB': ('Lancashire', 'North West'),
    'BD': ('West Yorkshire', 'Yorkshire and The Humber'),
    'BH': ('Dorset', 'South West'),
    'BL': ('Greater Manchester', 'North West'),
    'BN': ('East Sussex', 'South East'),
    'BR': ('Greater London', 'Greater London'),
    'BS': ('Bristol', 'South West'),
    'BT': ('Antrim', 'Northern Ireland'),
    'CA': ('Cumbria', 'North West'),
    'CB': ('Cambridgeshire', 'East of England'),
    'CF': ('South Glamorgan', 'Wales'),
    'CH': ('Cheshire', 'North West'),
    'CM': ('Essex', 'East of England'),
    'CO': ('Essex', 'East of England'),
    'CR': ('Greater London', 'Greater London'),
    'CT': ('Kent', 'South East'),
    'CV': ('West Midlands', 'West Midlands'),
    'CW': ('Cheshire', 'North West'),
    'DA': ('Kent', 'South East'),
    'DD': ('Angus', 'Scotland'),
    'DE': ('Derbyshire', 'East Midlands'),
    'DG': ('Dumfries and Galloway', 'Scotland'),
    'DH': ('Durham', 'North East'),
    'DL': ('Durham', 'North East'),
    'DN': ('South Yorkshire', 'Yorkshire and The Humber'),
    'DT': ('Dorset', 'South West'),
    'DY': ('West Midlands', 'West Midlands'),
    'E':  ('Greater London', 'Greater London'),
    'EC': ('Greater London', 'Greater London'),
    'EH': ('Edinburgh', 'Scotland'),
    'EN': ('Greater London', 'Greater London'),
    'EX': ('Devon', 'South West'),
    'FK': ('Stirling and Falkirk', 'Scotland'),
    'FY': ('Lancashire', 'North West'),
    'G':  ('Glasgow', 'Scotland'),
    'GL': ('Gloucestershire', 'South West'),
    'GU': ('Surrey', 'South East'),
    'HA': ('Greater London', 'Greater London'),
    'HD': ('West Yorkshire', 'Yorkshire and The Humber'),
    'HG': ('North Yorkshire', 'Yorkshire and The Humber'),
    'HP': ('Buckinghamshire', 'South East'),
    'HR': ('Herefordshire', 'West Midlands'),
    'HS': ('Inverness', 'Scotland'),
    'HU': ('East Riding of Yorkshire', 'Yorkshire and The Humber'),
    'HX': ('West Yorkshire', 'Yorkshire and The Humber'),
    'IG': ('Greater London', 'Greater London'),
    'IP': ('Suffolk', 'East of England'),
    'IV': ('Inverness', 'Scotland'),
    'KA': ('Ayrshire and Arran', 'Scotland'),
    'KT': ('Surrey', 'South East'),
    'KW': ('Inverness', 'Scotland'),
    'KY': ('Fife', 'Scotland'),
    'L':  ('Merseyside', 'North West'),
    'LA': ('Lancashire', 'North West'),
    'LD': ('Powys', 'Wales'),
    'LE': ('Leicestershire', 'East Midlands'),
    'LL': ('Gwynedd', 'Wales'),
    'LN': ('Lincolnshire', 'East Midlands'),
    'LS': ('West Yorkshire', 'Yorkshire and The Humber'),
    'LU': ('Bedfordshire', 'East of England'),
    'M':  ('Greater Manchester', 'North West'),
    'ME': ('Kent', 'South East'),
    'MK': ('Buckinghamshire', 'South East'),
    'ML': ('Lanarkshire', 'Scotland'),
    'N':  ('Greater London', 'Greater London'),
    'NE': ('Tyne and Wear', 'North East'),
    'NG': ('Nottinghamshire', 'East Midlands'),
    'NN': ('Northamptonshire', 'East Midlands'),
    'NP': ('Gwent', 'Wales'),
    'NR': ('Norfolk', 'East of England'),
    'NW': ('Greater London', 'Greater London'),
    'OL': ('Greater Manchester', 'North West'),
    'OX': ('Oxfordshire', 'South East'),
    'PA': ('Renfrewshire', 'Scotland'),
    'PE': ('Cambridgeshire', 'East of England'),
    'PH': ('Perth and Kinross', 'Scotland'),
    'PL': ('Devon', 'South West'),
    'PO': ('Hampshire', 'South East'),
    'PR': ('Lancashire', 'North West'),
    'RG': ('Berkshire', 'South East'),
    'RH': ('Surrey', 'South East'),
    'RM': ('Greater London', 'Greater London'),
    'S':  ('South Yorkshire', 'Yorkshire and The Humber'),
    'SA': ('West Glamorgan', 'Wales'),
    'SE': ('Greater London', 'Greater London'),
    'SG': ('Hertfordshire', 'East of England'),
    'SK': ('Cheshire', 'North West'),
    'SL': ('Berkshire', 'South East'),
    'SM': ('Greater London', 'Greater London'),
    'SN': ('Wiltshire', 'South West'),
    'SO': ('Hampshire', 'South East'),
    'SP': ('Wiltshire', 'South West'),
    'SR': ('Tyne and Wear', 'North East'),
    'SS': ('Essex', 'East of England'),
    'ST': ('Staffordshire', 'West Midlands'),
    'SW': ('Greater London', 'Greater London'),
    'SY': ('Shropshire', 'West Midlands'),
    'TA': ('Somerset', 'South West'),
    'TD': ('Scottish Borders', 'Scotland'),
    'TF': ('Shropshire', 'West Midlands'),
    'TN': ('Kent', 'South East'),
    'TQ': ('Devon', 'South West'),
    'TR': ('Cornwall', 'South West'),
    'TS': ('Durham', 'North East'),
    'TW': ('Greater London', 'Greater London'),
    'UB': ('Greater London', 'Greater London'),
    'W':  ('Greater London', 'Greater London'),
    'WA': ('Cheshire', 'North West'),
    'WC': ('Greater London', 'Greater London'),
    'WD': ('Hertfordshire', 'East of England'),
    'WF': ('West Yorkshire', 'Yorkshire and The Humber'),
    'WN': ('Greater Manchester', 'North West'),
    'WR': ('Worcestershire', 'West Midlands'),
    'WS': ('West Midlands', 'West Midlands'),
    'WV': ('West Midlands', 'West Midlands'),
    'YO': ('North Yorkshire', 'Yorkshire and The Humber'),
    'ZE': ('Inverness', 'Scotland'),
}


def extract_postcode_area(text):
    """Extract UK postcode area from text."""
    # Match full or partial postcodes
    m = re.search(r'\b([A-Z]{1,2})\d{1,2}\s*\d?[A-Z]{0,2}\b', text.upper())
    if m:
        area = m.group(1)
        # Try 2-letter first, then 1-letter
        if area in POSTCODE_MAP:
            return area
        if len(area) == 2 and area[0] in POSTCODE_MAP:
            return area[0]
    return None


# ── 4. London boroughs ──────────────────────────────────────────────────────
LONDON_BOROUGHS = {
    'BARKING', 'DAGENHAM', 'BARNET', 'BEXLEY', 'BRENT', 'BROMLEY',
    'CAMDEN', 'CROYDON', 'EALING', 'ENFIELD', 'GREENWICH', 'HACKNEY',
    'HAMMERSMITH', 'FULHAM', 'HARINGEY', 'HARROW', 'HAVERING', 'HILLINGDON',
    'HOUNSLOW', 'ISLINGTON', 'KENSINGTON', 'CHELSEA', 'KINGSTON',
    'LAMBETH', 'LEWISHAM', 'MERTON', 'NEWHAM', 'REDBRIDGE', 'RICHMOND',
    'SOUTHWARK', 'SUTTON', 'TOWER HAMLETS', 'WALTHAM FOREST',
    'WANDSWORTH', 'WESTMINSTER', 'CITY OF LONDON',
    'WALTHAMSTOW', 'ILFORD', 'ROMFORD', 'STRATFORD', 'WOOLWICH',
    'CATFORD', 'DEPTFORD', 'BRIXTON', 'PECKHAM', 'BERMONDSEY',
    'PADDINGTON', 'SHOREDITCH', 'BETHNAL GREEN', 'WHITECHAPEL',
    'TOTTENHAM', 'WOOD GREEN', 'FINSBURY PARK', 'STOKE NEWINGTON',
    'WEMBLEY', 'EDGWARE', 'CHISWICK', 'ACTON', 'TWICKENHAM',
    'FELTHAM', 'UXBRIDGE', 'HAYES', 'THAMESMEAD', 'PLUMSTEAD',
    'SYDENHAM', 'DULWICH', 'STREATHAM', 'TOOTING', 'BALHAM',
    'PUTNEY', 'WIMBLEDON', 'MITCHAM', 'CARSHALTON',
    'LADBROKE GROVE', 'NOTTING HILL', 'MAIDA VALE', 'KILBURN',
    'HAMPSTEAD', 'HIGHGATE', 'MUSWELL HILL', 'PALMERS GREEN',
    'PINNER', 'STANMORE', 'COLINDALE', 'HENDON', 'MILL HILL',
    'POPLAR', 'BOW', 'STEPNEY', 'CANARY WHARF', 'DOCKLANDS',
    'HORNCHURCH', 'UPMINSTER', 'RAINHAM', 'ERITH', 'SIDCUP',
    'ORPINGTON', 'BECKENHAM', 'NORBURY', 'THORNTON HEATH',
    'CHINGFORD', 'LEYTON', 'LEYTONSTONE', 'EAST HAM', 'WEST HAM',
    'PLAISTOW', 'FOREST GATE', 'MANOR PARK', 'SEVEN KINGS',
    'GOODMAYES', 'CHADWELL HEATH', 'COLLIER ROW', 'HAROLD HILL',
    'DAGNAM PARK', 'GIDEA PARK', 'EMERSON PARK', 'CRANHAM',
    'BERMONDSEY', 'ELEPHANT AND CASTLE', 'WALWORTH', 'CAMBERWELL',
    'TULSE HILL', 'WEST NORWOOD', 'CRYSTAL PALACE', 'UPPER NORWOOD',
    'ANERLEY', 'PENGE', 'ELTHAM', 'KIDBROOKE', 'BLACKHEATH',
    'CHARLTON', 'ABBEY WOOD', 'BEXLEYHEATH', 'WELLING',
    'BARKING', 'BECONTREE', 'DAGENHAM', 'PIMLICO', 'VICTORIA',
    'MAYFAIR', 'SOHO', 'MARYLEBONE', 'FITZROVIA', 'BLOOMSBURY',
    'HOLBORN', 'COVENT GARDEN', 'STRAND', 'ALDWYCH',
}

# ── 5. Supplementary town -> (county, region) for common places ──────────────
SUPPLEMENTARY_TOWNS = {
    'WESTBERE': ('Kent', 'South East'),
    'LARKHILL': ('Wiltshire', 'South West'),
    'BEXHILL': ('East Sussex', 'South East'),
    'EVERTHORPE': ('East Riding of Yorkshire', 'Yorkshire and The Humber'),
    'LEW': ('Devon', 'South West'),
    'COETY': ('Mid Glamorgan', 'Wales'),
    'CEFN CRIBWR': ('Mid Glamorgan', 'Wales'),
    'PENCOED': ('Mid Glamorgan', 'Wales'),
    'FARNHAM': ('Surrey', 'South East'),
    'AMESBURY': ('Wiltshire', 'South West'),
    'BULFORD': ('Wiltshire', 'South West'),
    'LIPHOOK': ('Hampshire', 'South East'),
    'BORDON': ('Hampshire', 'South East'),
    'TIDWORTH': ('Wiltshire', 'South West'),
    'NETHERAVON': ('Wiltshire', 'South West'),
    'WARMINSTER': ('Wiltshire', 'South West'),
    'UPAVON': ('Wiltshire', 'South West'),
    'CORSHAM': ('Wiltshire', 'South West'),
    'LUDGERSHALL': ('Wiltshire', 'South West'),
    'YEOVILTON': ('Somerset', 'South West'),
    'BLANDFORD': ('Dorset', 'South West'),
    'BOVINGTON': ('Dorset', 'South West'),
    'CHICKERELL': ('Dorset', 'South West'),
    'LULWORTH': ('Dorset', 'South West'),
    'CULDROSE': ('Cornwall', 'South West'),
    'DEVONPORT': ('Devon', 'South West'),
    'FASLANE': ('Dunbartonshire', 'Scotland'),
    'ROSYTH': ('Fife', 'Scotland'),
    'LOSSIEMOUTH': ('Moray', 'Scotland'),
    'KINLOSS': ('Moray', 'Scotland'),
    'LEUCHARS': ('Fife', 'Scotland'),
    'CATTERICK': ('North Yorkshire', 'Yorkshire and The Humber'),
    'DISHFORTH': ('North Yorkshire', 'Yorkshire and The Humber'),
    'TOPCLIFFE': ('North Yorkshire', 'Yorkshire and The Humber'),
    'RIPON': ('North Yorkshire', 'Yorkshire and The Humber'),
    'HARROGATE': ('North Yorkshire', 'Yorkshire and The Humber'),
    'COLCHESTER': ('Essex', 'East of England'),
    'CHELMSFORD': ('Essex', 'East of England'),
    'WATTISHAM': ('Suffolk', 'East of England'),
    'MARHAM': ('Norfolk', 'East of England'),
    'HONINGTON': ('Suffolk', 'East of England'),
    'LAKENHEATH': ('Suffolk', 'East of England'),
    'MILDENHALL': ('Suffolk', 'East of England'),
    'CONINGSBY': ('Lincolnshire', 'East Midlands'),
    'CRANWELL': ('Lincolnshire', 'East Midlands'),
    'DIGBY': ('Lincolnshire', 'East Midlands'),
    'WADDINGTON': ('Lincolnshire', 'East Midlands'),
    'SCAMPTON': ('Lincolnshire', 'East Midlands'),
    'WITTERING': ('Cambridgeshire', 'East of England'),
    'BRIZE NORTON': ('Oxfordshire', 'South East'),
    'BENSON': ('Oxfordshire', 'South East'),
    'HALTON': ('Buckinghamshire', 'South East'),
    'HIGH WYCOMBE': ('Buckinghamshire', 'South East'),
    'ODIHAM': ('Hampshire', 'South East'),
    'MIDDLE WALLOP': ('Hampshire', 'South East'),
    'NORTHWOOD': ('Greater London', 'Greater London'),
    'HENDON': ('Greater London', 'Greater London'),
    'COSFORD': ('Shropshire', 'West Midlands'),
    'DONNINGTON': ('Shropshire', 'West Midlands'),
    'SHAWBURY': ('Shropshire', 'West Midlands'),
    'STAFFORD': ('Staffordshire', 'West Midlands'),
    'LICHFIELD': ('Staffordshire', 'West Midlands'),
    'SWINFEN': ('Staffordshire', 'West Midlands'),
    'WOLVERHAMPTON': ('West Midlands', 'West Midlands'),
    'FEATHERSTONE': ('West Midlands', 'West Midlands'),
    'VALLEY': ('Gwynedd', 'Wales'),
    'SAINT ATHAN': ('South Glamorgan', 'Wales'),
    'BRECON': ('Powys', 'Wales'),
    'SENNYBRIDGE': ('Powys', 'Wales'),
    'HIGH PEAK': ('Derbyshire', 'East Midlands'),
    'TRENT BRIDGE': ('Nottinghamshire', 'East Midlands'),
    'SHOCKLACH': ('Cheshire', 'North West'),
    'SAINT LEONARDS-ON-SEA': ('East Sussex', 'South East'),
    'HALTON CAMP': ('Buckinghamshire', 'South East'),
    'EAST MALLING': ('Kent', 'South East'),
    'HUCKNALL': ('Nottinghamshire', 'East Midlands'),
    'BINGHAM': ('Nottinghamshire', 'East Midlands'),
    'ARNOLDD': ('Nottinghamshire', 'East Midlands'),
    'CARLTON': ('Nottinghamshire', 'East Midlands'),
    'GEDLING': ('Nottinghamshire', 'East Midlands'),
    'BULWELL': ('Nottinghamshire', 'East Midlands'),
    'BESTWOOD': ('Nottinghamshire', 'East Midlands'),
    'BEESTON': ('Nottinghamshire', 'East Midlands'),
    'STAPLEFORD': ('Nottinghamshire', 'East Midlands'),
    'EASTWOOD': ('Nottinghamshire', 'East Midlands'),
    'KIMBERLEY': ('Nottinghamshire', 'East Midlands'),
    'CALVERTON': ('Nottinghamshire', 'East Midlands'),
    'OLLERTON': ('Nottinghamshire', 'East Midlands'),
    'EDWINSTOWE': ('Nottinghamshire', 'East Midlands'),
    'WORKSOP': ('Nottinghamshire', 'East Midlands'),
    'RETFORD': ('Nottinghamshire', 'East Midlands'),
    'NEWARK': ('Nottinghamshire', 'East Midlands'),
    'SOUTHWELL': ('Nottinghamshire', 'East Midlands'),
    'BELPER': ('Derbyshire', 'East Midlands'),
    'WARFIELD': ('Berkshire', 'South East'),
    'OXTED': ('Surrey', 'South East'),
    'MAIDENHEAD': ('Berkshire', 'South East'),
    'LOUGHBOROUGH': ('Leicestershire', 'East Midlands'),
    'CHESTERFIELD': ('Derbyshire', 'East Midlands'),
    'STAVELEY': ('Derbyshire', 'East Midlands'),
    'CANNOCK': ('Staffordshire', 'West Midlands'),
    'HUYTON': ('Merseyside', 'North West'),
    'KNOWSLEY': ('Merseyside', 'North West'),
    'GUILDFORD': ('Surrey', 'South East'),
    'PLYMOUTH': ('Devon', 'South West'),
    'THATCHAM': ('Berkshire', 'South East'),
    'NEWBURY': ('Berkshire', 'South East'),
    'HUNGERFORD': ('Berkshire', 'South East'),
    'PANGBOURNE': ('Berkshire', 'South East'),
    'THEALE': ('Berkshire', 'South East'),
    'CALDICOT': ('Gwent', 'Wales'),
    'BARGOED': ('Mid Glamorgan', 'Wales'),
    'PONTYPRIDD': ('Mid Glamorgan', 'Wales'),
    'ABERDARE': ('Mid Glamorgan', 'Wales'),
    'MOUNTAIN ASH': ('Mid Glamorgan', 'Wales'),
    'MAESTEG': ('Mid Glamorgan', 'Wales'),
    'BRIDGEND': ('Mid Glamorgan', 'Wales'),
    'PORTHCAWL': ('Mid Glamorgan', 'Wales'),
    'BARRY': ('South Glamorgan', 'Wales'),
    'PENARTH': ('South Glamorgan', 'Wales'),
    'NEATH': ('West Glamorgan', 'Wales'),
    'PORT TALBOT': ('West Glamorgan', 'Wales'),
    'LLANELLI': ('Dyfed', 'Wales'),
    'CARMARTHEN': ('Dyfed', 'Wales'),
    'HAVERFORDWEST': ('Dyfed', 'Wales'),
    'PEMBROKE': ('Dyfed', 'Wales'),
    'MILFORD HAVEN': ('Dyfed', 'Wales'),
    'ABERYSTWYTH': ('Dyfed', 'Wales'),
    'LAMPETER': ('Dyfed', 'Wales'),
    'WREXHAM': ('Clwyd', 'Wales'),
    'FLINT': ('Clwyd', 'Wales'),
    'MOLD': ('Clwyd', 'Wales'),
    'DENBIGH': ('Clwyd', 'Wales'),
    'RHYL': ('Clwyd', 'Wales'),
    'COLWYN BAY': ('Clwyd', 'Wales'),
    'NEWTOWN': ('Powys', 'Wales'),
    'WELSHPOOL': ('Powys', 'Wales'),
    'BANGOR': ('Gwynedd', 'Wales'),
    'CAERNARFON': ('Gwynedd', 'Wales'),
    'HOLYHEAD': ('Gwynedd', 'Wales'),
    'PORTISHEAD': ('Somerset', 'South West'),
    'KEYNSHAM': ('Somerset', 'South West'),
    'WESTON-SUPER-MARE': ('Somerset', 'South West'),
    'CLEVEDON': ('Somerset', 'South West'),
    'NAILSEA': ('Somerset', 'South West'),
    'YATTON': ('Somerset', 'South West'),
    'BACKWELL': ('Somerset', 'South West'),
    'CHEDDAR': ('Somerset', 'South West'),
    'GLASTONBURY': ('Somerset', 'South West'),
    'STREET': ('Somerset', 'South West'),
    'WELLS': ('Somerset', 'South West'),
    'FROME': ('Somerset', 'South West'),
    'SHEPTON MALLET': ('Somerset', 'South West'),
    'MIDSOMER NORTON': ('Somerset', 'South West'),
    'RADSTOCK': ('Somerset', 'South West'),
    'TROWBRIDGE': ('Wiltshire', 'South West'),
    'MELKSHAM': ('Wiltshire', 'South West'),
    'CHIPPENHAM': ('Wiltshire', 'South West'),
    'DEVIZES': ('Wiltshire', 'South West'),
    'MARLBOROUGH': ('Wiltshire', 'South West'),
    'CALNE': ('Wiltshire', 'South West'),
    'WESTBURY': ('Wiltshire', 'South West'),
    'MATLOCK': ('Derbyshire', 'East Midlands'),
    'BUXTON': ('Derbyshire', 'East Midlands'),
    'GLOSSOP': ('Derbyshire', 'East Midlands'),
    'ASHBOURNE': ('Derbyshire', 'East Midlands'),
    'BAKEWELL': ('Derbyshire', 'East Midlands'),
    'ILKESTON': ('Derbyshire', 'East Midlands'),
    'LONG EATON': ('Derbyshire', 'East Midlands'),
    'SWADLINCOTE': ('Derbyshire', 'East Midlands'),
    'NEWHALL': ('Derbyshire', 'East Midlands'),
    'RIPLEY': ('Derbyshire', 'East Midlands'),
    'ALFRETON': ('Derbyshire', 'East Midlands'),
    'BOLSOVER': ('Derbyshire', 'East Midlands'),
    'DRONFIELD': ('Derbyshire', 'East Midlands'),
    'ECKINGTON': ('Derbyshire', 'East Midlands'),
    'WAINSCOTT': ('Kent', 'South East'),
    'CHATHAM': ('Kent', 'South East'),
    'ROCHESTER': ('Kent', 'South East'),
    'GILLINGHAM': ('Kent', 'South East'),
    'SITTINGBOURNE': ('Kent', 'South East'),
    'FAVERSHAM': ('Kent', 'South East'),
    'FOLKESTONE': ('Kent', 'South East'),
    'HYTHE': ('Kent', 'South East'),
    'DEAL': ('Kent', 'South East'),
    'SANDWICH': ('Kent', 'South East'),
    'MARGATE': ('Kent', 'South East'),
    'RAMSGATE': ('Kent', 'South East'),
    'BROADSTAIRS': ('Kent', 'South East'),
    'WHITSTABLE': ('Kent', 'South East'),
    'HERNE BAY': ('Kent', 'South East'),
    'SEVENOAKS': ('Kent', 'South East'),
    'TONBRIDGE': ('Kent', 'South East'),
    'TUNBRIDGE WELLS': ('Kent', 'South East'),
    'GRAVESEND': ('Kent', 'South East'),
    'DARTFORD': ('Kent', 'South East'),
    'SWANLEY': ('Kent', 'South East'),
    'ASHFORD': ('Kent', 'South East'),
    'DOVER': ('Kent', 'South East'),
    'SAINT MARGARETS AT CLIFFE': ('Kent', 'South East'),
    'GREAT BOUGHTON': ('Cheshire', 'North West'),
    'LEFTWICH': ('Cheshire', 'North West'),
    'NORTHWICH': ('Cheshire', 'North West'),
    'NANTWICH': ('Cheshire', 'North West'),
    'SANDBACH': ('Cheshire', 'North West'),
    'MIDDLEWICH': ('Cheshire', 'North West'),
    'WINSFORD': ('Cheshire', 'North West'),
    'CONGLETON': ('Cheshire', 'North West'),
    'MACCLESFIELD': ('Cheshire', 'North West'),
    'WILMSLOW': ('Cheshire', 'North West'),
    'KNUTSFORD': ('Cheshire', 'North West'),
    'FRODSHAM': ('Cheshire', 'North West'),
    'ELLESMERE PORT': ('Cheshire', 'North West'),
    'RUNCORN': ('Cheshire', 'North West'),
    'WIDNES': ('Cheshire', 'North West'),
    'WARRINGTON': ('Cheshire', 'North West'),
    'ENDERBY': ('Leicestershire', 'East Midlands'),
    'HINCKLEY': ('Leicestershire', 'East Midlands'),
    'COALVILLE': ('Leicestershire', 'East Midlands'),
    'LOUGHBOROUGH': ('Leicestershire', 'East Midlands'),
    'MELTON MOWBRAY': ('Leicestershire', 'East Midlands'),
    'MARKET HARBOROUGH': ('Leicestershire', 'East Midlands'),
    'LUTTERWORTH': ('Leicestershire', 'East Midlands'),
    'WIGSTON': ('Leicestershire', 'East Midlands'),
    'OADBY': ('Leicestershire', 'East Midlands'),
    'BLABY': ('Leicestershire', 'East Midlands'),
    'NARBOROUGH': ('Leicestershire', 'East Midlands'),
    'NORTH WEST LEICESTERSHIRE': ('Leicestershire', 'East Midlands'),
    'THORNTON-CLEVELEYS': ('Lancashire', 'North West'),
    'LYTHAM SAINT ANNES': ('Lancashire', 'North West'),
    'MORECAMBE': ('Lancashire', 'North West'),
    'LANCASTER': ('Lancashire', 'North West'),
    'BURNLEY': ('Lancashire', 'North West'),
    'NELSON': ('Lancashire', 'North West'),
    'COLNE': ('Lancashire', 'North West'),
    'ACCRINGTON': ('Lancashire', 'North West'),
    'ROSSENDALE': ('Lancashire', 'North West'),
    'CHORLEY': ('Lancashire', 'North West'),
    'LEYLAND': ('Lancashire', 'North West'),
    'SKELMERSDALE': ('Lancashire', 'North West'),
    'ORMSKIRK': ('Lancashire', 'North West'),
    'FLEETWOOD': ('Lancashire', 'North West'),
    'GARSTANG': ('Lancashire', 'North West'),
    'CLITHEROE': ('Lancashire', 'North West'),
    'LONGRIDGE': ('Lancashire', 'North West'),
    'THUNDERSLEY': ('Essex', 'East of England'),
    'BENFLEET': ('Essex', 'East of England'),
    'CANVEY ISLAND': ('Essex', 'East of England'),
    'RAYLEIGH': ('Essex', 'East of England'),
    'LEIGH-ON-SEA': ('Essex', 'East of England'),
    'SOUTHEND-ON-SEA': ('Essex', 'East of England'),
    'WESTCLIFF-ON-SEA': ('Essex', 'East of England'),
    'BASILDON': ('Essex', 'East of England'),
    'WICKFORD': ('Essex', 'East of England'),
    'BILLERICAY': ('Essex', 'East of England'),
    'BRENTWOOD': ('Essex', 'East of England'),
    'HARLOW': ('Essex', 'East of England'),
    'EPPING': ('Essex', 'East of England'),
    'LOUGHTON': ('Essex', 'East of England'),
    'CHIGWELL': ('Essex', 'East of England'),
    'GRAYS': ('Essex', 'East of England'),
    'TILBURY': ('Essex', 'East of England'),
    'STANFORD LE HOPE': ('Essex', 'East of England'),
    'SOUTH OCKENDON': ('Essex', 'East of England'),
    'WITHAM': ('Essex', 'East of England'),
    'BRAINTREE': ('Essex', 'East of England'),
    'HALSTEAD': ('Essex', 'East of England'),
    'SAFFRON WALDEN': ('Essex', 'East of England'),
    'GREAT DUNMOW': ('Essex', 'East of England'),
    'MALDON': ('Essex', 'East of England'),
    'BURTON-ON-TRENT': ('Staffordshire', 'West Midlands'),
    'BRANSTON': ('Staffordshire', 'West Midlands'),
    'UTTOXETER': ('Staffordshire', 'West Midlands'),
    'RUGELEY': ('Staffordshire', 'West Midlands'),
    'TAMWORTH': ('Staffordshire', 'West Midlands'),
    'NEWMARKET': ('Suffolk', 'East of England'),
    'BURY ST EDMUNDS': ('Suffolk', 'East of England'),
    'STOWMARKET': ('Suffolk', 'East of England'),
    'SUDBURY': ('Suffolk', 'East of England'),
    'HAVERHILL': ('Suffolk', 'East of England'),
    'LOWESTOFT': ('Suffolk', 'East of England'),
    'BECCLES': ('Suffolk', 'East of England'),
    'EYE': ('Suffolk', 'East of England'),
    'WETHERBY': ('West Yorkshire', 'Yorkshire and The Humber'),
    'WALTERS ASH': ('Buckinghamshire', 'South East'),
    'BRACKNELL': ('Berkshire', 'South East'),
    'READING': ('Berkshire', 'South East'),
    'WOKINGHAM': ('Berkshire', 'South East'),
    'SLOUGH': ('Berkshire', 'South East'),
    'WINDSOR': ('Berkshire', 'South East'),
    'ASCOT': ('Berkshire', 'South East'),
    'WOKING': ('Surrey', 'South East'),
    'REIGATE': ('Surrey', 'South East'),
    'DORKING': ('Surrey', 'South East'),
    'LEATHERHEAD': ('Surrey', 'South East'),
    'EPSOM': ('Surrey', 'South East'),
    'ESHER': ('Surrey', 'South East'),
    'COBHAM': ('Surrey', 'South East'),
    'WEYBRIDGE': ('Surrey', 'South East'),
    'GODALMING': ('Surrey', 'South East'),
    'HASLEMERE': ('Surrey', 'South East'),
    'CRANLEIGH': ('Surrey', 'South East'),
    'CAMBERLEY': ('Surrey', 'South East'),
    'FRIMLEY': ('Surrey', 'South East'),
    'STAINES': ('Surrey', 'South East'),
    'SUNBURY': ('Surrey', 'South East'),
    'WALTON-ON-THAMES': ('Surrey', 'South East'),
    'NEW HAW': ('Surrey', 'South East'),
    'SOUTH MIMMS': ('Hertfordshire', 'East of England'),
    'HERTFORD': ('Hertfordshire', 'East of England'),
    'WARE': ('Hertfordshire', 'East of England'),
    'HODDESDON': ('Hertfordshire', 'East of England'),
    'BROXBOURNE': ('Hertfordshire', 'East of England'),
    'CHESHUNT': ('Hertfordshire', 'East of England'),
    'POTTERS BAR': ('Hertfordshire', 'East of England'),
    'HATFIELD': ('Hertfordshire', 'East of England'),
    'WELWYN GARDEN CITY': ('Hertfordshire', 'East of England'),
    'STEVENAGE': ('Hertfordshire', 'East of England'),
    'HITCHIN': ('Hertfordshire', 'East of England'),
    'LETCHWORTH': ('Hertfordshire', 'East of England'),
    'BALDOCK': ('Hertfordshire', 'East of England'),
    'ROYSTON': ('Hertfordshire', 'East of England'),
    'BISHOPS STORTFORD': ('Hertfordshire', 'East of England'),
    'BOREHAMWOOD': ('Hertfordshire', 'East of England'),
    'ELSTREE': ('Hertfordshire', 'East of England'),
    'BUSHEY': ('Hertfordshire', 'East of England'),
    'WATFORD': ('Hertfordshire', 'East of England'),
    'RICKMANSWORTH': ('Hertfordshire', 'East of England'),
    'HEMEL HEMPSTEAD': ('Hertfordshire', 'East of England'),
    'BERKHAMSTED': ('Hertfordshire', 'East of England'),
    'TRING': ('Hertfordshire', 'East of England'),
    'ST ALBANS': ('Hertfordshire', 'East of England'),
    'HARPENDEN': ('Hertfordshire', 'East of England'),
    'CORBY': ('Northamptonshire', 'East Midlands'),
    'KETTERING': ('Northamptonshire', 'East Midlands'),
    'WELLINGBOROUGH': ('Northamptonshire', 'East Midlands'),
    'RUSHDEN': ('Northamptonshire', 'East Midlands'),
    'NORTHAMPTON': ('Northamptonshire', 'East Midlands'),
    'DAVENTRY': ('Northamptonshire', 'East Midlands'),
    'TOWCESTER': ('Northamptonshire', 'East Midlands'),
    'BRACKLEY': ('Northamptonshire', 'East Midlands'),
    'GRANTHAM': ('Lincolnshire', 'East Midlands'),
    'SLEAFORD': ('Lincolnshire', 'East Midlands'),
    'SPALDING': ('Lincolnshire', 'East Midlands'),
    'BOSTON': ('Lincolnshire', 'East Midlands'),
    'SKEGNESS': ('Lincolnshire', 'East Midlands'),
    'GAINSBOROUGH': ('Lincolnshire', 'East Midlands'),
    'MARKET RASEN': ('Lincolnshire', 'East Midlands'),
    'LOUTH': ('Lincolnshire', 'East Midlands'),
    'HORNCASTLE': ('Lincolnshire', 'East Midlands'),
    'STAMFORD': ('Lincolnshire', 'East Midlands'),
    'BOURNE': ('Lincolnshire', 'East Midlands'),
    'MANSFIELD': ('Nottinghamshire', 'East Midlands'),
    'KIRKBY IN ASHFIELD': ('Nottinghamshire', 'East Midlands'),
    'SUTTON IN ASHFIELD': ('Nottinghamshire', 'East Midlands'),
    'GAWCOTT': ('Buckinghamshire', 'South East'),
    'HANSLOPE': ('Buckinghamshire', 'South East'),
    'AYLESBURY': ('Buckinghamshire', 'South East'),
    'BUCKINGHAM': ('Buckinghamshire', 'South East'),
    'MARLOW': ('Buckinghamshire', 'South East'),
    'BEACONSFIELD': ('Buckinghamshire', 'South East'),
    'CHESHAM': ('Buckinghamshire', 'South East'),
    'AMERSHAM': ('Buckinghamshire', 'South East'),
    'PRINCES RISBOROUGH': ('Buckinghamshire', 'South East'),
    'BRIGHTON': ('East Sussex', 'South East'),
    'HASTINGS': ('East Sussex', 'South East'),
    'EASTBOURNE': ('East Sussex', 'South East'),
    'LEWES': ('East Sussex', 'South East'),
    'CROWBOROUGH': ('East Sussex', 'South East'),
    'UCKFIELD': ('East Sussex', 'South East'),
    'BATTLE': ('East Sussex', 'South East'),
    'RYE': ('East Sussex', 'South East'),
    'BEXHILL-ON-SEA': ('East Sussex', 'South East'),
    'HAILSHAM': ('East Sussex', 'South East'),
    'SEAFORD': ('East Sussex', 'South East'),
    'NEWHAVEN': ('East Sussex', 'South East'),
    'PEACEHAVEN': ('East Sussex', 'South East'),
    'HEATHFIELD': ('East Sussex', 'South East'),
    'WADHURST': ('East Sussex', 'South East'),
    'R A F SAINT MAWGAN': ('Cornwall', 'South West'),
    'CIRENCESTER': ('Gloucestershire', 'South West'),
    'STROUD': ('Gloucestershire', 'South West'),
    'CHELTENHAM': ('Gloucestershire', 'South West'),
    'TEWKESBURY': ('Gloucestershire', 'South West'),
    'BOURTON-ON-THE-WATER': ('Gloucestershire', 'South West'),
    'STOW-ON-THE-WOLD': ('Gloucestershire', 'South West'),
    'DURSLEY': ('Gloucestershire', 'South West'),
    'LYDNEY': ('Gloucestershire', 'South West'),
    'CINDERFORD': ('Gloucestershire', 'South West'),
    'COLEFORD': ('Gloucestershire', 'South West'),
    'EPISKOPI': ('', ''),  # Cyprus - non-UK
    'PEABODY': ('', ''),  # USA - non-UK
    'BALCARCE': ('', ''),  # Argentina - non-UK
    'STANLEY': ('', ''),  # Falkland Islands
    # ── Unresolved towns from first pass ──
    'TANGHAM': ('Suffolk', 'East of England'),  # Tangham near Woodbridge
    'SANDGATE': ('Kent', 'South East'),
    'NAPHILL': ('Buckinghamshire', 'South East'),
    'LITTLE NESTON': ('Cheshire', 'North West'),
    'GUILDFORD COURT': ('Surrey', 'South East'),  # In Guildford
    'PORTCHESTER': ('Hampshire', 'South East'),
    'BROMBOROUGH': ('Merseyside', 'North West'),
    'GREAT HOLM': ('Buckinghamshire', 'South East'),  # Milton Keynes
    'WOODFORD GREEN': ('Greater London', 'Greater London'),
    'WESTON-ON-TRENT': ('Derbyshire', 'East Midlands'),
    'WESTCROFT': ('Buckinghamshire', 'South East'),  # Milton Keynes
    'ST NEOTS': ('Cambridgeshire', 'East of England'),
    'SIMPSON': ('Buckinghamshire', 'South East'),  # Milton Keynes
    'SHAFTON': ('South Yorkshire', 'Yorkshire and The Humber'),
    'POTT SHRIGLEY': ('Cheshire', 'North West'),
    'PEAK DALE': ('Derbyshire', 'East Midlands'),
    'MENWITH HILL': ('North Yorkshire', 'Yorkshire and The Humber'),
    'MATLOCK DALE': ('Derbyshire', 'East Midlands'),
    'LYTHAM': ('Lancashire', 'North West'),
    'LONGMOOR': ('Hampshire', 'South East'),
    'LITTLEOVER': ('Derbyshire', 'East Midlands'),
    'LANGDON HILLS': ('Essex', 'East of England'),
    'HOYLAND': ('South Yorkshire', 'Yorkshire and The Humber'),
    'GREAT CROSBY': ('Merseyside', 'North West'),
    'GALLEY COMMON': ('Warwickshire', 'West Midlands'),
    'BRERETON': ('Staffordshire', 'West Midlands'),
    'BOULMER': ('Northumberland', 'North East'),
    'BASSENTHWAITE LAKE': ('Cumbria', 'North West'),
    'ASHTON-IN-MAKERFIELD': ('Greater Manchester', 'North West'),
    'WORSBROUGH': ('South Yorkshire', 'Yorkshire and The Humber'),
    'STANTON IN PEAK': ('Derbyshire', 'East Midlands'),
    'SARISBURY GREEN': ('Hampshire', 'South East'),
    'SAINT GEORGES': ('Shropshire', 'West Midlands'),
    'RUSTHALL': ('Kent', 'South East'),
    'RIDDINGS': ('Derbyshire', 'East Midlands'),
    'HOLMBURY SAINT MARY': ('Surrey', 'South East'),
    'HARMONDSWORTH': ('Greater London', 'Greater London'),
    'DENBY VILLAGE': ('Derbyshire', 'East Midlands'),
    'CATCLIFFE': ('South Yorkshire', 'Yorkshire and The Humber'),
    'CALCOT': ('Berkshire', 'South East'),
    'BURY SAINT EDMUNDS': ('Suffolk', 'East of England'),
    'MARSTON GREEN': ('West Midlands', 'West Midlands'),
    'RAF WYTON & RAF BRAMPTON': ('Cambridgeshire', 'East of England'),
    'RAf WYTON & RAf BRAMPTON': ('Cambridgeshire', 'East of England'),
    'UPPER MARHAM': ('Norfolk', 'East of England'),
    'WATTISHAM AIRFIELD': ('Suffolk', 'East of England'),
    'DISHFORTH AIRFIELD': ('North Yorkshire', 'Yorkshire and The Humber'),
    'HOPE VALLEY': ('Derbyshire', 'East Midlands'),
    'HALE VILLAGE': ('Merseyside', 'North West'),
    'STOCKBRIDGE VILLAGE': ('Merseyside', 'North West'),
    'LEA GREEN': ('Derbyshire', 'East Midlands'),
    'KNOWSLEY VILLAGE': ('Merseyside', 'North West'),
    'BRIDGEMERE': ('Cheshire', 'North West'),
    'ALFERTON': ('Derbyshire', 'East Midlands'),  # Typo for Alfreton
    'ALFRETON': ('Derbyshire', 'East Midlands'),
    'STROOD': ('Kent', 'South East'),
    'EARLEY': ('Berkshire', 'South East'),
    'CHAPEL-EN-LE-FRITH': ('Derbyshire', 'East Midlands'),
    'CHAPEL': ('Derbyshire', 'East Midlands'),  # Chapel-en-le-Frith
    'ECKINGTON': ('Derbyshire', 'East Midlands'),
    'AMBERGATE': ('Derbyshire', 'East Midlands'),
    'ILKESTON': ('Derbyshire', 'East Midlands'),
    'SHEERNESS': ('Kent', 'South East'),
    'ARUNDEL': ('West Sussex', 'South East'),
    'DEVIZES': ('Wiltshire', 'South West'),
    'DARLINGTON': ('Durham', 'North East'),
    'PRESCOT': ('Merseyside', 'North West'),
    'DIDCOT': ('Oxfordshire', 'South East'),
    'CHILTON': ('Durham', 'North East'),  # UKHSA Chilton is in Oxfordshire but common usage is Durham
    'PORTON DOWN': ('Wiltshire', 'South West'),
    'WESTVALE': ('Merseyside', 'North West'),
    'HENGOED': ('Mid Glamorgan', 'Wales'),
    'LLANDUDNO JUNCTION': ('Gwynedd', 'Wales'),
    'BLAENAU FFESTINIOG': ('Gwynedd', 'Wales'),
    'ACREFAIR': ('Clwyd', 'Wales'),
    'TIR-Y-BERTH': ('Mid Glamorgan', 'Wales'),
    'BEAUFORT': ('Gwent', 'Wales'),
    'CROSSKEYS': ('Gwent', 'Wales'),
    'LLANFRECHFA': ('Gwent', 'Wales'),
    'LLANSAMLET': ('West Glamorgan', 'Wales'),
    'PENGAM': ('Mid Glamorgan', 'Wales'),
    'RUMNEY': ('South Glamorgan', 'Wales'),
    'SOUTH WEST WALES': ('Dyfed', 'Wales'),
    'NATIONAL ASSEMBLY FOR WALES': ('South Glamorgan', 'Wales'),
}

# ── 6. County names for detection in raw_location ────────────────────────────
COUNTY_NAMES = {}  # populated from county_to_region_mapping.csv


# County names that are too common as English words and cause false positives
COUNTY_BLOCKLIST = {'DOWN', 'FIFE', 'BRISTOL', 'DURHAM', 'RUTLAND'}


def detect_county_in_text(text):
    """Check if a known county name appears in the text."""
    text_upper = text.upper()
    for county_upper, info in COUNTY_NAMES.items():
        if county_upper in COUNTY_BLOCKLIST:
            continue
        # Skip very short county abbreviations that match common words
        if len(county_upper) <= 4:
            continue
        pattern = r'\b' + re.escape(county_upper) + r'\b'
        if re.search(pattern, text_upper):
            return info
    return None


# ── 7. Region name hints in text ─────────────────────────────────────────────
REGION_HINTS = {
    'NORTH EAST ENGLAND': 'North East',
    'NORTH WEST ENGLAND': 'North West',
    'YORKSHIRE AND THE HUMBER': 'Yorkshire and The Humber',
    'YORKSHIRE AND HUMBER': 'Yorkshire and The Humber',
    'EAST MIDLANDS': 'East Midlands',
    'WEST MIDLANDS': 'West Midlands',
    'EAST OF ENGLAND': 'East of England',
    'GREATER LONDON': 'Greater London',
    'SOUTH EAST ENGLAND': 'South East',
    'SOUTH WEST ENGLAND': 'South West',
    'SOUTH EAST': 'South East',
    'SOUTH WEST': 'South West',
    'NORTH EAST': 'North East',
    'NORTH WEST': 'North West',
}

# ── 8. Non-UK country codes ─────────────────────────────────────────────────
NON_UK_PHRASES = [
    'FALKLAND', 'CYPRUS', 'ARGENTINA', 'MASSACHUSETTS',
    'BUENOS AIRES', 'LIMASSOL', 'EPISKOPI', 'PEABODY, US',
    'NANYUKI, KENYA', 'BFPO 680', 'BFPO 52', 'BFPO 16',
    'JOHANNESBURG', 'ULAANBAATAR',
    'HMNB GIBRALTAR',
]

NON_UK_COUNTRY_CODES = {'US', 'AR', 'CY', 'FK', 'AU', 'NZ', 'IE', 'FR',
                        'DE', 'IN', 'KE', 'ZA', 'MN', 'JE'}

# Patterns that end with ", XX" where XX is a non-UK country code
NON_UK_SUFFIX_RE = re.compile(r',\s*(?:US|AR|CY|AU|ZA|MN|JE|IE)\s*$', re.I)


def is_non_uk(raw_location, country_code):
    """Check if location is non-UK."""
    if country_code and country_code.upper() not in ('GB', 'UK', ''):
        if country_code.upper() in NON_UK_COUNTRY_CODES:
            return True
    raw_upper = raw_location.upper()
    for phrase in NON_UK_PHRASES:
        if phrase in raw_upper:
            return True
    if NON_UK_SUFFIX_RE.search(raw_location):
        return True
    # "California, City, US" / "Michigan, City, US" / "Victoria, City, AU"
    if re.match(r'^(?:California|Michigan|Ohio|Massachusetts|Victoria|Gauteng|County Dublin)', raw_location, re.I):
        return True
    return False


def is_multi_location(raw_location):
    """Check if location string contains multiple locations."""
    if ' : ' in raw_location:
        return True
    # Long comma-separated lists of cities
    if raw_location.count(',') > 6 and any(
        city in raw_location.upper() for city in
        ['BIRMINGHAM', 'MANCHESTER', 'LEEDS', 'GLASGOW', 'EDINBURGH']
    ):
        return True
    return False


# ── Main processing ──────────────────────────────────────────────────────────
def extract_candidate_towns(raw_location):
    """Extract possible town names from complex raw_location strings.

    Tries multiple parsing strategies to pull real town/city names from
    addresses, building names, HMP descriptions, etc.
    """
    candidates = []
    raw = raw_location.strip()

    # "England/Scotland/Wales/Cymru/Northern Ireland, Town, GB" format
    m = re.match(r'^(?:England|Scotland|Wales|Cymru|Northern Ireland),\s*(.+?),\s*GB$', raw, re.I)
    if m:
        candidates.append(m.group(1).strip().upper())
        return candidates  # This format is reliable, don't add noisy extras

    # "HM PRISON/HMP NAME TOWN, POSTCODE" - extract the town after prison name
    m = re.search(r'(?:HM\s+PRISON|HMP|HMYOI)\s+[\w\s]+?\s+([A-Z][\w\s-]+?)(?:,|\s+[A-Z]{1,2}\d)', raw, re.I)
    if m:
        town = m.group(1).strip().upper()
        if town not in ('THE', 'AND', 'AT', 'IN', 'ON'):
            candidates.append(town)

    # "Town, County/Postcode" format (but not "Wales, Town")
    m = re.match(r'^([A-Za-z][A-Za-z\s\'-]+?),\s*([A-Za-z\s]+?)(?:,|$)', raw)
    if m:
        first = m.group(1).strip().upper()
        # Don't add country names as town candidates
        if first not in ('ENGLAND', 'SCOTLAND', 'WALES', 'CYMRU', 'NORTHERN IRELAND',
                         'THIS POSITION IS BASED AT', 'THIS POSITION CAN BE BASED AT',
                         'THESE POSITIONS ARE BASED AT', 'ORGANISATION LOCATION'):
            candidates.append(first)

    # Comma-separated parts - pick plausible town names
    parts = [p.strip() for p in raw.split(',')]
    for p in parts:
        p_clean = p.strip().upper()
        if any(skip in p_clean for skip in [
            'UNITED KINGDOM', 'HYBRID', 'FLEXIBLE', 'ROAD', 'STREET',
            'LANE', 'AVENUE', 'DRIVE', 'WAY', 'CLOSE', 'CENTRE', 'OFFICES',
            'HOUSE', 'HALL', 'BUILDING', 'CAMPUS', 'COUNCIL', 'SCHOOL',
            'PRISON', 'POSITION', 'BASED', 'PLEASE', 'WORKING', 'ELEMENT',
            'ENGLAND', 'SCOTLAND', 'WALES', 'CYMRU', 'ORGANISATION',
            'REGIONAL', 'SECTION', 'DEPARTMENT', 'BARRACKS', 'DEPOT',
        ]):
            continue
        if re.match(r'^\d|^[A-Z]{1,2}\d', p_clean):
            continue
        if len(p_clean) > 2 and len(p_clean) < 40:
            candidates.append(p_clean)

    return candidates


def resolve_location(raw_location, town_city, country_region, country_code,
                     existing_region, town_lookup, county_region_map):
    """Resolve county and region for a single location row.

    Returns (region, county, confidence, method).
    """
    raw_upper = raw_location.upper().strip()
    town_upper = town_city.upper().strip()
    cr_upper = country_region.upper().strip()

    # ── Check non-UK ──
    if is_non_uk(raw_location, country_code):
        return ('Non-UK', '', 'high', 'non_uk')

    # ── Check multi-location ──
    if is_multi_location(raw_location):
        return ('Multiple', '', 'high', 'multi_location')

    # ── Strategy 1: Look up town_city in location lookup CSV ──
    if town_upper in town_lookup:
        info = town_lookup[town_upper]
        county = info['county']
        region = info['region'] or existing_region
        return (region, county, 'high', 'location_lookup')

    # ── Strategy 2: Look up town_city in supplementary towns ──
    if town_upper in SUPPLEMENTARY_TOWNS:
        county, region = SUPPLEMENTARY_TOWNS[town_upper]
        if not region and existing_region:
            region = existing_region
        return (region or existing_region, county, 'high', 'supplementary')

    # ── Strategy 3: Extract candidate towns from raw_location and look up ──
    candidates = extract_candidate_towns(raw_location)
    for candidate in candidates:
        if candidate in town_lookup:
            info = town_lookup[candidate]
            return (info['region'] or existing_region, info['county'],
                    'high', 'candidate_lookup')
        if candidate in SUPPLEMENTARY_TOWNS:
            county, region = SUPPLEMENTARY_TOWNS[candidate]
            return (region or existing_region, county, 'high', 'candidate_supplementary')

    # ── Strategy 4: Detect county name in raw_location ──
    county_info = detect_county_in_text(raw_location)
    if county_info:
        return (county_info['region'] or existing_region,
                county_info['county'], 'high', 'county_in_raw')

    # ── Strategy 5: Detect county name in country_region field ──
    county_info = detect_county_in_text(country_region)
    if county_info:
        return (county_info['region'] or existing_region,
                county_info['county'], 'high', 'county_in_field')

    # ── Strategy 6: London borough detection ──
    if town_upper in LONDON_BOROUGHS:
        return ('Greater London', 'Greater London', 'high', 'london_borough')

    # Check if raw_location mentions London boroughs
    for borough in LONDON_BOROUGHS:
        if borough in raw_upper:
            return ('Greater London', 'Greater London', 'high', 'london_borough_in_raw')

    # ── Strategy 7: Postcode extraction ──
    pc_area = extract_postcode_area(raw_location)
    if pc_area and pc_area in POSTCODE_MAP:
        county, region = POSTCODE_MAP[pc_area]
        return (region or existing_region, county, 'medium', 'postcode')

    # ── Strategy 8: Region hint in raw text ──
    for hint, region in REGION_HINTS.items():
        if hint in raw_upper:
            return (region, '', 'medium', 'region_hint')

    # ── Strategy 9: country_region or raw_location prefix hints ──
    # "Wales, Town, GB" or "Cymru, Town, GB" entries
    if raw_upper.startswith('WALES,') or raw_upper.startswith('CYMRU,'):
        return ('Wales', '', 'medium', 'wales_prefix')
    if raw_upper.startswith('SCOTLAND,'):
        return ('Scotland', '', 'medium', 'scotland_prefix')
    if raw_upper.startswith('NORTHERN IRELAND,'):
        return ('Northern Ireland', '', 'medium', 'ni_prefix')

    if cr_upper in ('ENGLAND', 'SCOTLAND', 'WALES', 'NORTHERN IRELAND', 'CYMRU'):
        if cr_upper == 'SCOTLAND':
            return ('Scotland', '', 'medium', 'country_hint')
        if cr_upper in ('WALES', 'CYMRU'):
            return ('Wales', '', 'medium', 'country_hint')
        if cr_upper == 'NORTHERN IRELAND':
            return ('Northern Ireland', '', 'medium', 'country_hint')

    # ── Strategy 10: Check if raw_location mentions London ──
    if 'LONDON' in raw_upper:
        return ('Greater London', 'Greater London', 'medium', 'london_keyword')

    # ── Strategy 11: Use existing region to infer county from context ──
    # If we have a region but no county, try to find county from postcode
    # or leave county blank (region is still useful)
    if existing_region:
        return (existing_region, '', 'low', 'existing_region_only')

    # ── No match ──
    return ('', '', 'review', 'unresolved')


def main():
    # Load data
    town_lookup = load_location_lookup()
    county_region_map = load_county_to_region()

    # Populate COUNTY_NAMES from the mapping
    for county_upper, info in county_region_map.items():
        COUNTY_NAMES[county_upper] = info

    # Also add some additional county name variants
    additional_counties = {
        'NORTHANTS': {'county': 'Northamptonshire', 'region': 'East Midlands'},
        'HANTS': {'county': 'Hampshire', 'region': 'South East'},
        'BEDS': {'county': 'Bedfordshire', 'region': 'East of England'},
        'BERKS': {'county': 'Berkshire', 'region': 'South East'},
        'BUCKS': {'county': 'Buckinghamshire', 'region': 'South East'},
        'CAMBS': {'county': 'Cambridgeshire', 'region': 'East of England'},
        'HERTS': {'county': 'Hertfordshire', 'region': 'East of England'},
        'LANCS': {'county': 'Lancashire', 'region': 'North West'},
        'LEICS': {'county': 'Leicestershire', 'region': 'East Midlands'},
        'LINCS': {'county': 'Lincolnshire', 'region': 'East Midlands'},
        'NOTTS': {'county': 'Nottinghamshire', 'region': 'East Midlands'},
        'OXON': {'county': 'Oxfordshire', 'region': 'South East'},
        'STAFFS': {'county': 'Staffordshire', 'region': 'West Midlands'},
        'WARKS': {'county': 'Warwickshire', 'region': 'West Midlands'},
        'WILTS': {'county': 'Wiltshire', 'region': 'South West'},
        'WORCS': {'county': 'Worcestershire', 'region': 'West Midlands'},
    }
    COUNTY_NAMES.update(additional_counties)

    # Load review data
    with open('/tmp/review_rows.json', 'r') as f:
        data = json.load(f)

    header = data['header']
    rows = data['rows']

    # Process each row
    results = []
    for i, row in enumerate(rows):
        raw_location = row[0]  # A
        town_city = row[1]     # B
        country_region = row[2]  # C
        country_code = row[3]  # D
        vacancy_count = row[4]  # E
        existing_region = row[5]  # F
        existing_county = row[6]  # G
        confidence = row[7]  # H
        source = row[8]  # I
        done = row[9]  # J

        region, county, conf, method = resolve_location(
            raw_location, town_city, country_region, country_code,
            existing_region, town_lookup, county_region_map
        )

        # If we have an existing region and our result is empty, keep existing
        if existing_region and not region:
            region = existing_region

        # If existing region and ours differ, flag for review
        region_mismatch = ''
        if existing_region and region and existing_region != region:
            if region not in ('Non-UK', 'Multiple'):
                region_mismatch = f'WAS:{existing_region}'

        results.append({
            'sheet_row': i + 2,  # 1-indexed, +1 for header
            'raw_location': raw_location,
            'town_city': town_city,
            'country_region': country_region,
            'suggested_region': region,
            'suggested_county': county,
            'confidence': conf,
            'method': method,
            'existing_region': existing_region,
            'region_mismatch': region_mismatch,
        })

    # Write output CSV
    output_path = 'review_location_mappings.csv'
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'sheet_row', 'raw_location', 'town_city', 'country_region',
            'suggested_region', 'suggested_county', 'confidence', 'method',
            'existing_region', 'region_mismatch'
        ])
        writer.writeheader()
        writer.writerows(results)

    # Summary stats
    resolved_county = sum(1 for r in results if r['suggested_county'])
    resolved_region = sum(1 for r in results if r['suggested_region'])
    mismatches = sum(1 for r in results if r['region_mismatch'])
    by_method = {}
    for r in results:
        m = r['method']
        by_method[m] = by_method.get(m, 0) + 1

    print(f'Total rows: {len(results)}')
    print(f'County resolved: {resolved_county} / {len(results)}')
    print(f'Region resolved: {resolved_region} / {len(results)}')
    print(f'Region mismatches: {mismatches}')
    print()
    print('By method:')
    for m, c in sorted(by_method.items(), key=lambda x: -x[1]):
        print(f'  {m}: {c}')
    print()
    print(f'Output written to: {output_path}')

    # Show mismatches
    if mismatches:
        print(f'\n=== Region mismatches ({mismatches}) ===')
        for r in results:
            if r['region_mismatch']:
                print(f"  Row {r['sheet_row']}: {r['raw_location'][:60]}... "
                      f"-> {r['suggested_region']} ({r['region_mismatch']})")

    # Show unresolved
    unresolved = [r for r in results if r['method'] == 'unresolved']
    if unresolved:
        print(f'\n=== Unresolved ({len(unresolved)}) ===')
        for r in unresolved:
            print(f"  Row {r['sheet_row']}: raw={r['raw_location'][:80]}, "
                  f"town={r['town_city']}, region={r['existing_region']}")


if __name__ == '__main__':
    main()
