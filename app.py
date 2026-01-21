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
    page_title="Job Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# BigQuery configuration
BQ_PROJECT_ID = "site-monitoring-421401"
BQ_DATASET_ID = "job_data_export"
BQ_TABLE_ID = "job_performance_enriched"

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

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data_from_bigquery(days_back=30, sample_size=None):
    """Load data from BigQuery enriched table with date filter.

    The enriched table is partitioned by event_date_parsed for fast queries.
    It includes all metadata and parsed location fields.

    Args:
        days_back: Number of days to look back
        sample_size: If set, limit the result to this many rows (for testing)
    """
    try:
        client = get_bigquery_client()

        # First check if the enriched table exists
        try:
            table_ref = f"{BQ_PROJECT_ID}.{BQ_DATASET_ID}.{BQ_TABLE_ID}"
            client.get_table(table_ref)
        except Exception as table_error:
            st.error("❌ **Enriched table not found in BigQuery**")
            st.markdown("""
            The `job_performance_enriched` table hasn't been created yet.

            **To create it:**
            1. Go to BigQuery console: https://console.cloud.google.com/bigquery?project=site-monitoring-421401
            2. Run the SQL from `scripts/create_enriched_table_with_regions.sql` (Step 1, lines 6-96)
            3. Wait for the query to complete (may take a few minutes)
            4. Refresh this dashboard

            **Error details:** {str(table_error)}
            """)
            st.stop()

        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        query = f"""
        SELECT
            entity_id_str,
            event_date_parsed,
            event_name,
            title_export,
            organization_name,
            location_region_matched,
            occupational_fields_export,
            importer_ID,
            publishing_date,
            expiration_date,
            workflow_state,
            upgrades
        FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.{BQ_TABLE_ID}`
        WHERE event_date_parsed >= '{cutoff_date}'
        AND event_name IN ('job_visit', 'job_apply_start')
        """

        # Add LIMIT clause if sampling
        if sample_size:
            query += f"\nLIMIT {sample_size}"

        info_msg = f"📊 Loading data for last {days_back} days from enriched table"
        if sample_size:
            info_msg += f" (sampling {sample_size:,} rows)"
        st.info(info_msg + "...")

        # Create progress indicators
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Stage 1: Start query
        status_text.text("Starting BigQuery query... 0%")
        progress_bar.progress(10)

        # Stage 2: Submit query
        query_job = client.query(query)
        status_text.text("Query submitted, waiting for results... 30%")
        progress_bar.progress(30)

        # Stage 3: Wait for completion
        query_job.result()
        status_text.text("Query complete, fetching data... 60%")
        progress_bar.progress(60)

        # Stage 4: Convert to dataframe
        df = query_job.to_dataframe(create_bqstorage_client=False)
        status_text.text("Processing data... 90%")
        progress_bar.progress(90)

        # Stage 5: Complete
        progress_bar.progress(100)
        status_text.text(f"Complete! Loaded {len(df):,} rows")

        # Clean up progress indicators immediately
        progress_bar.empty()
        status_text.empty()

        st.success(f"✅ Loaded {len(df):,} rows from BigQuery (partitioned table)")
        return df
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        st.markdown("""
        **Troubleshooting:**
        - Check BigQuery table exists: `job_data_export.job_performance_enriched`
        - Verify service account has `bigquery.jobs.create` permission
        - Check the table has data for the requested date range
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


# ============================================================================
# DATA PROCESSING FUNCTIONS
# ============================================================================

def apply_importer_mapping(df, mapping):
    """Apply importer ID to name mapping using find and replace."""
    if 'importer_ID' not in df.columns:
        df['importer_name'] = 'Unknown'
        return df

    # Convert importer_ID to string and strip whitespace for matching
    df = df.copy()
    df['importer_id_str'] = df['importer_ID'].astype(str).str.strip()

    if mapping:
        # Use map to replace importer IDs with names
        df['importer_name'] = df['importer_id_str'].map(mapping)
        # For any unmapped values, show the ID
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
    """Prepare enriched data by renaming columns for dashboard compatibility."""
    df = df.copy()

    # Rename enriched table columns to match dashboard expectations
    column_mapping = {
        'entity_id_str': 'entity_id',
        'event_date_parsed': 'event_date',
        'title_export': 'title',
        'location_region_matched': 'uk_region',
        'occupational_fields_export': 'occupational_fields',
        'publishing_date': 'start_date',
        'expiration_date': 'end_date'
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
    """Parse start and end dates from Jobiqo data."""
    if 'event_date' in df.columns:
        df['event_date'] = pd.to_datetime(df['event_date'], errors='coerce', utc=True).dt.tz_localize(None)
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
        # Date Range Filter
        if 'event_date' in df.columns and pd.api.types.is_datetime64_any_dtype(df['event_date']):
            min_date = df['event_date'].min().date()
            max_date = df['event_date'].max().date()
            default_start = (datetime.now() - timedelta(days=default_months*30)).date()
            default_start = max(default_start, min_date)

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
        # Region Filter
        if 'uk_region' in df.columns:
            regions = sorted(df['uk_region'].dropna().unique())
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
            use_container_width=True
        )

    st.markdown("---")

    return filters, apply_clicked

def apply_filters_to_data(df, filters):
    """Apply filter selections to dataframe."""
    # Handle None filters (no filters applied yet)
    if filters is None:
        return df.copy()

    filtered = df.copy()

    # Date Range Filter (vacancy must be active during period, events must occur during period)
    if filters.get('date_range') and len(filters['date_range']) == 2:
        start_date, end_date = filters['date_range']

        # Filter 1: Vacancy must be active during the date range
        if 'start_date' in filtered.columns and 'end_date' in filtered.columns:
            # Vacancy overlaps with selected date range
            filtered = filtered[
                (filtered['start_date'] <= pd.Timestamp(end_date)) &
                (filtered['end_date'] >= pd.Timestamp(start_date))
            ]

        # Filter 2: Only count events within the date range
        if 'event_date' in filtered.columns and pd.api.types.is_datetime64_any_dtype(filtered['event_date']):
            filtered = filtered[
                (filtered['event_date'].dt.date >= start_date) &
                (filtered['event_date'].dt.date <= end_date)
            ]

    # Importer Filter
    if filters.get('importer') and 'importer_name' in filtered.columns:
        filtered = filtered[filtered['importer_name'].isin(filters['importer'])]

    # Company Filter
    if filters.get('company') and 'organization_name' in filtered.columns:
        filtered = filtered[filtered['organization_name'].isin(filters['company'])]

    # Region Filter
    if filters.get('region') and 'uk_region' in filtered.columns:
        filtered = filtered[filtered['uk_region'].isin(filters['region'])]

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
    """Calculate key metrics from dataframe with robust statistics (optimized)."""
    entity_col = 'entity_id' if 'entity_id' in df.columns else df.columns[0]

    metrics = {}
    metrics['num_vacancies'] = df[entity_col].nunique()

    if 'event_name' in df.columns:
        # Vectorized counting
        event_counts = df['event_name'].value_counts()
        metrics['total_clicks'] = event_counts.get('job_visit', 0)
        metrics['total_applies'] = event_counts.get('job_apply_start', 0)
    else:
        metrics['total_clicks'] = len(df)
        metrics['total_applies'] = 0

    metrics['apply_click_ratio'] = (metrics['total_applies'] / metrics['total_clicks'] * 100) if metrics['total_clicks'] > 0 else 0

    # Calculate per-vacancy metrics with robust statistics (vectorized)
    if metrics['num_vacancies'] > 0 and 'event_name' in df.columns:
        # Vectorized groupby operations (much faster than loops)
        clicks_by_vacancy = df[df['event_name'] == 'job_visit'].groupby(entity_col).size()
        applies_by_vacancy = df[df['event_name'] == 'job_apply_start'].groupby(entity_col).size()

        # Fill missing vacancies with 0
        all_vacancies = df[entity_col].unique()
        vacancy_clicks = clicks_by_vacancy.reindex(all_vacancies, fill_value=0).values
        vacancy_applies = applies_by_vacancy.reindex(all_vacancies, fill_value=0).values

        # Median (robust to outliers)
        metrics['median_clicks_per_vacancy'] = np.median(vacancy_clicks) if len(vacancy_clicks) > 0 else 0
        metrics['median_applies_per_vacancy'] = np.median(vacancy_applies) if len(vacancy_applies) > 0 else 0

        # Mean with outlier removal (IQR method)
        clicks_no_outliers = remove_outliers_iqr(vacancy_clicks.tolist())
        applies_no_outliers = remove_outliers_iqr(vacancy_applies.tolist())

        metrics['mean_clicks_per_vacancy'] = np.mean(clicks_no_outliers) if clicks_no_outliers else 0
        metrics['mean_applies_per_vacancy'] = np.mean(applies_no_outliers) if applies_no_outliers else 0

        # Keep original simple averages for compatibility
        metrics['clicks_per_vacancy'] = metrics['median_clicks_per_vacancy']  # Default to median
        metrics['applies_per_vacancy'] = metrics['median_applies_per_vacancy']  # Default to median
    else:
        metrics['median_clicks_per_vacancy'] = 0
        metrics['median_applies_per_vacancy'] = 0
        metrics['mean_clicks_per_vacancy'] = 0
        metrics['mean_applies_per_vacancy'] = 0
        metrics['clicks_per_vacancy'] = 0
        metrics['applies_per_vacancy'] = 0

    return metrics

def calculate_quartile_metrics(df):
    """Calculate metrics by performance quartiles (top 25%, middle 50%, bottom 25%) - optimized."""
    entity_col = 'entity_id' if 'entity_id' in df.columns else df.columns[0]

    if 'event_name' not in df.columns:
        return None

    # Vectorized groupby operations
    clicks_by_vacancy = df[df['event_name'] == 'job_visit'].groupby(entity_col).size()
    applies_by_vacancy = df[df['event_name'] == 'job_apply_start'].groupby(entity_col).size()

    # Fill missing vacancies with 0
    all_vacancies = df[entity_col].unique()
    vacancy_clicks = clicks_by_vacancy.reindex(all_vacancies, fill_value=0)
    vacancy_applies = applies_by_vacancy.reindex(all_vacancies, fill_value=0)

    # Calculate quartile thresholds based on clicks
    if len(vacancy_clicks) < 4:
        return None  # Need at least 4 vacancies for quartiles

    q1_threshold = vacancy_clicks.quantile(0.25)
    q3_threshold = vacancy_clicks.quantile(0.75)

    # Categorize vacancies using vectorized operations
    top_25_mask = vacancy_clicks >= q3_threshold
    middle_50_mask = (vacancy_clicks >= q1_threshold) & (vacancy_clicks < q3_threshold)
    bottom_25_mask = vacancy_clicks < q1_threshold

    # Calculate metrics for each quartile
    quartiles = {}

    for name, mask in [('top_25', top_25_mask), ('middle_50', middle_50_mask), ('bottom_25', bottom_25_mask)]:
        ids = vacancy_clicks[mask].index
        total_clicks = vacancy_clicks[mask].sum()
        total_applies = vacancy_applies[ids].sum()
        num_vacancies = len(ids)

        quartiles[name] = {
            'num_vacancies': num_vacancies,
            'total_clicks': int(total_clicks),
            'total_applies': int(total_applies),
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

def create_overview_tab(df):
    """Create the Overview Dashboard tab."""
    st.header("📊 Overview Dashboard")

    # Debug info
    st.info(f"📋 Dataset contains {len(df):,} total rows")

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

    # Show filtered row count
    st.info(f"📊 Showing {len(filtered_df):,} rows after filters")

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
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Vacancies", f"{quartiles['top_25']['num_vacancies']:,}")

        with col2:
            st.metric("Total Clicks", f"{quartiles['top_25']['total_clicks']:,}")

        with col3:
            st.metric("Total Applies", f"{quartiles['top_25']['total_applies']:,}")

        with col4:
            st.metric("Avg Clicks/Vac", f"{quartiles['top_25']['clicks_per_vacancy']:.1f}")

        st.markdown("---")

        # Row 3: Middle 50% (Average Performers)
        st.markdown("### 🟡 Middle 50% Performers")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Vacancies", f"{quartiles['middle_50']['num_vacancies']:,}")

        with col2:
            st.metric("Total Clicks", f"{quartiles['middle_50']['total_clicks']:,}")

        with col3:
            st.metric("Total Applies", f"{quartiles['middle_50']['total_applies']:,}")

        with col4:
            st.metric("Avg Clicks/Vac", f"{quartiles['middle_50']['clicks_per_vacancy']:.1f}")

        st.markdown("---")

        # Row 4: Bottom 25% (Needs Improvement)
        st.markdown("### 🔴 Bottom 25% Performers")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Vacancies", f"{quartiles['bottom_25']['num_vacancies']:,}")

        with col2:
            st.metric("Total Clicks", f"{quartiles['bottom_25']['total_clicks']:,}")

        with col3:
            st.metric("Total Applies", f"{quartiles['bottom_25']['total_applies']:,}")

        with col4:
            st.metric("Avg Clicks/Vac", f"{quartiles['bottom_25']['clicks_per_vacancy']:.1f}")

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

    # Time Series
    if 'event_date' in filtered_df.columns and 'event_name' in filtered_df.columns:
        st.subheader("Trends Over Time")

        daily_clicks = filtered_df[filtered_df['event_name'] == 'job_visit'].groupby(
            filtered_df['event_date'].dt.date
        ).size().reset_index(name='Clicks')

        daily_applies = filtered_df[filtered_df['event_name'] == 'job_apply_start'].groupby(
            filtered_df['event_date'].dt.date
        ).size().reset_index(name='Applies')

        daily_data = pd.merge(daily_clicks, daily_applies, on='event_date', how='outer').fillna(0)
        daily_data = daily_data.sort_values('event_date')

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily_data['event_date'], y=daily_data['Clicks'],
                                name='Clicks', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=daily_data['event_date'], y=daily_data['Applies'],
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
                    'Mean Clicks (IQR)': round(imp_metrics['mean_clicks_per_vacancy'], 1),
                    'Median Applies': round(imp_metrics['median_applies_per_vacancy'], 2),
                    'Mean Applies (IQR)': round(imp_metrics['mean_applies_per_vacancy'], 2),
                    'Apply/Click %': round(imp_metrics['apply_click_ratio'], 2)
                })

            importer_df = pd.DataFrame(importer_stats).sort_values('Median Clicks', ascending=False)

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
                name='Mean Clicks/Vacancy (IQR)',
                x=importer_df['Importer'],
                y=importer_df['Mean Clicks (IQR)'],
                text=importer_df['Mean Clicks (IQR)'],
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

    with col2:
        if 'uk_region' in filtered_df.columns:
            st.subheader("Performance by Region")
            region_stats = []
            for region in filtered_df['uk_region'].unique():
                reg_df = filtered_df[filtered_df['uk_region'] == region]
                reg_metrics = calculate_metrics(reg_df)
                region_stats.append({
                    'Region': region,
                    'Vacancies': reg_metrics['num_vacancies'],
                    'Median Clicks': round(reg_metrics['median_clicks_per_vacancy'], 1),
                    'Mean Clicks (IQR)': round(reg_metrics['mean_clicks_per_vacancy'], 1),
                    'Median Applies': round(reg_metrics['median_applies_per_vacancy'], 2),
                    'Mean Applies (IQR)': round(reg_metrics['mean_applies_per_vacancy'], 2),
                    'Apply/Click %': round(reg_metrics['apply_click_ratio'], 2)
                })

            region_df = pd.DataFrame(region_stats).sort_values('Median Clicks', ascending=False)

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
                name='Mean Clicks/Vacancy (IQR)',
                x=region_df['Region'],
                y=region_df['Mean Clicks (IQR)'],
                text=region_df['Mean Clicks (IQR)'],
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

    # Debug info
    st.info(f"📋 Dataset contains {len(df):,} total rows")

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

    # Show filtered row count
    st.info(f"📊 Showing {len(filtered_df):,} rows after filters")

    # Benchmark Comparison Table
    st.subheader("📊 Benchmark Comparison Table")

    dimension = st.selectbox(
        "Group by:",
        ['Importer', 'Region', 'Occupation', 'Company'],
        key='deepdive_dimension'
    )

    column_map = {
        'Importer': 'importer_name',
        'Region': 'uk_region',
        'Occupation': 'occupation',
        'Company': 'organization_name'
    }

    if column_map[dimension] in filtered_df.columns:
        benchmark_data = []
        for value in filtered_df[column_map[dimension]].unique():
            subset = filtered_df[filtered_df[column_map[dimension]] == value]
            metrics = calculate_metrics(subset)
            benchmark_data.append({
                dimension: value,
                'Vacancies': metrics['num_vacancies'],
                'Total Clicks': metrics['total_clicks'],
                'Total Applies': metrics['total_applies'],
                'Apply/Click %': round(metrics['apply_click_ratio'], 2),
                'Median Clicks/Vac': round(metrics['median_clicks_per_vacancy'], 1),
                'Mean Clicks/Vac (IQR)': round(metrics['mean_clicks_per_vacancy'], 1),
                'Median Applies/Vac': round(metrics['median_applies_per_vacancy'], 2),
                'Mean Applies/Vac (IQR)': round(metrics['mean_applies_per_vacancy'], 2)
            })

        benchmark_df = pd.DataFrame(benchmark_data).sort_values('Median Clicks/Vac', ascending=False)
        st.dataframe(benchmark_df, width='stretch', height=400)

        # Export
        csv = benchmark_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Benchmark Data",
            csv,
            f"benchmark_{dimension.lower()}_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )

    st.markdown("---")

    # Heatmap
    st.subheader("🗺️ Performance Heatmap")

    if 'uk_region' in filtered_df.columns and 'importer_name' in filtered_df.columns:
        heatmap_data = []
        for region in filtered_df['uk_region'].unique():
            for importer in filtered_df['importer_name'].unique():
                subset = filtered_df[
                    (filtered_df['uk_region'] == region) &
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

def create_vacancy_performance_tab(df):
    """Create the Vacancy Performance tab."""
    st.header("📋 Vacancy Performance")

    # Debug info
    st.info(f"📋 Dataset contains {len(df):,} total rows")

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

    # Show filtered row count
    st.info(f"📊 Showing {len(filtered_df):,} rows after filters")

    # Separate clicks and applies
    clicks_df = filtered_df[filtered_df['event_name'] == 'job_visit'].copy() if 'event_name' in filtered_df.columns else filtered_df.copy()
    applies_df = filtered_df[filtered_df['event_name'] == 'job_apply_start'].copy() if 'event_name' in filtered_df.columns else pd.DataFrame()

    # Get unique jobs
    job_col = 'entity_id' if 'entity_id' in filtered_df.columns else filtered_df.columns[0]
    job_details = filtered_df.drop_duplicates(subset=[job_col])

    vacancy_data = []
    for _, job in job_details.iterrows():
        job_id = job[job_col]
        clicks = len(clicks_df[clicks_df[job_col] == job_id])
        applies = len(applies_df[applies_df[job_col] == job_id]) if not applies_df.empty else 0
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
                # Has both start and end date
                days_active = (end_date - start_date).days
            elif is_published:
                # Published but no end date - calculate to today
                today = pd.Timestamp(datetime.now())
                days_active = (today - start_date).days

        # Get occupation from occupational_fields
        occupation = job.get('occupational_fields', 'Unknown')
        if pd.notna(occupation) and str(occupation).strip():
            # Handle pipe-separated occupations, take first one
            occupation = str(occupation).split('|')[0].strip()
        else:
            occupation = 'Unknown'

        # Get upgrades
        upgrades_str = ', '.join(job.get('upgrades_list', [])) if 'upgrades_list' in job else ''

        vacancy_data.append({
            'Title': job.get('title', job.get('organization_name', 'Unknown')),
            'Company': job.get('organization_name', 'Unknown'),
            'Job ID': job_id,
            'Status': status,
            'Start Date': start_date if pd.notna(start_date) else None,
            'End Date': end_date if pd.notna(end_date) else None,
            'Days Active': int(days_active) if days_active is not None and days_active > 0 else None,
            'Region': job.get('uk_region', 'Unknown'),
            'Occupation': occupation,
            'Importer': job.get('importer_name', 'Unknown'),
            'Upgrades': upgrades_str if upgrades_str else 'None',
            'Clicks': int(clicks),
            'Applies': int(applies),
            'Ratio %': round(ratio, 2) if clicks > 0 else None,
            'Clicks/Day': round(clicks / days_active, 2) if days_active and days_active > 0 and is_published else None,
            'Applies/Day': round(applies / days_active, 2) if days_active and days_active > 0 and is_published else None
        })

    vacancy_df = pd.DataFrame(vacancy_data)

    # Check if we have any data
    if len(vacancy_df) == 0:
        st.warning("⚠️ No vacancy data found for the selected filters. Try adjusting your date range or filters.")
        return

    # Calculate occupation averages (within filtered date range)
    occupation_stats = {}
    if 'Occupation' in vacancy_df.columns:
        for occupation in vacancy_df['Occupation'].unique():
            occ_vacancies = vacancy_df[vacancy_df['Occupation'] == occupation]
            occupation_stats[occupation] = {
                'avg_clicks': occ_vacancies['Clicks'].mean(),
                'avg_applies': occ_vacancies['Applies'].mean()
            }

        # Add occupation averages to each row
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
    st.info(f"📋 Dataset contains {len(df):,} total rows")
    st.info("💡 Select filters for each side, then click Apply Filters to compare")

    col_left, col_right = st.columns(2)

    # Left Side
    with col_left:
        st.subheader("📊 Side A")
        with st.expander("🔍 Filters", expanded=True):
            filters_left, apply_left = create_filter_panel(df, 'comp_left')

        if apply_left:
            st.session_state.comp_left_filters = filters_left
            st.rerun()

        # Apply filters
        if 'comp_left_filters' in st.session_state:
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

        if apply_right:
            st.session_state.comp_right_filters = filters_right
            st.rerun()

        # Apply filters
        if 'comp_right_filters' in st.session_state:
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
# MAIN APPLICATION
# ============================================================================

def main():
    st.title("📊 Job Performance Dashboard")

    # Sidebar - Data Loading Controls
    st.sidebar.header("⚙️ Data Loading Settings")

    days_back = st.sidebar.slider(
        "Days to Load",
        min_value=7,
        max_value=90,
        value=30,
        step=7,
        help="Number of days of historical data to load from BigQuery"
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
    df_raw = load_data_from_bigquery(days_back=days_back, sample_size=sample_size)
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
    for tab_prefix in ['overview', 'deepdive', 'vacancy', 'comp_left', 'comp_right']:
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

    st.sidebar.info(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.sidebar.metric("Total Records", f"{len(df):,}")

    if enable_sampling:
        st.sidebar.warning(f"⚠️ Sampling enabled: showing {len(df):,} of all records")

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
                st.write(f"'{name}': {count} records")

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Overview",
        "🔍 Deep Dive",
        "📋 Vacancy Performance",
        "⚖️ Comparison"
    ])

    with tab1:
        create_overview_tab(df)

    with tab2:
        create_deep_dive_tab(df)

    with tab3:
        create_vacancy_performance_tab(df)

    with tab4:
        create_comparison_tab(df)

if __name__ == "__main__":
    main()
