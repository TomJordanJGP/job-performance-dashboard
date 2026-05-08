"""Update the Review tab with suggested_region and suggested_county.

Reads mapping results from review_location_mappings.csv and writes
columns F (suggested_region) and G (suggested_county) in the Google Sheet.
Does NOT mark column J (done).
"""

import csv
import gspread
from google.oauth2.service_account import Credentials


def main():
    # Load mapping results
    mappings = {}
    with open('review_location_mappings.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sheet_row = int(row['sheet_row'])
            mappings[sheet_row] = {
                'region': row['suggested_region'],
                'county': row['suggested_county'],
                'confidence': row['confidence'],
                'method': row['method'],
                'existing_region': row['existing_region'],
                'mismatch': row['region_mismatch'],
            }

    # Connect to Google Sheet
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.readonly',
    ]
    creds = Credentials.from_service_account_file('service_account.json', scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key('1YPfZMxK2Rdl91JjAKd60xtjNinDfBe0DHpa5euFwmDc')
    ws = sh.worksheet('Review')

    # Read current data to verify row count
    all_data = ws.get_all_values()
    data_rows = len(all_data) - 1  # exclude header
    print(f'Sheet has {data_rows} data rows, mapping has {len(mappings)} entries')

    # Build batch updates for columns F (6) and G (7)
    # Also update H (confidence) and I (source/method) for traceability
    updates = []

    for sheet_row, m in sorted(mappings.items()):
        region = m['region']
        county = m['county']
        confidence = m['confidence']
        method = m['method']
        existing = m['existing_region']

        # Column F (suggested_region) - write our value
        # If existing differs from ours, prepend with our value so user sees both
        if region:
            updates.append({
                'range': f'F{sheet_row}',
                'values': [[region]],
            })

        # Column G (suggested_county) - always write (was empty for all rows)
        if county:
            updates.append({
                'range': f'G{sheet_row}',
                'values': [[county]],
            })

        # Column H (confidence) - update with our confidence
        updates.append({
            'range': f'H{sheet_row}',
            'values': [[confidence]],
        })

        # Column I (source) - update with our method
        updates.append({
            'range': f'I{sheet_row}',
            'values': [[method]],
        })

    print(f'Preparing {len(updates)} cell updates...')

    # Batch update in chunks (gspread limit)
    CHUNK_SIZE = 500
    for i in range(0, len(updates), CHUNK_SIZE):
        chunk = updates[i:i + CHUNK_SIZE]
        ws.batch_update(chunk, value_input_option='RAW')
        print(f'  Updated cells {i+1}-{min(i+CHUNK_SIZE, len(updates))}')

    # Summary
    regions_written = sum(1 for m in mappings.values() if m['region'])
    counties_written = sum(1 for m in mappings.values() if m['county'])
    mismatches = sum(1 for m in mappings.values() if m['mismatch'])
    print(f'\nDone!')
    print(f'  Regions written: {regions_written}')
    print(f'  Counties written: {counties_written}')
    print(f'  Region mismatches (changed from existing): {mismatches}')
    print(f'  Column J (done) NOT touched - ready for your review')


if __name__ == '__main__':
    main()
