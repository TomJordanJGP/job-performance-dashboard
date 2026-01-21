"""
Script to copy data from a BigQuery connected sheet to a regular Google Sheet.
This is needed because BigQuery connected sheets can't be read via the normal Sheets API.
"""

import gspread
from google.oauth2.service_account import Credentials

# Configuration
SPREADSHEET_ID = "1XvVxCV8oo-qwZOwdHfsqMTIljHQ1gHISfZoIvVI8i7U"
BIGQUERY_SHEET_NAME = "job-performance-details_combined_2"
NEW_SHEET_NAME = "job_data_regular"  # We'll create this as a regular sheet

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
]

def main():
    print("🔧 Connecting to Google Sheets...")

    # Connect to Google Sheets
    creds = Credentials.from_service_account_file(
        'service_account.json',
        scopes=SCOPES
    )
    client = gspread.authorize(creds)

    print(f"📊 Opening spreadsheet: {SPREADSHEET_ID}")
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    print(f"\n📋 Available sheets:")
    for ws in spreadsheet.worksheets():
        print(f"  - {ws.title}")

    # Try to read the BigQuery sheet using get_all_values
    print(f"\n🔍 Attempting to read BigQuery sheet: '{BIGQUERY_SHEET_NAME}'...")

    try:
        source_sheet = spreadsheet.worksheet(BIGQUERY_SHEET_NAME)

        # For BigQuery sheets, we need to get the visible range of data
        # This might return an empty result if the sheet hasn't been "extracted"
        all_values = source_sheet.get_all_values()

        if not all_values or len(all_values) == 0:
            print("\n❌ ERROR: The BigQuery sheet appears empty or can't be read.")
            print("\nThis usually means:")
            print("1. The BigQuery data needs to be extracted/refreshed in Google Sheets first")
            print("2. BigQuery connected sheets have API limitations")
            print("\n💡 SOLUTION:")
            print("In Google Sheets:")
            print("1. Click on the BigQuery sheet tab")
            print("2. Click 'Extract' button in the BigQuery toolbar")
            print("3. Wait for extraction to complete")
            print("4. OR manually copy all data and paste into a new regular sheet")
            return

        print(f"✅ Successfully read {len(all_values)} rows (including header)")
        print(f"   Columns: {len(all_values[0])}")

        # Check if the regular sheet already exists
        try:
            regular_sheet = spreadsheet.worksheet(NEW_SHEET_NAME)
            print(f"\n⚠️  Sheet '{NEW_SHEET_NAME}' already exists. Deleting it...")
            spreadsheet.del_worksheet(regular_sheet)
        except:
            pass

        # Create new regular sheet
        print(f"\n📝 Creating new regular sheet: '{NEW_SHEET_NAME}'...")
        new_sheet = spreadsheet.add_worksheet(
            title=NEW_SHEET_NAME,
            rows=len(all_values),
            cols=len(all_values[0])
        )

        # Copy all data to the new sheet
        print(f"📤 Copying data to new sheet...")
        new_sheet.update('A1', all_values)

        print(f"\n✅ SUCCESS!")
        print(f"   Created sheet: '{NEW_SHEET_NAME}'")
        print(f"   Copied {len(all_values)} rows")
        print(f"\n💡 Next step: Update app.py to use sheet name: '{NEW_SHEET_NAME}'")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print(f"\nThis BigQuery sheet can't be accessed via API.")
        print("\n🔧 MANUAL WORKAROUND:")
        print("1. Open the Google Sheet in your browser")
        print("2. Click on the BigQuery sheet tab")
        print("3. Select all data (Ctrl+A or Cmd+A)")
        print("4. Copy (Ctrl+C or Cmd+C)")
        print("5. Create a new sheet tab (click + at bottom)")
        print("6. Paste the data (Ctrl+V or Cmd+V)")
        print(f"7. Rename the new sheet to '{NEW_SHEET_NAME}'")
        print(f"8. Update DATA_SHEET_NAME in app.py to '{NEW_SHEET_NAME}'")

if __name__ == "__main__":
    main()
