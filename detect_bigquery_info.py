"""
Script to detect BigQuery connection information from a Google Sheet.
"""

import gspread
from google.oauth2.service_account import Credentials
import json

# Configuration
SPREADSHEET_ID = "1XvVxCV8oo-qwZOwdHfsqMTIljHQ1gHISfZoIvVI8i7U"
BIGQUERY_SHEET_NAME = "job-performance-details_combined_2"

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
]

def main():
    print("🔧 Connecting to Google Sheets...")

    creds = Credentials.from_service_account_file(
        'service_account.json',
        scopes=SCOPES
    )
    client = gspread.authorize(creds)

    print(f"📊 Opening spreadsheet: {SPREADSHEET_ID}")
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    print(f"\n🔍 Looking for BigQuery connection info in sheet: '{BIGQUERY_SHEET_NAME}'...")

    try:
        sheet = spreadsheet.worksheet(BIGQUERY_SHEET_NAME)

        # Get sheet metadata
        print(f"\n📋 Sheet ID: {sheet.id}")
        print(f"   Title: {sheet.title}")
        print(f"   Rows: {sheet.row_count}")
        print(f"   Cols: {sheet.col_count}")

        # Try to get sheet properties which might contain BigQuery info
        sheet_metadata = spreadsheet.fetch_sheet_metadata()

        print(f"\n📄 Spreadsheet metadata:")
        for s in sheet_metadata['sheets']:
            if s['properties']['title'] == BIGQUERY_SHEET_NAME:
                print(json.dumps(s, indent=2))

                # Check for data source
                if 'dataSourceSheetProperties' in s['properties']:
                    print("\n✅ Found BigQuery data source!")
                    print(json.dumps(s['properties']['dataSourceSheetProperties'], indent=2))

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

    print("\n" + "="*60)
    print("MANUAL INSTRUCTIONS:")
    print("="*60)
    print("\n📌 To find the BigQuery table info:")
    print("1. Open the Google Sheet in your browser")
    print("2. Click on Data > Data connectors > View all connectors")
    print("3. OR click 'Connection settings' in the BigQuery toolbar")
    print("4. You should see:")
    print("   - Project ID")
    print("   - Dataset ID")
    print("   - Table ID")
    print("\n💡 Once you have this info, we can query BigQuery directly!")

if __name__ == "__main__":
    main()
