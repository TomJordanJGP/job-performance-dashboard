import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from google.cloud import bigquery
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import sys
sys.path.append('.')
from utils.region_parser import extract_region_from_address

# Page configuration
st.set_page_config(
    page_title="Job Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
SPREADSHEET_ID = "1XvVxCV8oo-qwZOwdHfsqMTIljHQ1gHISfZoIvVI8i7U"
MAPPING_SHEET_NAME = "importer_mapping"
JOBIQO_SHEET_NAME = "jobiqo_export"  # New sheet for Jobiqo daily export

# BigQuery configuration
BQ_PROJECT_ID = "site-monitoring-421401"
BQ_DATASET_ID = "job_data_export"
BQ_TABLE_ID = "job_performance_details_combined"

# Google Sheets API scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/bigquery',
]

@st.cache_resource
def get_bigquery_client():
    """Initialize and cache the BigQuery client."""
    try:
        creds = Credentials.from_service_account_file(
            'service_account.json',
            scopes=SCOPES
        )
        client = bigquery.Client(credentials=creds, project=BQ_PROJECT_ID)
        return client
    except FileNotFoundError:
        st.error("⚠️ Service account credentials not found.")
        st.stop()
    except Exception as e:
        st.error(f"Error initializing BigQuery client: {str(e)}")
        st.stop()

@st.cache_resource
def get_google_sheets_client():
    """Initialize and cache the Google Sheets client."""
    try:
        creds = Credentials.from_service_account_file(
            'service_account.json',
            scopes=SCOPES
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Error initializing Google Sheets client: {str(e)}")
        st.stop()

@st.cache_data(ttl=3600)  # Cache for 1 hour instead of 5 minutes
def load_data_from_bigquery(days_back=90):
    """Load data from BigQuery with date filter for better performance."""
    try:
        client = get_bigquery_client()

        # Calculate date filter for recent data only
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')

        # Query only recent data for much faster loading
        query = f"""
        SELECT *
        FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.{BQ_TABLE_ID}`
        WHERE event_date >= '{cutoff_date}'
        ORDER BY event_date DESC
        """

        st.info(f"📊 Querying BigQuery (last {days_back} days)...")
        query_job = client.query(query)
        # Disable BigQuery Storage API to avoid permission issues
        df = query_job.to_dataframe(create_bqstorage_client=False)

        st.success(f"✅ Loaded {len(df):,} rows from BigQuery")
        return df
    except Exception as e:
        st.error(f"❌ Error loading data from BigQuery: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        st.stop()

@st.cache_data(ttl=300)
def load_importer_mapping():
    """Load importer mapping from CSV file."""
    try:
        st.info(f"Loading importer mapping from CSV...")
        # Use encoding='utf-8-sig' to handle BOM characters
        mapping_df = pd.read_csv('importer_mapping.csv', encoding='utf-8-sig')

        if 'importer_id' in mapping_df.columns and 'importer_name' in mapping_df.columns:
            # Filter out empty rows
            mapping_df = mapping_df[mapping_df['importer_id'].notna()]
            mapping_df = mapping_df[mapping_df['importer_id'].astype(str).str.strip() != '']

            importer_mapping = dict(zip(mapping_df['importer_id'].astype(str), mapping_df['importer_name']))
            st.success(f"✅ Loaded {len(importer_mapping)} importer mappings")
            return importer_mapping

        st.warning("⚠️ importer_mapping.csv missing required columns")
        return {}
    except FileNotFoundError:
        st.warning(f"⚠️ importer_mapping.csv not found. Importer IDs will be shown as numbers.")
        return {}
    except Exception as e:
        st.warning(f"⚠️ Could not load importer mapping: {str(e)}")
        return {}

@st.cache_data(ttl=300)
def load_jobiqo_export():
    """Load Jobiqo export data from CSV file."""
    try:
        st.info(f"Loading Jobiqo export data from CSV...")
        jobiqo_df = pd.read_csv('jobs-export.csv')
        st.success(f"✅ Loaded {len(jobiqo_df)} Jobiqo records from jobs-export.csv")
        return jobiqo_df
    except FileNotFoundError:
        st.warning(f"⚠️ jobs-export.csv not found. Vacancy view will not have start/end dates.")
        return pd.DataFrame()
    except Exception as e:
        st.warning(f"⚠️ Could not load Jobiqo export: {str(e)}")
        return pd.DataFrame()

def apply_importer_mapping(df, mapping):
    """Apply importer ID to name mapping."""
    if 'importer_id' not in df.columns:
        df['importer_name'] = 'Unknown'
        return df

    # Convert importer_id to string for mapping
    df['importer_id_str'] = df['importer_id'].astype(str).str.strip()

    if mapping:
        # Apply mapping
        df['importer_name'] = df['importer_id_str'].map(mapping)
        # For unmapped values, show the ID
        df['importer_name'] = df['importer_name'].fillna('ID: ' + df['importer_id_str'])
        st.info(f"✅ Applied mapping to {len(df[df['importer_name'].isin(mapping.values())])} rows")
    else:
        # No mapping available, show IDs
        df['importer_name'] = 'ID: ' + df['importer_id_str']

    return df

def merge_jobiqo_data(df, jobiqo_df):
    """Merge Jobiqo export data with main data."""
    if jobiqo_df.empty:
        return df

    # Jobiqo CSV has 'job_id', BigQuery has 'entity_id'
    # Rename job_id to entity_id for easier joining
    if 'job_id' in jobiqo_df.columns:
        jobiqo_df = jobiqo_df.rename(columns={'job_id': 'entity_id'})

    join_key = 'entity_id'

    if join_key in df.columns and join_key in jobiqo_df.columns:
        # Select key columns from Jobiqo export
        jobiqo_subset = jobiqo_df[[
            'entity_id', 'title', 'publishing_date', 'expiration_date',
            'organization_profile_name', 'locations'
        ]].copy()

        # Rename for clarity
        jobiqo_subset = jobiqo_subset.rename(columns={
            'publishing_date': 'start_date',
            'expiration_date': 'end_date',
            'organization_profile_name': 'organization_name_jobiqo',
            'locations': 'location_full'
        })

        df = df.merge(jobiqo_subset, on=join_key, how='left', suffixes=('', '_from_jobiqo'))

    return df

def parse_date_column(df, date_col='event_date'):
    """Parse date column."""
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col].astype(str), format='%Y%m%d', errors='coerce')
    return df

def add_uk_regions(df):
    """Add UK region column based on address from Jobiqo locations."""
    def parse_location(location):
        """Parse location string which may contain multiple locations separated by |"""
        if not location or pd.isna(location):
            return 'Unknown'

        # Split by | if multiple locations
        locations = str(location).split('|')

        # Try to extract region from each location
        regions = []
        for loc in locations:
            region = extract_region_from_address(loc.strip())
            if region != 'Unknown':
                regions.append(region)

        # Return first valid region found, or combine if multiple unique regions
        if regions:
            unique_regions = list(set(regions))
            if len(unique_regions) == 1:
                return unique_regions[0]
            else:
                # Multiple regions - return first or combine
                return unique_regions[0]  # Could also return: ' / '.join(unique_regions[:2])

        return 'Unknown'

    # Use location_full from Jobiqo if available, otherwise fall back to regions column
    if 'location_full' in df.columns:
        df['uk_region'] = df['location_full'].apply(parse_location)
    elif 'regions' in df.columns:
        df['uk_region'] = df['regions'].apply(extract_region_from_address)
    else:
        df['uk_region'] = 'Unknown'

    return df

def create_vacancy_view(df):
    """Create vacancy-level view."""
    st.header("📋 Vacancy View")

    # Separate clicks and applies
    clicks_df = df[df['event_name'] == 'job_visit'].copy() if 'event_name' in df.columns else df.copy()
    applies_df = df[df['event_name'] == 'job_apply_start'].copy() if 'event_name' in df.columns else pd.DataFrame()

    # Aggregate by job
    job_col = 'entity_id' if 'entity_id' in df.columns else df.columns[0]

    # Get unique jobs with their details
    job_details = df.drop_duplicates(subset=[job_col])

    vacancy_data = []
    for _, job in job_details.iterrows():
        job_id = job[job_col]

        clicks = len(clicks_df[clicks_df[job_col] == job_id])
        applies = len(applies_df[applies_df[job_col] == job_id]) if not applies_df.empty else 0
        ratio = (applies / clicks * 100) if clicks > 0 else 0

        vacancy_data.append({
            'Title': job.get('title', job.get('organization_name', 'Unknown')),
            'Organisation': job.get('organization_name', 'Unknown'),
            'Job ID': job_id,
            'Start Date': job.get('start_date', 'N/A'),
            'End Date': job.get('end_date', 'N/A'),
            'Location (Region)': job.get('uk_region', 'Unknown'),
            'Total Clicks': clicks,
            'Total Apply Start': applies,
            'Apply Click Ratio (%)': round(ratio, 2)
        })

    vacancy_df = pd.DataFrame(vacancy_data)
    vacancy_df = vacancy_df.sort_values('Total Clicks', ascending=False)

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Vacancies", len(vacancy_df))
    with col2:
        st.metric("Total Clicks", f"{vacancy_df['Total Clicks'].sum():,}")
    with col3:
        st.metric("Total Applies", f"{vacancy_df['Total Apply Start'].sum():,}")
    with col4:
        avg_ratio = vacancy_df['Apply Click Ratio (%)'].mean()
        st.metric("Avg Apply Rate", f"{avg_ratio:.2f}%")

    # Filters
    st.subheader("Filters")
    col1, col2 = st.columns(2)

    with col1:
        regions = sorted(vacancy_df['Location (Region)'].unique())
        selected_regions = st.multiselect("Region", regions, key='vacancy_region')

    with col2:
        orgs = sorted(vacancy_df['Organisation'].unique())
        selected_orgs = st.multiselect("Organisation", orgs, key='vacancy_org')

    # Apply filters
    filtered_df = vacancy_df.copy()
    if selected_regions:
        filtered_df = filtered_df[filtered_df['Location (Region)'].isin(selected_regions)]
    if selected_orgs:
        filtered_df = filtered_df[filtered_df['Organisation'].isin(selected_orgs)]

    # Display
    st.subheader(f"Vacancy Data ({len(filtered_df)} vacancies)")
    st.dataframe(filtered_df, width='stretch', height=600)

    # Export
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Download Vacancy Report",
        csv,
        f"vacancy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        "text/csv"
    )

def create_comparison_view(df):
    """Create side-by-side comparison view."""
    st.header("⚖️ Comparison View")
    st.info("💡 Select your filters below, then click 'Apply Filters' to update the metrics")

    # Initialize session state for applied filters
    if 'applied_filters_left' not in st.session_state:
        st.session_state.applied_filters_left = None
    if 'applied_filters_right' not in st.session_state:
        st.session_state.applied_filters_right = None

    # Create two columns for side-by-side comparison
    col_left, col_right = st.columns(2)

    # Helper function to apply filters
    def apply_filters(data, date_range, importer, company, region):
        filtered = data.copy()

        # Date filter
        if date_range and len(date_range) == 2 and 'event_date' in filtered.columns:
            if pd.api.types.is_datetime64_any_dtype(filtered['event_date']):
                filtered = filtered[(filtered['event_date'].dt.date >= date_range[0]) &
                                  (filtered['event_date'].dt.date <= date_range[1])]

        # Importer filter
        if importer and 'importer_name' in filtered.columns:
            filtered = filtered[filtered['importer_name'].isin(importer)]

        # Company filter
        if company and 'organization_name' in filtered.columns:
            filtered = filtered[filtered['organization_name'].isin(company)]

        # Region filter
        if region and 'uk_region' in filtered.columns:
            filtered = filtered[filtered['uk_region'].isin(region)]

        return filtered

    # Helper function to calculate metrics
    def calculate_metrics(data):
        entity_col = 'entity_id' if 'entity_id' in data.columns else data.columns[0]

        # Number of unique vacancies
        num_vacancies = data[entity_col].nunique()

        # Total clicks (job_visit events)
        if 'event_name' in data.columns:
            total_clicks = len(data[data['event_name'] == 'job_visit'])
            total_applies = len(data[data['event_name'] == 'job_apply_start'])
        else:
            total_clicks = len(data)
            total_applies = 0

        return num_vacancies, total_clicks, total_applies

    # Left side filters
    with col_left:
        st.subheader("📊 Side A")

        with st.expander("Filters", expanded=True):
            # Date filter
            left_date = None
            if 'event_date' in df.columns and pd.api.types.is_datetime64_any_dtype(df['event_date']):
                min_date = df['event_date'].min().date()
                max_date = df['event_date'].max().date()
                left_date = st.date_input("Date Range", [min_date, max_date],
                                         key='left_date', min_value=min_date, max_value=max_date)

            # Importer filter
            left_importer = []
            if 'importer_name' in df.columns:
                importers = sorted(df['importer_name'].unique())
                left_importer = st.multiselect("Importer", importers, key='left_importer')

            # Company filter
            left_company = []
            if 'organization_name' in df.columns:
                companies = sorted(df['organization_name'].unique())
                left_company = st.multiselect("Company", companies, key='left_company')

            # Region filter
            left_region = []
            if 'uk_region' in df.columns:
                regions = sorted(df['uk_region'].unique())
                left_region = st.multiselect("Region", regions, key='left_region')

            st.markdown("---")

            # Apply button
            if st.button("🔄 Apply Filters", key='left_apply', width='stretch', type="primary"):
                st.session_state.applied_filters_left = {
                    'date': left_date,
                    'importer': left_importer,
                    'company': left_company,
                    'region': left_region
                }
                st.rerun()

        # Use applied filters or show default (all data)
        if st.session_state.applied_filters_left:
            filters = st.session_state.applied_filters_left
            left_filtered = apply_filters(df, filters.get('date'), filters.get('importer'),
                                        filters.get('company'), filters.get('region'))
        else:
            # Default: show all data
            left_filtered = df.copy()

        # Calculate metrics
        left_vacancies, left_clicks, left_applies = calculate_metrics(left_filtered)

        # Display metrics
        st.markdown("### Totals")
        st.metric("Number of Vacancies", f"{left_vacancies:,}")
        st.metric("Total Clicks", f"{left_clicks:,}")
        st.metric("Total Apply Start", f"{left_applies:,}")

        # Additional info
        if left_clicks > 0:
            apply_rate = (left_applies / left_clicks * 100)
            st.metric("Apply Click Ratio", f"{apply_rate:.2f}%")

    # Right side filters
    with col_right:
        st.subheader("📊 Side B")

        with st.expander("Filters", expanded=True):
            # Date filter
            right_date = None
            if 'event_date' in df.columns and pd.api.types.is_datetime64_any_dtype(df['event_date']):
                min_date = df['event_date'].min().date()
                max_date = df['event_date'].max().date()
                right_date = st.date_input("Date Range", [min_date, max_date],
                                          key='right_date', min_value=min_date, max_value=max_date)

            # Importer filter
            right_importer = []
            if 'importer_name' in df.columns:
                importers = sorted(df['importer_name'].unique())
                right_importer = st.multiselect("Importer", importers, key='right_importer')

            # Company filter
            right_company = []
            if 'organization_name' in df.columns:
                companies = sorted(df['organization_name'].unique())
                right_company = st.multiselect("Company", companies, key='right_company')

            # Region filter
            right_region = []
            if 'uk_region' in df.columns:
                regions = sorted(df['uk_region'].unique())
                right_region = st.multiselect("Region", regions, key='right_region')

            st.markdown("---")

            # Apply button
            if st.button("🔄 Apply Filters", key='right_apply', width='stretch', type="primary"):
                st.session_state.applied_filters_right = {
                    'date': right_date,
                    'importer': right_importer,
                    'company': right_company,
                    'region': right_region
                }
                st.rerun()

        # Use applied filters or show default (all data)
        if st.session_state.applied_filters_right:
            filters = st.session_state.applied_filters_right
            right_filtered = apply_filters(df, filters.get('date'), filters.get('importer'),
                                         filters.get('company'), filters.get('region'))
        else:
            # Default: show all data
            right_filtered = df.copy()

        # Calculate metrics
        right_vacancies, right_clicks, right_applies = calculate_metrics(right_filtered)

        # Display metrics
        st.markdown("### Totals")
        st.metric("Number of Vacancies", f"{right_vacancies:,}")
        st.metric("Total Clicks", f"{right_clicks:,}")
        st.metric("Total Apply Start", f"{right_applies:,}")

        # Additional info
        if right_clicks > 0:
            apply_rate = (right_applies / right_clicks * 100)
            st.metric("Apply Click Ratio", f"{apply_rate:.2f}%")

    # Comparison summary
    st.markdown("---")
    st.subheader("📈 Comparison Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Vacancies**")
        diff = right_vacancies - left_vacancies
        pct = ((right_vacancies / left_vacancies - 1) * 100) if left_vacancies > 0 else 0
        st.markdown(f"Side A: {left_vacancies:,}")
        st.markdown(f"Side B: {right_vacancies:,}")
        st.markdown(f"Difference: {diff:+,} ({pct:+.1f}%)")

    with col2:
        st.markdown("**Clicks**")
        diff = right_clicks - left_clicks
        pct = ((right_clicks / left_clicks - 1) * 100) if left_clicks > 0 else 0
        st.markdown(f"Side A: {left_clicks:,}")
        st.markdown(f"Side B: {right_clicks:,}")
        st.markdown(f"Difference: {diff:+,} ({pct:+.1f}%)")

    with col3:
        st.markdown("**Applies**")
        diff = right_applies - left_applies
        pct = ((right_applies / left_applies - 1) * 100) if left_applies > 0 else 0
        st.markdown(f"Side A: {left_applies:,}")
        st.markdown(f"Side B: {right_applies:,}")
        st.markdown(f"Difference: {diff:+,} ({pct:+.1f}%)")

def create_overview_dashboard(df):
    """Create overview dashboard."""
    st.header("📊 Overview Dashboard")

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Records", f"{len(df):,}")
    with col2:
        if 'organization_name' in df.columns:
            st.metric("Unique Organizations", f"{df['organization_name'].nunique():,}")
    with col3:
        if 'occupation' in df.columns:
            st.metric("Unique Occupations", f"{df['occupation'].nunique():,}")
    with col4:
        if 'uk_region' in df.columns:
            st.metric("UK Regions", f"{df['uk_region'].nunique():,}")

    st.markdown("---")

    # Visualizations
    col1, col2 = st.columns(2)

    with col1:
        if 'occupation' in df.columns:
            st.subheader("Top 10 Occupations")
            occ_counts = df['occupation'].value_counts().head(10)
            fig = px.bar(x=occ_counts.values, y=occ_counts.index, orientation='h')
            fig.update_layout(showlegend=False, height=400, xaxis_title="Count", yaxis_title="Occupation")
            st.plotly_chart(fig, width='stretch')

    with col2:
        if 'uk_region' in df.columns:
            st.subheader("Distribution by UK Region")
            region_counts = df['uk_region'].value_counts()
            fig = px.pie(values=region_counts.values, names=region_counts.index)
            st.plotly_chart(fig, width='stretch')

    # Timeline
    if 'event_date' in df.columns and pd.api.types.is_datetime64_any_dtype(df['event_date']):
        st.subheader("Events Over Time")
        daily = df.groupby(df['event_date'].dt.date).size().reset_index()
        daily.columns = ['Date', 'Count']
        fig = px.line(daily, x='Date', y='Count')
        st.plotly_chart(fig, width='stretch')

def main():
    st.title("📊 Job Performance Dashboard")

    # Load data
    with st.spinner("Loading data..."):
        df_raw = load_data_from_bigquery()
        importer_mapping = load_importer_mapping()
        jobiqo_df = load_jobiqo_export()

        df = df_raw.copy()
        df = apply_importer_mapping(df, importer_mapping)
        df = parse_date_column(df)
        df = add_uk_regions(df)
        df = merge_jobiqo_data(df, jobiqo_df)

    # Sidebar filters
    st.sidebar.header("Global Filters")

    # Date filter
    if 'event_date' in df.columns and pd.api.types.is_datetime64_any_dtype(df['event_date']):
        min_date = df['event_date'].min().date()
        max_date = df['event_date'].max().date()
        date_range = st.sidebar.date_input("Date Range", [min_date, max_date], min_value=min_date, max_value=max_date)

        if len(date_range) == 2:
            df = df[(df['event_date'].dt.date >= date_range[0]) & (df['event_date'].dt.date <= date_range[1])]

    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.info(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Overview", "📋 Vacancy View", "⚖️ Comparison"])

    with tab1:
        create_overview_dashboard(df)

    with tab2:
        create_vacancy_view(df)

    with tab3:
        create_comparison_view(df)

if __name__ == "__main__":
    main()
