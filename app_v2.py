import streamlit as st
import pandas as pd
import numpy as np
from google.oauth2.service_account import Credentials
from google.cloud import bigquery
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="Job Performance Dashboard (v2 Dev)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# BigQuery configuration
BQ_PROJECT_ID = "site-monitoring-421401"
BQ_DATASET_ID = "job_data_export"
BQ_TABLE_ID = "dashboard_vacancy_summary"
BQ_DAILY_TOTALS_TABLE_ID = "dashboard_daily_totals"

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/bigquery',
]

# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

@st.cache_resource(ttl=None)
def get_bigquery_client():
    """Initialize and cache the BigQuery client."""
    import os

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    service_account_path = os.path.join(script_dir, 'service_account.json')

    try:
        # Try Streamlit secrets first (for cloud deployment)
        use_secrets = False
        try:
            if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
                use_secrets = True
        except Exception as e:
            use_secrets = False

        if use_secrets:
            creds = Credentials.from_service_account_info(
                st.secrets['gcp_service_account'],
                scopes=SCOPES
            )
        else:
            # Fall back to local file (for local development)
            pass

            # Check if file exists before trying to use it
            if not os.path.exists(service_account_path):
                st.error(f"❌ No authentication found!")
                st.error(f"Local file does not exist at: {service_account_path}")
                st.error("Please either:")
                st.error("1. Add secrets to Streamlit Cloud (Settings → Secrets), OR")
                st.error("2. Add service_account.json file to the app directory")
                st.stop()

            creds = Credentials.from_service_account_file(
                service_account_path,
                scopes=SCOPES
            )

        client = bigquery.Client(credentials=creds, project=BQ_PROJECT_ID)
        return client
    except FileNotFoundError as e:
        st.error(f"⚠️ Service account credentials not found at: {service_account_path}")
        st.error("Please add them to Streamlit secrets or place service_account.json in the app directory")
        st.code(f"Expected location: {service_account_path}")
        st.code(f"Error: {repr(e)}")
        st.stop()
    except Exception as e:
        st.error(f"❌ Unexpected error initializing BigQuery client: {type(e).__name__}")
        st.error(f"Error message: {str(e)}")
        st.code(f"Attempted to load from: {service_account_path}")
        st.code(f"Full error: {repr(e)}")
        st.stop()

@st.cache_data(ttl=14400)  # Cache for 4 hours (data refreshes daily)
def load_all_data(days_back=30, sample_size=None):
    """Load vacancy summary and daily totals in a single BigQuery call.

    Returns both DataFrames from one round trip to minimise latency.

    Args:
        days_back: Number of days to look back
        sample_size: If set, limit vacancy rows (for testing)
    """
    try:
        client = get_bigquery_client()

        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        limit_clause = f"LIMIT {sample_size}" if sample_size else ""

        # Run both queries in one script to minimise round trips
        vacancy_query = f"""
        SELECT
            entity_id_str,
            first_event_date,
            last_event_date,
            clicks,
            applies,
            title,
            organization_name,
            uk_regions,
            primary_uk_region,
            occupational_fields,
            importer_ID,
            importer_name,
            workflow_state,
            upgrades,
            start_date,
            end_date,
            category,
            contract_type,
            employment_type
        FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.{BQ_TABLE_ID}`
        WHERE last_event_date >= '{cutoff_date}'
        {limit_clause}
        """

        daily_query = f"""
        SELECT
            event_date,
            clicks,
            applies,
            active_vacancies
        FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.{BQ_DAILY_TOTALS_TABLE_ID}`
        WHERE event_date >= '{cutoff_date}'
        ORDER BY event_date
        """

        # Submit both queries concurrently
        vacancy_job = client.query(vacancy_query)
        daily_job = client.query(daily_query)

        # Wait for both to complete
        vacancy_job.result()
        daily_job.result()

        vacancy_df = vacancy_job.to_dataframe(create_bqstorage_client=False)
        daily_df = daily_job.to_dataframe(create_bqstorage_client=False)

        return vacancy_df, daily_df
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        st.markdown("""
        **Troubleshooting:**
        - Check BigQuery tables exist: `dashboard_vacancy_summary` and `dashboard_daily_totals`
        - Verify service account has `bigquery.jobs.create` permission
        - Check the tables have data for the requested date range
        """)
        st.stop()

@st.cache_data(ttl=300)
def load_importer_mapping():
    """Load importer mapping from CSV file."""
    try:
        mapping_df = pd.read_csv('importer_mapping.csv', encoding='utf-8-sig')
        if 'importer_id' in mapping_df.columns and 'importer_name' in mapping_df.columns:
            mapping_df = mapping_df[mapping_df['importer_id'].notna()]
            mapping_df = mapping_df[mapping_df['importer_id'].astype(str).str.strip() != '']
            # Create mapping with string keys (stripped)
            importer_mapping = dict(zip(
                mapping_df['importer_id'].astype(str).str.strip(),
                mapping_df['importer_name'].str.strip()
            ))
            return importer_mapping
        return {}
    except Exception as e:
        st.error(f"Error loading importer mapping: {e}")
        return {}

@st.cache_data(ttl=14400)
def load_launch_timing_data(days_back=365):
    """Load per-vacancy per-day event counts from the enriched table for launch timing analysis."""
    try:
        client = get_bigquery_client()
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        query = f"""
        WITH vacancy_start AS (
            SELECT
                entity_id_str,
                MIN(event_date_parsed) as first_event_date,
                ANY_VALUE(occupational_fields) as occupational_fields
            FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.job_performance_enriched`
            WHERE event_date_parsed >= '{cutoff_date}'
            GROUP BY entity_id_str
        ),
        daily_events AS (
            SELECT
                e.entity_id_str,
                e.event_date_parsed,
                COUNTIF(e.event_name = 'job_visit') as clicks,
                COUNTIF(e.event_name = 'job_apply_start') as applies
            FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.job_performance_enriched` e
            WHERE e.event_date_parsed >= '{cutoff_date}'
            GROUP BY e.entity_id_str, e.event_date_parsed
        )
        SELECT
            d.entity_id_str,
            d.event_date_parsed,
            d.clicks,
            d.applies,
            DATE_DIFF(d.event_date_parsed, v.first_event_date, DAY) as day_offset,
            EXTRACT(DAYOFWEEK FROM v.first_event_date) as launch_dow,
            EXTRACT(DAYOFWEEK FROM d.event_date_parsed) as event_dow,
            v.occupational_fields
        FROM daily_events d
        JOIN vacancy_start v ON d.entity_id_str = v.entity_id_str
        WHERE DATE_DIFF(d.event_date_parsed, v.first_event_date, DAY) BETWEEN 0 AND 30
        ORDER BY d.entity_id_str, d.event_date_parsed
        """

        job = client.query(query)
        job.result()
        return job.to_dataframe(create_bqstorage_client=False)
    except Exception as e:
        st.error(f"Error loading launch timing data: {str(e)}")
        return pd.DataFrame()


# ============================================================================
# DATA PROCESSING FUNCTIONS
# ============================================================================

def apply_importer_mapping(df, mapping):
    """Apply importer ID to name mapping. Uses BigQuery importer_name as primary,
    falls back to CSV mapping for any NULLs."""
    if 'importer_name' in df.columns:
        # importer_name already comes from BigQuery; fill gaps with CSV mapping
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

    # Fallback: no importer_name column — use CSV mapping
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

    # Create a copy to avoid modifying original
    df = df.copy()

    # Extract all unique upgrade types
    all_upgrades = set()
    for upgrades_str in df['upgrades'].dropna():
        if pd.notna(upgrades_str) and upgrades_str.strip():
            upgrades_list = [u.strip() for u in str(upgrades_str).split('|')]
            all_upgrades.update(upgrades_list)

    # Store parsed upgrades as a list
    df['upgrades_list'] = df['upgrades'].apply(lambda x:
        [u.strip() for u in str(x).split('|')] if pd.notna(x) and str(x).strip() else []
    )

    return df

def prepare_enriched_data(df):
    """Prepare vacancy summary data by renaming columns for dashboard compatibility."""
    df = df.copy()

    # The vacancy summary table already uses clean names for most columns.
    # Only entity_id_str needs renaming.
    column_mapping = {
        'entity_id_str': 'entity_id',
    }

    # Only rename columns that exist
    existing_renames = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=existing_renames)

    return df

def add_occupation_column(df):
    """Extract occupation field from occupational_fields column."""
    if 'occupational_fields' in df.columns:
        df['occupation'] = df['occupational_fields'].apply(lambda x:
            str(x).split('|')[0].strip() if pd.notna(x) and str(x).strip() else 'Unknown'
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

# ============================================================================
# FILTER FUNCTIONS
# ============================================================================

def create_filter_panel(df, key_prefix, default_months=6):
    """Create a reusable filter panel for all tabs with compact 3-column layout."""
    st.subheader("🔍 Filters")

    filters = {}

    # Row 1: Date Range, Importer, Company
    col1, col2, col3 = st.columns(3)

    with col1:
        # Date Range Filter (uses last_event_date for range boundaries)
        date_col = 'last_event_date' if 'last_event_date' in df.columns else None
        if date_col and pd.api.types.is_datetime64_any_dtype(df[date_col]):
            # Use first_event_date min and last_event_date max for the full range
            min_date = df['first_event_date'].dropna().min() if 'first_event_date' in df.columns else df[date_col].dropna().min()
            max_date = df[date_col].dropna().max()
            if pd.isna(min_date) or pd.isna(max_date):
                min_date = datetime.now().date()
                max_date = datetime.now().date()
            else:
                min_date = min_date.date() if hasattr(min_date, 'date') else min_date
                max_date = max_date.date() if hasattr(max_date, 'date') else max_date
            default_start = min_date

            filters['date_range'] = st.date_input(
                "Date Range",
                [default_start, max_date],
                min_value=min_date,
                max_value=max_date,
                key=f'{key_prefix}_date'
            )

    with col2:
        # Importer Filter
        if 'importer_name' in df.columns:
            importers = sorted(df['importer_name'].dropna().unique())
            filters['importer'] = st.multiselect(
                "Importer",
                importers,
                key=f'{key_prefix}_importer'
            )

    with col3:
        # Company Filter
        if 'organization_name' in df.columns:
            companies = sorted(df['organization_name'].dropna().unique())
            filters['company'] = st.multiselect(
                "Company",
                companies,
                key=f'{key_prefix}_company'
            )

    # Row 2: Region, Occupation, Upgrades
    col1, col2, col3 = st.columns(3)

    with col1:
        # Region Filter — extract all unique regions from pipe-separated uk_regions
        if 'uk_regions' in df.columns:
            all_regions = set()
            for regions_str in df['uk_regions'].dropna():
                for r in str(regions_str).split(' | '):
                    r = r.strip()
                    if r:
                        all_regions.add(r)
            regions = sorted(all_regions)
            filters['region'] = st.multiselect(
                "Region",
                regions,
                key=f'{key_prefix}_region'
            )

    with col2:
        # Occupation Filter
        if 'occupation' in df.columns:
            occupations = sorted(df['occupation'].dropna().unique())
            filters['occupation'] = st.multiselect(
                "Occupation",
                occupations,
                key=f'{key_prefix}_occupation'
            )

    with col3:
        # Upgrades Filter
        if 'upgrades_list' in df.columns:
            all_upgrades = set()
            for upgrades in df['upgrades_list']:
                all_upgrades.update(upgrades)
            upgrade_options = sorted(list(all_upgrades))
            filters['upgrades'] = st.multiselect(
                "Upgrades",
                upgrade_options,
                key=f'{key_prefix}_upgrades'
            )

    # Row 3: Job Title Search and Apply Button
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        # Job Title Search
        filters['job_title'] = st.text_input(
            "Job Title (search)",
            key=f'{key_prefix}_title',
            placeholder="e.g., Housing Director"
        )

    with col2:
        # Apply button
        st.write("")  # Spacer to align button
        apply_clicked = st.button(
            "🔄 Apply Filters",
            key=f'{key_prefix}_apply',
            type="primary",
            width='stretch'
        )

    st.markdown("---")

    return filters, apply_clicked

def apply_filters_to_data(df, filters):
    """Apply filter selections to dataframe."""
    # Handle None filters (no filters applied yet)
    if filters is None:
        return df.copy()

    filtered = df.copy()

    # Date Range Filter (show vacancies whose event date range overlaps the selected range)
    if filters.get('date_range') and len(filters['date_range']) == 2:
        start_date, end_date = filters['date_range']

        # A vacancy is in range if first_event_date <= end_date AND last_event_date >= start_date
        if 'first_event_date' in filtered.columns and 'last_event_date' in filtered.columns:
            if pd.api.types.is_datetime64_any_dtype(filtered['last_event_date']):
                filtered = filtered[
                    (filtered['first_event_date'].dt.date <= end_date) &
                    (filtered['last_event_date'].dt.date >= start_date)
                ]

    # Importer Filter
    if filters.get('importer') and 'importer_name' in filtered.columns:
        filtered = filtered[filtered['importer_name'].isin(filters['importer'])]

    # Company Filter
    if filters.get('company') and 'organization_name' in filtered.columns:
        filtered = filtered[filtered['organization_name'].isin(filters['company'])]

    # Region Filter — match vacancies where ANY region in pipe-separated uk_regions matches
    if filters.get('region') and 'uk_regions' in filtered.columns:
        selected_regions = set(filters['region'])
        mask = filtered['uk_regions'].apply(
            lambda x: bool(selected_regions & set(r.strip() for r in str(x).split(' | ')))
            if pd.notna(x) else False
        )
        filtered = filtered[mask]

    # Occupation Filter
    if filters.get('occupation') and 'occupation' in filtered.columns:
        filtered = filtered[filtered['occupation'].isin(filters['occupation'])]

    # Upgrades Filter (vacancy has ANY of the selected upgrades)
    if filters.get('upgrades') and 'upgrades_list' in filtered.columns:
        filtered = filtered[filtered['upgrades_list'].apply(
            lambda x: any(upgrade in x for upgrade in filters['upgrades'])
        )]

    # Job Title Search (case-insensitive partial match)
    if filters.get('job_title') and filters['job_title'].strip():
        if 'title' in filtered.columns:
            search_term = filters['job_title'].strip().lower()
            filtered = filtered[filtered['title'].str.lower().str.contains(search_term, na=False)]

    return filtered

# ============================================================================
# CALCULATION FUNCTIONS
# ============================================================================

def remove_outliers_iqr(data):
    """Remove outliers using IQR (Interquartile Range) method."""
    if len(data) < 4:  # Need at least 4 points for IQR
        return data

    q1 = np.percentile(data, 25)
    q3 = np.percentile(data, 75)
    iqr = q3 - q1

    lower_bound = q1 - (1.5 * iqr)
    upper_bound = q3 + (1.5 * iqr)

    return [x for x in data if lower_bound <= x <= upper_bound]


def calculate_metrics(df):
    """Calculate key metrics from pre-aggregated vacancy summary data.

    Each row in df is a vacancy with pre-computed 'clicks' and 'applies' columns.
    """
    entity_col = 'entity_id' if 'entity_id' in df.columns else df.columns[0]

    metrics = {}
    metrics['num_vacancies'] = len(df)  # Each row IS a vacancy now

    if 'clicks' in df.columns:
        metrics['total_clicks'] = int(df['clicks'].sum())
        metrics['total_applies'] = int(df['applies'].sum())
    else:
        metrics['total_clicks'] = 0
        metrics['total_applies'] = 0

    metrics['apply_click_ratio'] = (metrics['total_applies'] / metrics['total_clicks'] * 100) if metrics['total_clicks'] > 0 else 0

    # Calculate per-vacancy metrics directly from columns
    if metrics['num_vacancies'] > 0 and 'clicks' in df.columns:
        metrics['mean_clicks_per_vacancy'] = metrics['total_clicks'] / metrics['num_vacancies']
        metrics['mean_applies_per_vacancy'] = metrics['total_applies'] / metrics['num_vacancies']
        metrics['median_clicks_per_vacancy'] = float(np.median(df['clicks'].values))
        metrics['median_applies_per_vacancy'] = float(np.median(df['applies'].values))
        metrics['clicks_per_vacancy'] = metrics['mean_clicks_per_vacancy']
        metrics['applies_per_vacancy'] = metrics['mean_applies_per_vacancy']
    else:
        metrics['median_clicks_per_vacancy'] = 0
        metrics['median_applies_per_vacancy'] = 0
        metrics['mean_clicks_per_vacancy'] = 0
        metrics['mean_applies_per_vacancy'] = 0
        metrics['clicks_per_vacancy'] = 0
        metrics['applies_per_vacancy'] = 0

    return metrics

def calculate_quartile_metrics(df):
    """Calculate metrics by performance quartiles (top 25%, middle 50%, bottom 25%).

    Uses pre-aggregated clicks and applies columns directly.
    """
    if 'clicks' not in df.columns:
        return None

    if len(df) < 4:
        return None  # Need at least 4 vacancies for quartiles

    vacancy_clicks = df['clicks']
    vacancy_applies = df['applies']

    # Calculate quartile thresholds based on clicks
    q1_threshold = vacancy_clicks.quantile(0.25)
    q3_threshold = vacancy_clicks.quantile(0.75)

    # Categorize vacancies using vectorized operations
    top_25_mask = vacancy_clicks >= q3_threshold
    middle_50_mask = (vacancy_clicks >= q1_threshold) & (vacancy_clicks < q3_threshold)
    bottom_25_mask = vacancy_clicks < q1_threshold

    # Calculate metrics for each quartile
    quartiles = {}

    for name, mask in [('top_25', top_25_mask), ('middle_50', middle_50_mask), ('bottom_25', bottom_25_mask)]:
        total_clicks = int(vacancy_clicks[mask].sum())
        total_applies = int(vacancy_applies[mask].sum())
        num_vacancies = int(mask.sum())

        quartiles[name] = {
            'num_vacancies': num_vacancies,
            'total_clicks': total_clicks,
            'total_applies': total_applies,
            'apply_click_ratio': (total_applies / total_clicks * 100) if total_clicks > 0 else 0,
            'clicks_per_vacancy': total_clicks / num_vacancies if num_vacancies > 0 else 0,
            'applies_per_vacancy': total_applies / num_vacancies if num_vacancies > 0 else 0
        }

    return quartiles


def get_performance_color(value, avg_value, metric_type='ratio'):
    """Get color indicator based on performance vs average."""
    if value is None or avg_value is None or avg_value == 0:
        return "⚪"

    diff_pct = ((value - avg_value) / avg_value) * 100

    if diff_pct > 10:
        return "🟢"  # Above average
    elif diff_pct < -10:
        return "🔴"  # Below average
    else:
        return "🟡"  # Near average

# ============================================================================
# TAB 1: OVERVIEW DASHBOARD
# ============================================================================

def create_overview_tab(df, daily_totals=None):
    """Create the Overview Dashboard tab.

    Args:
        df: The vacancy summary dataframe (one row per vacancy)
        daily_totals: Pre-aggregated daily totals dataframe (one row per day)
    """
    st.header("📊 Overview Dashboard")

    # Filters in sidebar/expander
    with st.expander("🔍 Filters", expanded=True):
        filters, apply_clicked = create_filter_panel(df, 'overview')

    # Apply filters
    if apply_clicked or 'overview_filters' in st.session_state:
        if apply_clicked:
            st.session_state.overview_filters = filters
        filtered_df = apply_filters_to_data(df, st.session_state.overview_filters)
    else:
        filtered_df = df.copy()

    # Calculate metrics
    metrics = calculate_metrics(filtered_df)
    quartiles = calculate_quartile_metrics(filtered_df)

    # Debug: Show what we got
    with st.expander("🔧 Debug Info", expanded=False):
        st.write("**Available columns:**")
        st.write(filtered_df.columns.tolist())
        st.write("**Metrics calculated:**")
        st.json(metrics)
        st.write("**Sample data (first 5 rows):**")
        st.dataframe(filtered_df.head())

    # KPI Cards with Quartile Breakdown
    st.subheader("Key Performance Indicators")

    if quartiles:
        # Row 1: Overall Totals
        st.markdown("### 📊 Overall Performance")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Vacancies", f"{metrics['num_vacancies']:,}")

        with col2:
            st.metric("Total Clicks", f"{metrics['total_clicks']:,}")

        with col3:
            st.metric("Total Applies", f"{metrics['total_applies']:,}")

        with col4:
            st.metric("Apply/Click Ratio", f"{metrics['apply_click_ratio']:.2f}%")

        st.markdown("---")

        # Row 2: Top 25% (Best Performers)
        st.markdown("### 🟢 Top 25% Performers")
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric("Vacancies", f"{quartiles['top_25']['num_vacancies']:,}")

        with col2:
            st.metric("Total Clicks", f"{quartiles['top_25']['total_clicks']:,}")

        with col3:
            st.metric("Total Applies", f"{quartiles['top_25']['total_applies']:,}")

        with col4:
            st.metric("Apply/Click %", f"{quartiles['top_25']['apply_click_ratio']:.2f}%")

        with col5:
            st.metric("Avg Clicks/Vac", f"{quartiles['top_25']['clicks_per_vacancy']:.1f}")

        with col6:
            st.metric("Avg Applies/Vac", f"{quartiles['top_25']['applies_per_vacancy']:.2f}")

        st.markdown("---")

        # Row 3: Middle 50% (Average Performers)
        st.markdown("### 🟡 Middle 50% Performers")
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric("Vacancies", f"{quartiles['middle_50']['num_vacancies']:,}")

        with col2:
            st.metric("Total Clicks", f"{quartiles['middle_50']['total_clicks']:,}")

        with col3:
            st.metric("Total Applies", f"{quartiles['middle_50']['total_applies']:,}")

        with col4:
            st.metric("Apply/Click %", f"{quartiles['middle_50']['apply_click_ratio']:.2f}%")

        with col5:
            st.metric("Avg Clicks/Vac", f"{quartiles['middle_50']['clicks_per_vacancy']:.1f}")

        with col6:
            st.metric("Avg Applies/Vac", f"{quartiles['middle_50']['applies_per_vacancy']:.2f}")

        st.markdown("---")

        # Row 4: Bottom 25% (Needs Improvement)
        st.markdown("### 🔴 Bottom 25% Performers")
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric("Vacancies", f"{quartiles['bottom_25']['num_vacancies']:,}")

        with col2:
            st.metric("Total Clicks", f"{quartiles['bottom_25']['total_clicks']:,}")

        with col3:
            st.metric("Total Applies", f"{quartiles['bottom_25']['total_applies']:,}")

        with col4:
            st.metric("Apply/Click %", f"{quartiles['bottom_25']['apply_click_ratio']:.2f}%")

        with col5:
            st.metric("Avg Clicks/Vac", f"{quartiles['bottom_25']['clicks_per_vacancy']:.1f}")

        with col6:
            st.metric("Avg Applies/Vac", f"{quartiles['bottom_25']['applies_per_vacancy']:.2f}")

    else:
        # Fallback to simple view if not enough data
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Vacancies", f"{metrics['num_vacancies']:,}")

        with col2:
            st.metric("Total Clicks", f"{metrics['total_clicks']:,}")

        with col3:
            st.metric("Total Applies", f"{metrics['total_applies']:,}")

        with col4:
            st.metric("Apply/Click Ratio", f"{metrics['apply_click_ratio']:.2f}%")

    st.markdown("---")

    # Time Series (from pre-aggregated daily totals)
    if daily_totals is not None and len(daily_totals) > 0:
        st.subheader("Trends Over Time")

        # Check if any filters are active (beyond default)
        has_active_filters = False
        if 'overview_filters' in st.session_state and st.session_state.overview_filters:
            f = st.session_state.overview_filters
            if any([f.get('importer'), f.get('company'), f.get('region'),
                    f.get('occupation'), f.get('upgrades'), f.get('job_title')]):
                has_active_filters = True

        if has_active_filters:
            st.caption("Note: Trend data shows global site performance (not affected by filters above).")

        daily_data = daily_totals.copy()
        daily_data = daily_data.sort_values('event_date')

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily_data['event_date'], y=daily_data['clicks'],
                                name='Clicks', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=daily_data['event_date'], y=daily_data['applies'],
                                name='Applies', line=dict(color='green')))
        fig.update_layout(height=400, hovermode='x unified')
        st.plotly_chart(fig, width='stretch')

    st.markdown("---")

    # Performance by Dimension
    col1, col2 = st.columns(2)

    with col1:
        if 'importer_name' in filtered_df.columns:
            st.subheader("Performance by Importer")
            importer_stats = []
            for importer in filtered_df['importer_name'].unique():
                imp_df = filtered_df[filtered_df['importer_name'] == importer]
                imp_metrics = calculate_metrics(imp_df)
                importer_stats.append({
                    'Importer': importer,
                    'Vacancies': imp_metrics['num_vacancies'],
                    'Median Clicks': round(imp_metrics['median_clicks_per_vacancy'], 1),
                    'Mean Clicks': round(imp_metrics['mean_clicks_per_vacancy'], 1),
                    'Median Applies': round(imp_metrics['median_applies_per_vacancy'], 2),
                    'Mean Applies': round(imp_metrics['mean_applies_per_vacancy'], 2),
                    'Apply/Click %': round(imp_metrics['apply_click_ratio'], 2)
                })

            if importer_stats:
                importer_df = pd.DataFrame(importer_stats).sort_values('Mean Clicks', ascending=False)

                # Create grouped bar chart
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name='Median Clicks/Vacancy',
                    x=importer_df['Importer'],
                    y=importer_df['Median Clicks'],
                    text=importer_df['Median Clicks'],
                    textposition='auto',
                ))
                fig.add_trace(go.Bar(
                    name='Mean Clicks/Vacancy',
                    x=importer_df['Importer'],
                    y=importer_df['Mean Clicks'],
                    text=importer_df['Mean Clicks'],
                    textposition='auto',
                ))

                fig.update_layout(
                    barmode='group',
                    height=400,
                    xaxis_title='Importer',
                    yaxis_title='Clicks per Vacancy',
                    hovermode='x unified'
                )
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No importer data available for the selected filters.")

    with col2:
        if 'uk_regions' in filtered_df.columns:
            st.subheader("Performance by Region")
            # Explode pipe-separated regions so each region is counted independently
            # A vacancy in "London | West Midlands" contributes to both region stats
            region_stats = []
            all_regions = set()
            for regions_str in filtered_df['uk_regions'].dropna():
                for r in str(regions_str).split(' | '):
                    r = r.strip()
                    if r:
                        all_regions.add(r)
            for region in all_regions:
                reg_mask = filtered_df['uk_regions'].apply(
                    lambda x: region in [r.strip() for r in str(x).split(' | ')] if pd.notna(x) else False
                )
                reg_df = filtered_df[reg_mask]
                reg_metrics = calculate_metrics(reg_df)
                region_stats.append({
                    'Region': region,
                    'Vacancies': reg_metrics['num_vacancies'],
                    'Median Clicks': round(reg_metrics['median_clicks_per_vacancy'], 1),
                    'Mean Clicks': round(reg_metrics['mean_clicks_per_vacancy'], 1),
                    'Median Applies': round(reg_metrics['median_applies_per_vacancy'], 2),
                    'Mean Applies': round(reg_metrics['mean_applies_per_vacancy'], 2),
                    'Apply/Click %': round(reg_metrics['apply_click_ratio'], 2)
                })

            if region_stats:
                region_df = pd.DataFrame(region_stats).sort_values('Mean Clicks', ascending=False)

                # Create grouped bar chart
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name='Median Clicks/Vacancy',
                    x=region_df['Region'],
                    y=region_df['Median Clicks'],
                    text=region_df['Median Clicks'],
                    textposition='auto',
                ))
                fig.add_trace(go.Bar(
                    name='Mean Clicks/Vacancy',
                    x=region_df['Region'],
                    y=region_df['Mean Clicks'],
                    text=region_df['Mean Clicks'],
                    textposition='auto',
                ))

                fig.update_layout(
                    barmode='group',
                    height=400,
                    xaxis_title='Region',
                    yaxis_title='Clicks per Vacancy',
                    hovermode='x unified'
                )
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No region data available for the selected filters.")

    st.markdown("---")

    # Conversion Funnel
    st.subheader("Conversion Funnel")
    funnel_data = pd.DataFrame({
        'Stage': ['Vacancies', 'Clicks', 'Applies'],
        'Count': [metrics['num_vacancies'], metrics['total_clicks'], metrics['total_applies']]
    })
    fig = px.funnel(funnel_data, x='Count', y='Stage')
    fig.update_layout(height=400)
    st.plotly_chart(fig, width='stretch')

# ============================================================================
# TAB 2: DEEP DIVE
# ============================================================================

def create_deep_dive_tab(df):
    """Create the Deep Dive tab."""
    st.header("🔍 Deep Dive")

    # Filters
    with st.expander("🔍 Filters", expanded=True):
        filters, apply_clicked = create_filter_panel(df, 'deepdive')

    # Apply filters
    if apply_clicked or 'deepdive_filters' in st.session_state:
        if apply_clicked:
            st.session_state.deepdive_filters = filters
        filtered_df = apply_filters_to_data(df, st.session_state.deepdive_filters)
    else:
        filtered_df = df.copy()

    # Benchmark Comparison Table
    st.subheader("📊 Benchmark Comparison Table")

    dimension = st.selectbox(
        "Group by:",
        ['Importer', 'Region', 'Occupation', 'Company'],
        key='deepdive_dimension'
    )

    column_map = {
        'Importer': 'importer_name',
        'Region': 'uk_regions',
        'Occupation': 'occupation',
        'Company': 'organization_name'
    }

    col_name = column_map[dimension]
    if col_name in filtered_df.columns:
        benchmark_data = []

        if dimension == 'Region':
            # Regions are pipe-separated — explode for per-region stats
            all_values = set()
            for regions_str in filtered_df[col_name].dropna():
                for r in str(regions_str).split(' | '):
                    r = r.strip()
                    if r:
                        all_values.add(r)
            for value in all_values:
                mask = filtered_df[col_name].apply(
                    lambda x: value in [r.strip() for r in str(x).split(' | ')] if pd.notna(x) else False
                )
                subset = filtered_df[mask]
                metrics = calculate_metrics(subset)
                benchmark_data.append({
                    dimension: value,
                    'Vacancies': metrics['num_vacancies'],
                    'Total Clicks': metrics['total_clicks'],
                    'Total Applies': metrics['total_applies'],
                    'Apply/Click %': round(metrics['apply_click_ratio'], 2),
                    'Median Clicks/Vac': round(metrics['median_clicks_per_vacancy'], 1),
                    'Mean Clicks/Vac': round(metrics['mean_clicks_per_vacancy'], 1),
                    'Median Applies/Vac': round(metrics['median_applies_per_vacancy'], 2),
                    'Mean Applies/Vac': round(metrics['mean_applies_per_vacancy'], 2)
                })
        else:
            for value in filtered_df[col_name].unique():
                subset = filtered_df[filtered_df[col_name] == value]
                metrics = calculate_metrics(subset)
                benchmark_data.append({
                    dimension: value,
                    'Vacancies': metrics['num_vacancies'],
                    'Total Clicks': metrics['total_clicks'],
                    'Total Applies': metrics['total_applies'],
                    'Apply/Click %': round(metrics['apply_click_ratio'], 2),
                    'Median Clicks/Vac': round(metrics['median_clicks_per_vacancy'], 1),
                    'Mean Clicks/Vac': round(metrics['mean_clicks_per_vacancy'], 1),
                    'Median Applies/Vac': round(metrics['median_applies_per_vacancy'], 2),
                    'Mean Applies/Vac': round(metrics['mean_applies_per_vacancy'], 2)
                })

        if benchmark_data:
            benchmark_df = pd.DataFrame(benchmark_data).sort_values('Mean Clicks/Vac', ascending=False)
            st.dataframe(benchmark_df, width='stretch')
        else:
            st.info("No benchmark data available for the selected filters.")
            benchmark_df = pd.DataFrame()

        # Export
        csv = benchmark_df.to_csv(index=False).encode('utf-8') if not benchmark_df.empty else b''
        st.download_button(
            "📥 Download Benchmark Data",
            csv,
            f"benchmark_{dimension.lower()}_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )

    st.markdown("---")

    # Heatmap
    st.subheader("🗺️ Performance Heatmap")

    if 'uk_regions' in filtered_df.columns and 'importer_name' in filtered_df.columns:
        heatmap_data = []
        # Explode regions for heatmap
        all_regions = set()
        for regions_str in filtered_df['uk_regions'].dropna():
            for r in str(regions_str).split(' | '):
                r = r.strip()
                if r:
                    all_regions.add(r)
        for region in all_regions:
            reg_mask = filtered_df['uk_regions'].apply(
                lambda x: region in [r.strip() for r in str(x).split(' | ')] if pd.notna(x) else False
            )
            for importer in filtered_df['importer_name'].unique():
                subset = filtered_df[
                    reg_mask &
                    (filtered_df['importer_name'] == importer)
                ]
                if len(subset) > 0:
                    metrics = calculate_metrics(subset)
                    heatmap_data.append({
                        'Region': region,
                        'Importer': importer,
                        'Clicks/Vacancy': metrics['clicks_per_vacancy'],
                        'Applies/Vacancy': metrics['applies_per_vacancy'],
                        'Apply/Click %': metrics['apply_click_ratio']
                    })

        if heatmap_data:
            heatmap_df = pd.DataFrame(heatmap_data)

            # Allow user to select metric for heatmap
            heatmap_metric = st.selectbox(
                "Select metric for heatmap:",
                ['Clicks/Vacancy', 'Applies/Vacancy', 'Apply/Click %'],
                key='heatmap_metric'
            )

            heatmap_pivot = heatmap_df.pivot(index='Region', columns='Importer', values=heatmap_metric)

            fig = px.imshow(
                heatmap_pivot,
                labels=dict(x="Importer", y="Region", color=heatmap_metric),
                aspect="auto",
                color_continuous_scale='RdYlGn'
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, width='stretch')

# ============================================================================
# TAB 3: VACANCY PERFORMANCE
# ============================================================================

def create_vacancy_performance_tab(df, full_df=None):
    """Create the Vacancy Performance tab.

    Args:
        df: The main dataframe (used for filtering)
        full_df: The full unfiltered dataframe (used for benchmark calculations)
    """
    st.header("📋 Vacancy Performance")

    # Use full_df if provided, otherwise use df
    if full_df is None:
        full_df = df

    # Filters
    with st.expander("🔍 Filters", expanded=True):
        filters, apply_clicked = create_filter_panel(df, 'vacancy')

    # Apply filters
    if apply_clicked or 'vacancy_filters' in st.session_state:
        if apply_clicked:
            st.session_state.vacancy_filters = filters
        filtered_df = apply_filters_to_data(df, st.session_state.vacancy_filters)
    else:
        filtered_df = df.copy()

    # Each row in filtered_df is already a vacancy with clicks/applies columns
    job_col = 'entity_id' if 'entity_id' in filtered_df.columns else filtered_df.columns[0]

    vacancy_data = []
    for _, job in filtered_df.iterrows():
        job_id = job[job_col]
        clicks = int(job.get('clicks', 0))
        applies = int(job.get('applies', 0))
        ratio = (applies / clicks * 100) if clicks > 0 else 0

        # Get vacancy status from workflow_state
        status = job.get('workflow_state', 'Unknown')
        is_published = status == 'published'

        # Calculate days active with improved logic
        days_active = None
        start_date = job.get('start_date')
        end_date = job.get('end_date')

        if pd.notna(start_date):
            if pd.notna(end_date):
                days_active = (end_date - start_date).days
            elif is_published:
                today = pd.Timestamp(datetime.now())
                days_active = (today - start_date).days

        # Get occupation from occupational_fields
        occupation = job.get('occupational_fields', 'Unknown')
        if pd.notna(occupation) and str(occupation).strip():
            occupation = str(occupation).split('|')[0].strip()
        else:
            occupation = 'Unknown'

        # Get upgrades
        upgrades_str = ', '.join(job.get('upgrades_list', [])) if 'upgrades_list' in job.index else ''

        vacancy_data.append({
            'Title': job.get('title', job.get('organization_name', 'Unknown')),
            'Company': job.get('organization_name', 'Unknown'),
            'Job ID': job_id,
            'Status': status,
            'Start Date': start_date if pd.notna(start_date) else None,
            'End Date': end_date if pd.notna(end_date) else None,
            'Days Active': int(days_active) if days_active is not None and days_active > 0 else None,
            'Region': job.get('uk_regions', 'Unknown'),
            'Occupation': occupation,
            'Importer': job.get('importer_name', 'Unknown'),
            'Upgrades': upgrades_str if upgrades_str else 'None',
            'Clicks': clicks,
            'Applies': applies,
            'Ratio %': round(ratio, 2) if clicks > 0 else None,
            'Clicks/Day': round(clicks / days_active, 2) if days_active and days_active > 0 else None,
            'Applies/Day': round(applies / days_active, 2) if days_active and days_active > 0 else None
        })

    vacancy_df = pd.DataFrame(vacancy_data)

    # Check if we have any data
    if len(vacancy_df) == 0:
        st.warning("⚠️ No vacancy data found for the selected filters. Try adjusting your date range or filters.")
        return

    # Calculate occupation benchmarks from FULL dataset (static benchmarks)
    # With pre-aggregated data, each row already has clicks/applies
    full_job_col = 'entity_id' if 'entity_id' in full_df.columns else full_df.columns[0]

    # Build occupation stats directly from the full dataframe
    full_df_with_occ = full_df.copy()
    full_df_with_occ['_occupation'] = full_df_with_occ['occupational_fields'].apply(
        lambda x: str(x).split('|')[0].strip() if pd.notna(x) and str(x).strip() else 'Unknown'
    )

    occupation_stats = {}
    for occupation in full_df_with_occ['_occupation'].unique():
        occ_vacancies = full_df_with_occ[full_df_with_occ['_occupation'] == occupation]
        occupation_stats[occupation] = {
            'avg_clicks': occ_vacancies['clicks'].mean() if 'clicks' in occ_vacancies.columns else 0,
            'avg_applies': occ_vacancies['applies'].mean() if 'applies' in occ_vacancies.columns else 0
        }

    # Add occupation benchmarks to filtered vacancy data
    if 'Occupation' in vacancy_df.columns:
        vacancy_df['Avg Clicks (Occupation)'] = vacancy_df['Occupation'].map(
            lambda x: round(occupation_stats.get(x, {}).get('avg_clicks', 0), 1)
        )
        vacancy_df['Avg Applies (Occupation)'] = vacancy_df['Occupation'].map(
            lambda x: round(occupation_stats.get(x, {}).get('avg_applies', 0), 1)
        )

    vacancy_df = vacancy_df.sort_values('Clicks', ascending=False)

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Vacancies", len(vacancy_df))
    with col2:
        st.metric("Total Clicks", f"{vacancy_df['Clicks'].sum():,}")
    with col3:
        st.metric("Total Applies", f"{vacancy_df['Applies'].sum():,}")
    with col4:
        avg_ratio = vacancy_df['Ratio %'].mean()
        st.metric("Avg Apply Rate", f"{avg_ratio:.2f}%")

    # Display table
    st.subheader(f"Vacancy Data ({len(vacancy_df)} vacancies)")
    st.dataframe(vacancy_df, width='stretch', height=600, hide_index=True)

    # Export
    csv = vacancy_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Download Vacancy Report",
        csv,
        f"vacancy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        "text/csv"
    )

# ============================================================================
# TAB 4: COMPARISON
# ============================================================================

def create_comparison_tab(df):
    """Create the Comparison tab."""
    st.header("⚖️ Comparison")
    st.info("💡 Select filters for each side, then click Apply Filters to compare")

    col_left, col_right = st.columns(2)

    # Left Side
    with col_left:
        st.subheader("📊 Side A")
        with st.expander("🔍 Filters", expanded=True):
            filters_left, apply_left = create_filter_panel(df, 'comp_left')

        if apply_left or 'comp_left_filters' in st.session_state:
            if apply_left:
                st.session_state.comp_left_filters = filters_left
            filtered_left = apply_filters_to_data(df, st.session_state.comp_left_filters)
        else:
            filtered_left = df.copy()

        metrics_left = calculate_metrics(filtered_left)

        st.markdown("### Totals")
        st.metric("Vacancies", f"{metrics_left['num_vacancies']:,}")
        st.metric("Clicks", f"{metrics_left['total_clicks']:,}")
        st.metric("Applies", f"{metrics_left['total_applies']:,}")
        st.metric("Apply/Click %", f"{metrics_left['apply_click_ratio']:.2f}%")
        st.metric("Clicks/Vacancy", f"{metrics_left['clicks_per_vacancy']:.1f}")
        st.metric("Applies/Vacancy", f"{metrics_left['applies_per_vacancy']:.2f}")

    # Right Side
    with col_right:
        st.subheader("📊 Side B")
        with st.expander("🔍 Filters", expanded=True):
            filters_right, apply_right = create_filter_panel(df, 'comp_right')

        if apply_right or 'comp_right_filters' in st.session_state:
            if apply_right:
                st.session_state.comp_right_filters = filters_right
            filtered_right = apply_filters_to_data(df, st.session_state.comp_right_filters)
        else:
            filtered_right = df.copy()

        metrics_right = calculate_metrics(filtered_right)

        st.markdown("### Totals")
        st.metric("Vacancies", f"{metrics_right['num_vacancies']:,}")
        st.metric("Clicks", f"{metrics_right['total_clicks']:,}")
        st.metric("Applies", f"{metrics_right['total_applies']:,}")
        st.metric("Apply/Click %", f"{metrics_right['apply_click_ratio']:.2f}%")
        st.metric("Clicks/Vacancy", f"{metrics_right['clicks_per_vacancy']:.1f}")
        st.metric("Applies/Vacancy", f"{metrics_right['applies_per_vacancy']:.2f}")

    # Comparison Summary
    st.markdown("---")
    st.subheader("📈 Comparison Summary")

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.markdown("**Vacancies**")
        diff = metrics_right['num_vacancies'] - metrics_left['num_vacancies']
        pct = ((metrics_right['num_vacancies'] / metrics_left['num_vacancies'] - 1) * 100) if metrics_left['num_vacancies'] > 0 else 0
        st.markdown(f"Side A: {metrics_left['num_vacancies']:,}")
        st.markdown(f"Side B: {metrics_right['num_vacancies']:,}")
        color = "🟢" if diff > 0 else "🔴" if diff < 0 else "⚪"
        st.markdown(f"{color} Diff: {diff:+,} ({pct:+.1f}%)")

    with col2:
        st.markdown("**Clicks**")
        diff = metrics_right['total_clicks'] - metrics_left['total_clicks']
        pct = ((metrics_right['total_clicks'] / metrics_left['total_clicks'] - 1) * 100) if metrics_left['total_clicks'] > 0 else 0
        st.markdown(f"Side A: {metrics_left['total_clicks']:,}")
        st.markdown(f"Side B: {metrics_right['total_clicks']:,}")
        color = "🟢" if diff > 0 else "🔴" if diff < 0 else "⚪"
        st.markdown(f"{color} Diff: {diff:+,} ({pct:+.1f}%)")

    with col3:
        st.markdown("**Applies**")
        diff = metrics_right['total_applies'] - metrics_left['total_applies']
        pct = ((metrics_right['total_applies'] / metrics_left['total_applies'] - 1) * 100) if metrics_left['total_applies'] > 0 else 0
        st.markdown(f"Side A: {metrics_left['total_applies']:,}")
        st.markdown(f"Side B: {metrics_right['total_applies']:,}")
        color = "🟢" if diff > 0 else "🔴" if diff < 0 else "⚪"
        st.markdown(f"{color} Diff: {diff:+,} ({pct:+.1f}%)")

    with col4:
        st.markdown("**Apply/Click %**")
        diff = metrics_right['apply_click_ratio'] - metrics_left['apply_click_ratio']
        st.markdown(f"Side A: {metrics_left['apply_click_ratio']:.2f}%")
        st.markdown(f"Side B: {metrics_right['apply_click_ratio']:.2f}%")
        color = "🟢" if diff > 0 else "🔴" if diff < 0 else "⚪"
        st.markdown(f"{color} Diff: {diff:+.2f}%")

    with col5:
        st.markdown("**Clicks/Vacancy**")
        diff = metrics_right['clicks_per_vacancy'] - metrics_left['clicks_per_vacancy']
        pct = ((metrics_right['clicks_per_vacancy'] / metrics_left['clicks_per_vacancy'] - 1) * 100) if metrics_left['clicks_per_vacancy'] > 0 else 0
        st.markdown(f"Side A: {metrics_left['clicks_per_vacancy']:.1f}")
        st.markdown(f"Side B: {metrics_right['clicks_per_vacancy']:.1f}")
        color = "🟢" if diff > 0 else "🔴" if diff < 0 else "⚪"
        st.markdown(f"{color} Diff: {diff:+.1f} ({pct:+.1f}%)")

    with col6:
        st.markdown("**Applies/Vacancy**")
        diff = metrics_right['applies_per_vacancy'] - metrics_left['applies_per_vacancy']
        pct = ((metrics_right['applies_per_vacancy'] / metrics_left['applies_per_vacancy'] - 1) * 100) if metrics_left['applies_per_vacancy'] > 0 else 0
        st.markdown(f"Side A: {metrics_left['applies_per_vacancy']:.2f}")
        st.markdown(f"Side B: {metrics_right['applies_per_vacancy']:.2f}")
        color = "🟢" if diff > 0 else "🔴" if diff < 0 else "⚪"
        st.markdown(f"{color} Diff: {diff:+.2f} ({pct:+.1f}%)")

    # Visual comparison
    st.markdown("---")
    st.subheader("Visual Comparison")

    comparison_data = pd.DataFrame({
        'Side': ['A', 'B', 'A', 'B', 'A', 'B'],
        'Metric': ['Vacancies', 'Vacancies', 'Clicks', 'Clicks', 'Applies', 'Applies'],
        'Value': [
            metrics_left['num_vacancies'], metrics_right['num_vacancies'],
            metrics_left['total_clicks'], metrics_right['total_clicks'],
            metrics_left['total_applies'], metrics_right['total_applies']
        ]
    })

    fig = px.bar(comparison_data, x='Metric', y='Value', color='Side', barmode='group')
    fig.update_layout(height=400)
    st.plotly_chart(fig, width='stretch')

# ============================================================================
# TAB 5: SALES INTELLIGENCE
# ============================================================================

def create_sales_intelligence_tab(df):
    """Create the Sales Intelligence tab with upgrade ROI, client scorecards,
    underperforming alerts, and sector benchmarks."""

    with st.expander("🔍 Filters", expanded=False):
        filters, apply_clicked = create_filter_panel(df, 'sales')

    if apply_clicked:
        st.session_state['sales_filters'] = filters

    filtered_df = apply_filters_to_data(df, st.session_state.get('sales_filters'))

    # ------------------------------------------------------------------
    # Section 1: Upgrade ROI
    # ------------------------------------------------------------------
    st.subheader("1. Upgrade ROI by Occupation")

    st.info(
        "**Methodology:** Figures show average clicks/applies per vacancy for each occupation and upgrade type. "
        "Only vacancies with a **single upgrade** (or no upgrade) are included to avoid double-counting. "
        "Vacancy counts shown in brackets — figures from small samples (n<10) are marked with * and should be treated with caution. "
        "Occupations with fewer than 5 vacancies are excluded."
    )

    if len(filtered_df) > 0 and 'upgrades_list' in filtered_df.columns:
        # Classify each vacancy
        work_df = filtered_df.copy()
        work_df['upgrade_count'] = work_df['upgrades_list'].apply(len)
        work_df['upgrade_category'] = work_df['upgrades_list'].apply(
            lambda x: 'No Upgrade' if not x else (x[0] if len(x) == 1 else ' + '.join(sorted(x)))
        )

        # ---- Primary view: single-upgrade vacancies only ----
        single_df = work_df[work_df['upgrade_count'] <= 1].copy()

        if len(single_df) > 0:
            # Aggregate: occupation × upgrade → mean clicks/applies + count
            agg = single_df.groupby(['occupation', 'upgrade_category']).agg(
                avg_clicks=('clicks', 'mean'),
                avg_applies=('applies', 'mean'),
                n=('clicks', 'count')
            ).reset_index()

            # Pivot to tables
            clicks_table = agg.pivot(index='occupation', columns='upgrade_category', values='avg_clicks').round(1)
            applies_table = agg.pivot(index='occupation', columns='upgrade_category', values='avg_applies').round(1)
            count_table = agg.pivot(index='occupation', columns='upgrade_category', values='n').fillna(0).astype(int)

            # Ensure "No Upgrade" is first column
            for tbl in [clicks_table, applies_table, count_table]:
                cols = list(tbl.columns)
                if 'No Upgrade' in cols:
                    cols.remove('No Upgrade')
                    cols = ['No Upgrade'] + sorted(cols)

            clicks_table = clicks_table.reindex(columns=cols)
            applies_table = applies_table.reindex(columns=cols)
            count_table = count_table.reindex(columns=cols).fillna(0).astype(int)

            # Filter: 5+ vacancies per occupation
            total_per_occ = count_table.sum(axis=1)
            mask = total_per_occ >= 5
            clicks_table = clicks_table[mask]
            applies_table = applies_table[mask]
            count_table = count_table[mask]

            if len(clicks_table) > 0:
                # Sort by total vacancy count descending
                sort_order = count_table.sum(axis=1).sort_values(ascending=False).index
                clicks_table = clicks_table.loc[sort_order]
                applies_table = applies_table.loc[sort_order]
                count_table = count_table.loc[sort_order]

                # Build display tables with "value (n=X)" format
                def build_display_table(val_table, cnt_table):
                    display = val_table.copy().astype(str)
                    for col in display.columns:
                        for idx in display.index:
                            v = val_table.at[idx, col]
                            n = int(cnt_table.at[idx, col]) if idx in cnt_table.index and col in cnt_table.columns else 0
                            if pd.isna(v) or n == 0:
                                display.at[idx, col] = '—'
                            else:
                                flag = '*' if n < 10 else ''
                                display.at[idx, col] = f'{v:.1f} (n={n}){flag}'
                    return display

                # Build uplift tables (% vs No Upgrade baseline)
                def build_uplift_table(val_table):
                    uplift = val_table.copy()
                    if 'No Upgrade' not in uplift.columns:
                        return None
                    for col in uplift.columns:
                        if col == 'No Upgrade':
                            uplift[col] = '—'
                        else:
                            for idx in uplift.index:
                                v = val_table.at[idx, col]
                                baseline = val_table.at[idx, 'No Upgrade']
                                if pd.isna(v) or pd.isna(baseline) or baseline == 0:
                                    uplift.at[idx, col] = '—'
                                else:
                                    pct = ((v - baseline) / baseline) * 100
                                    uplift.at[idx, col] = f'{pct:+.0f}%'
                    return uplift

                # View toggle
                view_mode = st.radio(
                    "Display mode", ["Absolute values", "% uplift vs No Upgrade"],
                    horizontal=True, key='upgrade_roi_mode'
                )

                tab_clicks, tab_applies = st.tabs(["Clicks per Vacancy", "Applies per Vacancy"])

                def style_display(display_df, val_table):
                    """Apply green/red highlighting vs No Upgrade baseline."""
                    def highlight_row(row):
                        baseline_key = 'No Upgrade'
                        styles = []
                        for col in row.index:
                            cell = row[col]
                            if col == baseline_key:
                                styles.append('background-color: #f0f0f0')
                            elif cell == '—' or baseline_key not in val_table.columns:
                                styles.append('')
                            else:
                                idx = row.name
                                v = val_table.at[idx, col] if col in val_table.columns else None
                                b = val_table.at[idx, baseline_key] if baseline_key in val_table.columns else None
                                if pd.isna(v) or pd.isna(b) or b == 0:
                                    styles.append('')
                                elif v > b * 1.1:
                                    styles.append('background-color: #c6efce')
                                elif v < b * 0.9:
                                    styles.append('background-color: #ffc7ce')
                                else:
                                    styles.append('')
                            return styles
                    return display_df.style.apply(highlight_row, axis=1)

                with tab_clicks:
                    if view_mode == "Absolute values":
                        display = build_display_table(clicks_table, count_table)
                    else:
                        display = build_uplift_table(clicks_table)
                    if display is not None:
                        styled = style_display(display, clicks_table)
                        st.dataframe(styled, width='stretch', height=min(500, 35 * len(display) + 40))

                with tab_applies:
                    if view_mode == "Absolute values":
                        display = build_display_table(applies_table, count_table)
                    else:
                        display = build_uplift_table(applies_table)
                    if display is not None:
                        styled = style_display(display, applies_table)
                        st.dataframe(styled, width='stretch', height=min(500, 35 * len(display) + 40))

                st.caption("Green = >10% above 'No Upgrade' baseline | Red = >10% below | Grey = baseline | * = small sample (n<10)")

                # ---- Secondary view: multi-upgrade combinations ----
                multi_df = work_df[work_df['upgrade_count'] > 1]
                if len(multi_df) > 0:
                    with st.expander(f"Upgrade Combinations ({len(multi_df)} vacancies with multiple upgrades)"):
                        combo_agg = multi_df.groupby('upgrade_category').agg(
                            vacancies=('clicks', 'count'),
                            avg_clicks=('clicks', 'mean'),
                            avg_applies=('applies', 'mean')
                        ).reset_index().sort_values('vacancies', ascending=False)
                        combo_agg.columns = ['Upgrade Combination', 'Vacancies', 'Avg Clicks', 'Avg Applies']

                        # Add baseline comparison
                        no_upgrade_clicks = single_df[single_df['upgrade_category'] == 'No Upgrade']['clicks'].mean()
                        no_upgrade_applies = single_df[single_df['upgrade_category'] == 'No Upgrade']['applies'].mean()
                        if no_upgrade_clicks and no_upgrade_clicks > 0:
                            combo_agg['Clicks vs No Upgrade'] = combo_agg['Avg Clicks'].apply(
                                lambda x: f'{((x / no_upgrade_clicks) - 1) * 100:+.0f}%')
                        if no_upgrade_applies and no_upgrade_applies > 0:
                            combo_agg['Applies vs No Upgrade'] = combo_agg['Avg Applies'].apply(
                                lambda x: f'{((x / no_upgrade_applies) - 1) * 100:+.0f}%')

                        st.dataframe(
                            combo_agg.style.format({'Avg Clicks': '{:.1f}', 'Avg Applies': '{:.1f}'}),
                            width='stretch', hide_index=True
                        )
                        st.caption("These vacancies had multiple upgrades applied simultaneously. "
                                   "Performance shown is for the full combination, not individual upgrade types.")
            else:
                st.info("Not enough data (need 5+ vacancies per occupation).")
    else:
        st.info("No data available for upgrade analysis.")

    st.markdown("---")

    # ------------------------------------------------------------------
    # Section 2: Client Scorecards
    # ------------------------------------------------------------------
    st.subheader("2. Client Scorecards")
    st.caption("Per-organisation performance benchmarked against their sector average.")

    if len(filtered_df) > 0 and 'organization_name' in filtered_df.columns:
        # Organisation selector
        orgs = sorted(filtered_df['organization_name'].dropna().unique())
        selected_orgs = st.multiselect("Select organisations to view", orgs, key='sales_org_select')

        # Calculate sector (occupation) benchmarks
        sector_benchmarks = filtered_df.groupby('occupation').agg(
            sector_avg_clicks=('clicks', 'mean'),
            sector_avg_applies=('applies', 'mean'),
            sector_vacancy_count=('clicks', 'count')
        ).reset_index()

        # Calculate per-org metrics
        org_data = filtered_df.groupby(['organization_name', 'occupation']).agg(
            vacancies=('clicks', 'count'),
            total_clicks=('clicks', 'sum'),
            total_applies=('applies', 'sum'),
            avg_clicks=('clicks', 'mean'),
            avg_applies=('applies', 'mean')
        ).reset_index()

        org_data = org_data.merge(sector_benchmarks, on='occupation', how='left')
        org_data['apply_rate'] = (org_data['total_applies'] / org_data['total_clicks'] * 100).fillna(0).round(1)
        org_data['clicks_vs_sector'] = ((org_data['avg_clicks'] / org_data['sector_avg_clicks'] - 1) * 100).round(1)
        org_data['applies_vs_sector'] = ((org_data['avg_applies'] / org_data['sector_avg_applies'] - 1) * 100).round(1)

        display_orgs = selected_orgs if selected_orgs else orgs[:10]

        for org in display_orgs:
            org_rows = org_data[org_data['organization_name'] == org]
            if len(org_rows) == 0:
                continue

            total_vacancies = int(org_rows['vacancies'].sum())
            total_clicks = int(org_rows['total_clicks'].sum())
            total_applies = int(org_rows['total_applies'].sum())
            apply_rate = (total_applies / total_clicks * 100) if total_clicks > 0 else 0

            with st.expander(f"**{org}** — {total_vacancies} vacancies, {total_clicks:,} clicks, {total_applies:,} applies"):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Vacancies", f"{total_vacancies:,}")
                col2.metric("Total Clicks", f"{total_clicks:,}")
                col3.metric("Total Applies", f"{total_applies:,}")
                col4.metric("Apply Rate", f"{apply_rate:.1f}%")

                # Per-occupation breakdown with sector comparison
                display_cols = ['occupation', 'vacancies', 'avg_clicks', 'sector_avg_clicks', 'clicks_vs_sector',
                                'avg_applies', 'sector_avg_applies', 'applies_vs_sector']
                display_df = org_rows[display_cols].copy()
                display_df.columns = ['Occupation', 'Vacancies', 'Avg Clicks', 'Sector Avg Clicks', 'Clicks vs Sector %',
                                      'Avg Applies', 'Sector Avg Applies', 'Applies vs Sector %']
                display_df = display_df.sort_values('Vacancies', ascending=False)

                def color_vs_sector(val):
                    if pd.isna(val):
                        return ''
                    if val > 10:
                        return 'color: #006100; background-color: #c6efce'
                    elif val < -10:
                        return 'color: #9c0006; background-color: #ffc7ce'
                    return ''

                styled = display_df.style.map(
                    color_vs_sector, subset=['Clicks vs Sector %', 'Applies vs Sector %']
                ).format({
                    'Avg Clicks': '{:.1f}', 'Sector Avg Clicks': '{:.1f}',
                    'Avg Applies': '{:.1f}', 'Sector Avg Applies': '{:.1f}',
                    'Clicks vs Sector %': '{:+.1f}%', 'Applies vs Sector %': '{:+.1f}%'
                })
                st.dataframe(styled, width='stretch', hide_index=True)
    else:
        st.info("No data available for client scorecards.")

    st.markdown("---")

    # ------------------------------------------------------------------
    # Section 3: Underperforming Vacancy Alerts
    # ------------------------------------------------------------------
    st.subheader("3. Underperforming Vacancy Alerts")
    st.caption("Published vacancies performing below the 25th percentile for their occupation.")

    if len(filtered_df) > 0:
        # Only look at published vacancies
        published = filtered_df[filtered_df['workflow_state'] == 'published'].copy()

        if len(published) > 0:
            # Calculate per-occupation thresholds
            occ_stats = filtered_df.groupby('occupation').agg(
                p25_clicks=('clicks', lambda x: x.quantile(0.25)),
                avg_clicks=('clicks', 'mean'),
                avg_applies=('applies', 'mean')
            ).reset_index()

            published = published.merge(occ_stats, on='occupation', how='left')

            # Flag underperformers
            underperformers = published[published['clicks'] < published['p25_clicks']].copy()

            if len(underperformers) > 0:
                # Calculate days live
                now = pd.Timestamp.now()
                if 'first_event_date' in underperformers.columns:
                    underperformers['days_live'] = (now - underperformers['first_event_date']).dt.days

                display_df = underperformers[['title', 'organization_name', 'occupation',
                                              'clicks', 'avg_clicks', 'applies', 'avg_applies',
                                              'days_live']].copy()
                display_df.columns = ['Title', 'Organisation', 'Occupation',
                                      'Clicks', 'Sector Avg Clicks', 'Applies', 'Sector Avg Applies',
                                      'Days Live']
                display_df = display_df.sort_values('Clicks', ascending=True)

                st.warning(f"**{len(underperformers):,}** published vacancies are below the 25th percentile for their occupation.")

                st.dataframe(
                    display_df.style.format({
                        'Sector Avg Clicks': '{:.1f}',
                        'Sector Avg Applies': '{:.1f}'
                    }),
                    width='stretch',
                    hide_index=True,
                    height=min(600, 35 * len(display_df) + 40)
                )
            else:
                st.success("No underperforming published vacancies found.")
        else:
            st.info("No published vacancies in the filtered data.")
    else:
        st.info("No data available.")

    st.markdown("---")

    # ------------------------------------------------------------------
    # Section 4: Sector Benchmarks
    # ------------------------------------------------------------------
    st.subheader("4. Sector Benchmarks")
    st.caption("Performance benchmarks by occupation — use these figures when talking to clients.")

    if len(filtered_df) > 0 and 'occupation' in filtered_df.columns:
        sector = filtered_df.groupby('occupation').agg(
            vacancies=('clicks', 'count'),
            median_clicks=('clicks', 'median'),
            mean_clicks=('clicks', 'mean'),
            median_applies=('applies', 'median'),
            mean_applies=('applies', 'mean'),
        ).reset_index()

        # Apply rate per occupation
        occ_totals = filtered_df.groupby('occupation').agg(
            total_clicks=('clicks', 'sum'),
            total_applies=('applies', 'sum')
        ).reset_index()
        occ_totals['apply_rate'] = (occ_totals['total_applies'] / occ_totals['total_clicks'] * 100).fillna(0)
        sector = sector.merge(occ_totals[['occupation', 'apply_rate']], on='occupation', how='left')

        # Average days live
        if 'first_event_date' in filtered_df.columns and 'last_event_date' in filtered_df.columns:
            filtered_df_copy = filtered_df.copy()
            filtered_df_copy['days_live'] = (filtered_df_copy['last_event_date'] - filtered_df_copy['first_event_date']).dt.days
            avg_days = filtered_df_copy.groupby('occupation')['days_live'].mean().reset_index()
            avg_days.columns = ['occupation', 'avg_days_live']
            sector = sector.merge(avg_days, on='occupation', how='left')
        else:
            sector['avg_days_live'] = None

        sector = sector[sector['vacancies'] >= 5].sort_values('vacancies', ascending=False)
        sector.columns = ['Occupation', 'Vacancies', 'Median Clicks', 'Mean Clicks',
                          'Median Applies', 'Mean Applies', 'Apply Rate %', 'Avg Days Live']

        if len(sector) > 0:
            def _gradient_green(val, col_min, col_max):
                if pd.isna(val) or col_max == col_min:
                    return ''
                pct = (val - col_min) / (col_max - col_min)
                r = int(245 - pct * 47)
                g = int(245 - pct * 12)
                b = int(245 - pct * 47)
                return f'background-color: rgb({r},{g},{b})'

            def apply_manual_gradient(df_styled, col, color='green'):
                col_data = sector[col].dropna()
                if len(col_data) == 0:
                    return df_styled
                cmin, cmax = col_data.min(), col_data.max()
                if color == 'green':
                    return df_styled.map(lambda v: f'background-color: rgba(34,139,34,{min((v-cmin)/(cmax-cmin),1)*0.3:.2f})' if pd.notna(v) and cmax > cmin else '', subset=[col])
                elif color == 'blue':
                    return df_styled.map(lambda v: f'background-color: rgba(30,90,200,{min((v-cmin)/(cmax-cmin),1)*0.3:.2f})' if pd.notna(v) and cmax > cmin else '', subset=[col])
                else:
                    return df_styled.map(lambda v: f'background-color: rgba(220,120,20,{min((v-cmin)/(cmax-cmin),1)*0.3:.2f})' if pd.notna(v) and cmax > cmin else '', subset=[col])

            styled = sector.style.format({
                'Median Clicks': '{:.0f}', 'Mean Clicks': '{:.1f}',
                'Median Applies': '{:.0f}', 'Mean Applies': '{:.1f}',
                'Apply Rate %': '{:.1f}%', 'Avg Days Live': '{:.0f}'
            })
            styled = apply_manual_gradient(styled, 'Median Clicks', 'green')
            styled = apply_manual_gradient(styled, 'Median Applies', 'blue')
            styled = apply_manual_gradient(styled, 'Apply Rate %', 'orange')

            st.dataframe(styled, width='stretch', hide_index=True,
                         height=min(600, 35 * len(sector) + 40))
        else:
            st.info("Not enough data (need 5+ vacancies per occupation).")
    else:
        st.info("No data available for benchmarks.")


# ============================================================================
# TAB 6: LAUNCH TIMING
# ============================================================================

def create_launch_timing_tab(launch_df):
    """Analyse vacancy performance by day offset from launch, with day-of-week analysis."""

    st.subheader("Vacancy Performance by Day Since Launch")
    st.caption("Each vacancy is normalised to Day 0 (first event). Averages across all vacancies show the typical performance curve.")

    if launch_df is None or len(launch_df) == 0:
        st.warning("No launch timing data available. This requires event-level data from the enriched table.")
        return

    df = launch_df.copy()

    # Add occupation column for filtering
    if 'occupational_fields' in df.columns:
        df['occupation'] = df['occupational_fields'].apply(lambda x:
            str(x).split('|')[0].strip() if pd.notna(x) and str(x).strip() else 'Unknown'
        )

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        if 'occupation' in df.columns:
            occupations = sorted(df['occupation'].dropna().unique())
            selected_occs = st.multiselect("Filter by Occupation", occupations, key='launch_occ')
            if selected_occs:
                df = df[df['occupation'].isin(selected_occs)]
    with col2:
        metric_choice = st.radio("Metric", ["Clicks (Views)", "Applies"], horizontal=True, key='launch_metric')
        metric_col = 'clicks' if 'Clicks' in metric_choice else 'applies'

    vacancy_count = df['entity_id_str'].nunique()
    st.info(f"Analysing **{vacancy_count:,}** vacancies")

    # Map BigQuery DAYOFWEEK (1=Sun, 2=Mon, ... 7=Sat) to readable names
    dow_map = {1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
               5: 'Thursday', 6: 'Friday', 7: 'Saturday'}
    dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    df['launch_day_name'] = df['launch_dow'].map(dow_map)
    df['event_day_name'] = df['event_dow'].map(dow_map)

    # ------------------------------------------------------------------
    # Chart 1: Average performance by day offset (Day 0 - Day 30)
    # ------------------------------------------------------------------
    st.markdown("### Performance Curve (Day 0 — Day 30)")

    avg_by_day = df.groupby('day_offset')[metric_col].mean().reset_index()
    avg_by_day.columns = ['Day', metric_col]

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=avg_by_day['Day'], y=avg_by_day[metric_col],
        mode='lines+markers',
        name=f'Avg {metric_col.title()}',
        line=dict(color='#2563eb', width=2),
        marker=dict(size=5)
    ))

    # Shade weekends (approximate: if Day 0 is any day, weekends fall at offsets
    # that depend on launch day — so instead shade typical weekend bands)
    # We'll use the event_dow to mark which day_offsets tend to be weekends
    weekend_offsets = df[df['event_day_name'].isin(['Saturday', 'Sunday'])].groupby('day_offset').size()
    all_offsets = df.groupby('day_offset').size()
    weekend_pct = (weekend_offsets / all_offsets).fillna(0)
    # Shade offsets where >40% of events fall on weekends
    weekend_days = weekend_pct[weekend_pct > 0.4].index.tolist()

    for d in weekend_days:
        fig1.add_vrect(x0=d - 0.5, x1=d + 0.5, fillcolor='rgba(200,200,200,0.2)',
                       line_width=0, layer='below')

    fig1.update_layout(
        height=400,
        xaxis_title='Days Since Launch',
        yaxis_title=f'Avg {metric_col.title()} per Vacancy',
        hovermode='x unified',
        annotations=[dict(x=0.98, y=0.98, xref='paper', yref='paper',
                          text='Shaded = Weekend', showarrow=False,
                          font=dict(size=10, color='grey'))]
    )
    st.plotly_chart(fig1, width='stretch')

    # ------------------------------------------------------------------
    # Chart 2: Performance curve by launch day of week
    # ------------------------------------------------------------------
    st.markdown("### Performance by Launch Day of Week")
    st.caption("Which day of the week is best to launch a vacancy?")

    avg_by_dow = df.groupby(['launch_day_name', 'day_offset'])[metric_col].mean().reset_index()

    colors = {'Monday': '#2563eb', 'Tuesday': '#7c3aed', 'Wednesday': '#059669',
              'Thursday': '#d97706', 'Friday': '#dc2626', 'Saturday': '#6b7280', 'Sunday': '#9ca3af'}

    fig2 = go.Figure()
    for day in dow_order:
        day_data = avg_by_dow[avg_by_dow['launch_day_name'] == day]
        if len(day_data) > 0:
            fig2.add_trace(go.Scatter(
                x=day_data['day_offset'], y=day_data[metric_col],
                mode='lines',
                name=day,
                line=dict(color=colors.get(day, '#333'), width=2),
                opacity=0.8
            ))

    fig2.update_layout(
        height=450,
        xaxis_title='Days Since Launch',
        yaxis_title=f'Avg {metric_col.title()} per Vacancy',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    st.plotly_chart(fig2, width='stretch')

    # ------------------------------------------------------------------
    # Summary table: first 7 days total by launch day
    # ------------------------------------------------------------------
    st.markdown("### First 7 Days Summary by Launch Day")

    first_week = df[df['day_offset'] <= 6].copy()
    summary = first_week.groupby('launch_day_name').agg(
        vacancies=('entity_id_str', 'nunique'),
        avg_clicks_7d=('clicks', 'mean'),
        avg_applies_7d=('applies', 'mean')
    ).reset_index()

    # Multiply by 7 to get total over first week (avg per day × 7 days)
    summary['avg_clicks_7d'] = (summary['avg_clicks_7d'] * 7).round(1)
    summary['avg_applies_7d'] = (summary['avg_applies_7d'] * 7).round(1)

    # Sort by day of week
    summary['sort_key'] = summary['launch_day_name'].map({d: i for i, d in enumerate(dow_order)})
    summary = summary.sort_values('sort_key').drop(columns='sort_key')

    summary.columns = ['Launch Day', 'Vacancies', 'Avg Clicks (First 7 Days)', 'Avg Applies (First 7 Days)']

    def _manual_grad(df_styled, col, r, g, b):
        col_data = summary[col].dropna()
        if len(col_data) == 0:
            return df_styled
        cmin, cmax = col_data.min(), col_data.max()
        return df_styled.map(
            lambda v: f'background-color: rgba({r},{g},{b},{min((v-cmin)/(cmax-cmin),1)*0.3:.2f})'
            if pd.notna(v) and cmax > cmin else '', subset=[col]
        )

    styled = summary.style.format({'Avg Clicks (First 7 Days)': '{:.1f}', 'Avg Applies (First 7 Days)': '{:.1f}'})
    styled = _manual_grad(styled, 'Avg Clicks (First 7 Days)', 34, 139, 34)
    styled = _manual_grad(styled, 'Avg Applies (First 7 Days)', 30, 90, 200)
    st.dataframe(styled, width='stretch', hide_index=True)


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    st.title("📊 Job Performance Dashboard (v2 Dev)")

    # Sidebar - Data Loading Controls
    st.sidebar.header("⚙️ Data Loading Settings")

    days_back = st.sidebar.slider(
        "Vacancies Active In Last (Days)",
        min_value=7,
        max_value=365,
        value=365,
        step=7,
        help="Show vacancies that received at least one view or click within this many days"
    )

    # Sampling option for faster testing
    enable_sampling = st.sidebar.checkbox(
        "Enable Sampling (Faster)",
        value=False,
        help="Limit data to a sample for faster loading during testing"
    )

    sample_size = None
    if enable_sampling:
        sample_size = st.sidebar.number_input(
            "Sample Size (rows)",
            min_value=1000,
            max_value=100000,
            value=10000,
            step=1000,
            help="Number of rows to sample from BigQuery"
        )

    # Load data with progress indicators
    progress_bar = st.progress(0)
    status_text = st.empty()

    status_text.text("Loading data from BigQuery... 0%")
    df_raw, daily_totals = load_all_data(days_back=days_back, sample_size=sample_size)
    progress_bar.progress(30)

    status_text.text("Loading launch timing data... 30%")
    launch_timing_df = load_launch_timing_data(days_back=days_back)
    progress_bar.progress(40)

    status_text.text("Loading importer mapping... 40%")
    importer_mapping = load_importer_mapping()
    progress_bar.progress(50)

    # Process enriched data
    status_text.text("Preparing enriched data... 50%")
    df = df_raw.copy()
    df = prepare_enriched_data(df)  # Rename enriched table columns
    progress_bar.progress(60)

    status_text.text("Applying importer mapping... 60%")
    df = apply_importer_mapping(df, importer_mapping)
    progress_bar.progress(70)

    status_text.text("Parsing upgrades... 70%")
    df = parse_upgrades(df)
    progress_bar.progress(80)

    status_text.text("Parsing dates... 80%")
    df = parse_dates_in_jobiqo(df)  # Parse timestamp columns
    progress_bar.progress(90)

    status_text.text("Adding occupation column... 90%")
    df = add_occupation_column(df)
    progress_bar.progress(100)

    status_text.text("✅ Data loaded successfully!")
    progress_bar.empty()
    status_text.empty()

    # Initialize session state for all tabs
    for tab_prefix in ['overview', 'deepdive', 'vacancy', 'comp_left', 'comp_right', 'sales']:
        if f'{tab_prefix}_filters' not in st.session_state:
            st.session_state[f'{tab_prefix}_filters'] = None

    # Sidebar
    st.sidebar.markdown("---")
    st.sidebar.header("📊 Dashboard Info")

    # Authentication status
    try:
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            st.sidebar.success("🔐 Authentication: Streamlit Secrets")
        else:
            st.sidebar.info("🔐 Authentication: Local File")
    except:
        st.sidebar.info("🔐 Authentication: Local File")

    # Data loading info
    st.sidebar.info(f"📊 Vacancies active in last {days_back} days")
    st.sidebar.metric("Total Vacancies", f"{len(df):,}")
    if 'clicks' in df.columns:
        st.sidebar.metric("Total Clicks", f"{int(df['clicks'].sum()):,}")
        st.sidebar.metric("Total Applies", f"{int(df['applies'].sum()):,}")
    st.sidebar.info(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if enable_sampling:
        st.sidebar.warning(f"⚠️ Sampling enabled: showing {len(df):,} of all vacancies")

    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Debug: Show importer mapping status
    with st.sidebar.expander("🔧 Importer Mapping Debug"):
        st.write(f"Mapping loaded: {len(importer_mapping)} entries")
        if importer_mapping:
            st.write("**Mapping:**")
            for k, v in importer_mapping.items():
                st.write(f"'{k}' → '{v}'")

        # Show unique importer IDs in data
        if 'importer_ID' in df.columns:
            unique_ids = df['importer_ID'].astype(str).str.strip().unique()
            st.write(f"\n**Unique IDs in data:** {len(unique_ids)}")
            for uid in sorted(unique_ids):
                matched = importer_mapping.get(uid, "NOT FOUND")
                st.write(f"'{uid}' → {matched}")

        # Show unique importer names in data
        if 'importer_name' in df.columns:
            unique_names = df['importer_name'].unique()
            st.write(f"\n**Unique names in data:** {len(unique_names)}")
            for name in sorted(unique_names):
                count = len(df[df['importer_name'] == name])
                st.write(f"'{name}': {count} vacancies")

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Overview",
        "🔍 Deep Dive",
        "📋 Vacancy Performance",
        "⚖️ Comparison",
        "💼 Sales Intelligence",
        "📅 Launch Timing"
    ])

    with tab1:
        create_overview_tab(df, daily_totals=daily_totals)

    with tab2:
        create_deep_dive_tab(df)

    with tab3:
        create_vacancy_performance_tab(df, full_df=df)

    with tab4:
        create_comparison_tab(df)

    with tab5:
        create_sales_intelligence_tab(df)

    with tab6:
        create_launch_timing_tab(launch_timing_df)

if __name__ == "__main__":
    main()
