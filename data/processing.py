"""Data processing and enrichment functions."""

import pandas as pd


def apply_importer_mapping(df, mapping):
    """Apply importer ID to name mapping. Uses BigQuery importer_name as primary,
    falls back to CSV mapping for any NULLs."""
    if 'importer_name' in df.columns:
        df = df.copy()
        if mapping and 'importer_ID' in df.columns:
            df['importer_id_str'] = df['importer_ID'].astype(str).str.strip()
            mask = df['importer_name'].isna() | (df['importer_name'].astype(str).str.strip() == '')
            df.loc[mask, 'importer_name'] = df.loc[mask, 'importer_id_str'].map(mapping)
        df['importer_name'] = df['importer_name'].fillna('Unknown')
        return df

    if 'importer_ID' not in df.columns:
        df['importer_name'] = 'Unknown'
        return df

    df = df.copy()
    df['importer_id_str'] = df['importer_ID'].astype(str).str.strip()

    if mapping:
        df['importer_name'] = df['importer_id_str'].map(mapping)
        df['importer_name'] = df['importer_name'].fillna('ID: ' + df['importer_id_str'])
    else:
        df['importer_name'] = 'ID: ' + df['importer_id_str']

    return df


def parse_upgrades(df):
    """Parse upgrades column and create individual upgrade columns."""
    if 'upgrades' not in df.columns:
        return df

    df = df.copy()

    all_upgrades = set()
    for upgrades_str in df['upgrades'].dropna():
        if pd.notna(upgrades_str) and upgrades_str.strip():
            upgrades_list = [u.strip() for u in str(upgrades_str).split('|')]
            all_upgrades.update(upgrades_list)

    df['upgrades_list'] = df['upgrades'].apply(lambda x:
        [u.strip() for u in str(x).split('|')] if pd.notna(x) and str(x).strip() else []
    )

    return df


def prepare_enriched_data(df):
    """Prepare vacancy summary data by renaming columns for dashboard compatibility."""
    df = df.copy()
    column_mapping = {
        'entity_id_str': 'entity_id',
    }
    existing_renames = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=existing_renames)
    return df


def add_occupation_column(df):
    """Extract occupation field from occupational_fields column."""
    if 'occupational_fields' in df.columns:
        df['occupation'] = df['occupational_fields'].apply(lambda x:
            str(x).split('|')[0].strip().title() if pd.notna(x) and str(x).strip() else 'Unknown'
        )
    else:
        df['occupation'] = 'Unknown'
    return df


def parse_dates_in_jobiqo(df):
    """Parse date columns from vacancy summary data."""
    if 'first_event_date' in df.columns:
        df['first_event_date'] = pd.to_datetime(df['first_event_date'], errors='coerce', utc=True).dt.tz_localize(None)
    if 'last_event_date' in df.columns:
        df['last_event_date'] = pd.to_datetime(df['last_event_date'], errors='coerce', utc=True).dt.tz_localize(None)
    if 'start_date' in df.columns:
        df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce', utc=True).dt.tz_localize(None)
    if 'end_date' in df.columns:
        df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce', utc=True).dt.tz_localize(None)
    return df
