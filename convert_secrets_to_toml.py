#!/usr/bin/env python3
"""
Convert service_account.json to Streamlit secrets TOML format.
Run this script to generate the secrets content for Streamlit Cloud.
"""
import json

# Read service account JSON
with open('service_account.json', 'r') as f:
    creds = json.load(f)

# Convert to TOML format
print("[gcp_service_account]")
for key, value in creds.items():
    if isinstance(value, str):
        # Escape quotes and newlines in strings
        value_escaped = value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        print(f'{key} = "{value_escaped}"')
    else:
        print(f'{key} = "{value}"')

print("\n" + "="*80)
print("Copy the output above and paste it into Streamlit Cloud secrets!")
print("="*80)
