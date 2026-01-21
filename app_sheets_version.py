import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io

# Page configuration
st.set_page_config(
    page_title="Job Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
SPREADSHEET_ID = "1XvVxCV8oo-qwZOwdHfsqMTIljHQ1gHISfZoIvVI8i7U"
DATA_SHEET_NAME = "job_data_copy"  # Regular sheet copy created by Apps Script
MAPPING_SHEET_NAME = "importer_mapping"

# Google Sheets API scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
]

@st.cache_resource
def get_google_sheets_client():
    """Initialize and cache the Google Sheets client."""
    try:
        # Try to load service account credentials
        creds = Credentials.from_service_account_file(
            'service_account.json',
            scopes=SCOPES
        )
        client = gspread.authorize(creds)
        return client
    except FileNotFoundError:
        st.error("⚠️ Service account credentials not found. Please add 'service_account.json' to the project directory.")
        st.info("See README.md for setup instructions.")
        st.stop()
    except Exception as e:
        st.error(f"Error initializing Google Sheets client: {str(e)}")
        st.stop()

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    """Load data from Google Sheets."""
    try:
        client = get_google_sheets_client()

        # Try to open the spreadsheet
        try:
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
        except Exception as e:
            st.error(f"❌ Error opening spreadsheet: {str(e)}")
            st.error("**Possible causes:**")
            st.error("- The service account email doesn't have access to the sheet")
            st.error("- The spreadsheet ID is incorrect")
            st.error("- The Google Sheets API is not enabled")
            st.info(f"Spreadsheet ID: {SPREADSHEET_ID}")
            st.stop()

        # Load main data
        try:
            st.info(f"Loading sheet: '{DATA_SHEET_NAME}'...")
            data_sheet = spreadsheet.worksheet(DATA_SHEET_NAME)

            # Get all values (works better with BigQuery connected sheets)
            all_values = data_sheet.get_all_values()

            if len(all_values) > 0:
                # First row is headers
                headers = all_values[0]
                # Rest are data rows
                data_rows = all_values[1:]
                df = pd.DataFrame(data_rows, columns=headers)
                st.success(f"✅ Loaded {len(df)} rows from main data sheet")
            else:
                st.error("The sheet appears to be empty")
                st.stop()
        except Exception as e:
            st.error(f"❌ Error loading main data sheet '{DATA_SHEET_NAME}': {str(e)}")
            st.error("**Possible causes:**")
            st.error(f"- Sheet name '{DATA_SHEET_NAME}' doesn't exist in the spreadsheet")
            st.error("- Check the exact sheet tab name (case-sensitive)")

            # Try to list available sheets
            try:
                available_sheets = [ws.title for ws in spreadsheet.worksheets()]
                st.info(f"Available sheets in this spreadsheet: {', '.join(available_sheets)}")
            except:
                pass
            st.stop()

        # Load importer mapping
        try:
            st.info(f"Loading sheet: '{MAPPING_SHEET_NAME}'...")
            mapping_sheet = spreadsheet.worksheet(MAPPING_SHEET_NAME)

            # Get all values
            mapping_values = mapping_sheet.get_all_values()

            if len(mapping_values) > 0:
                mapping_headers = mapping_values[0]
                mapping_rows = mapping_values[1:]
                mapping_df = pd.DataFrame(mapping_rows, columns=mapping_headers)

                # Create mapping dictionary
                if not mapping_df.empty and 'importer_id' in mapping_df.columns and 'importer_name' in mapping_df.columns:
                    # Filter out empty rows
                    mapping_df = mapping_df[mapping_df['importer_id'].str.strip() != '']
                    importer_mapping = dict(zip(mapping_df['importer_id'].astype(str), mapping_df['importer_name']))
                    st.success(f"✅ Loaded {len(importer_mapping)} importer mappings")
                else:
                    st.warning(f"⚠️ Importer mapping sheet found but columns 'importer_id' or 'importer_name' are missing")
                    importer_mapping = {}
            else:
                st.warning("⚠️ Importer mapping sheet is empty")
                importer_mapping = {}
        except Exception as e:
            st.warning(f"⚠️ Could not load importer mapping sheet '{MAPPING_SHEET_NAME}': {str(e)}")
            st.info("The dashboard will work without importer name mapping.")
            importer_mapping = {}

        return df, importer_mapping
    except Exception as e:
        st.error(f"❌ Unexpected error loading data: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        st.stop()

def apply_importer_mapping(df, mapping):
    """Apply importer ID to name mapping."""
    if mapping and 'importer_id' in df.columns:
        df['importer_name'] = df['importer_id'].astype(str).map(mapping)
        # Fill unmapped IDs with the original ID
        df['importer_name'] = df['importer_name'].fillna(df['importer_id'].astype(str))
    else:
        df['importer_name'] = df['importer_id'].astype(str) if 'importer_id' in df.columns else 'Unknown'
    return df

def parse_date_column(df, date_col='event_data'):
    """Parse date column from YYYYMMDD format to datetime."""
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col].astype(str), format='%Y%m%d', errors='coerce')
    return df

def create_metrics_cards(df):
    """Create metric cards for dashboard."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Records", f"{len(df):,}")

    with col2:
        unique_orgs = df['organization_name'].nunique() if 'organization_name' in df.columns else 0
        st.metric("Unique Organizations", f"{unique_orgs:,}")

    with col3:
        unique_jobs = df['occupation'].nunique() if 'occupation' in df.columns else 0
        st.metric("Unique Occupations", f"{unique_jobs:,}")

    with col4:
        unique_regions = df['regions'].nunique() if 'regions' in df.columns else 0
        st.metric("Unique Regions", f"{unique_regions:,}")

def create_visualizations(df):
    """Create data visualizations."""

    # Top 10 Occupations
    if 'occupation' in df.columns:
        st.subheader("Top 10 Occupations")
        occupation_counts = df['occupation'].value_counts().head(10)
        fig_occupation = px.bar(
            x=occupation_counts.values,
            y=occupation_counts.index,
            orientation='h',
            labels={'x': 'Count', 'y': 'Occupation'},
            title="Most Common Occupations"
        )
        fig_occupation.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_occupation, use_container_width=True)

    # Event distribution over time
    if 'event_data' in df.columns and pd.api.types.is_datetime64_any_dtype(df['event_data']):
        st.subheader("Events Over Time")
        df_sorted = df.sort_values('event_data')
        daily_counts = df_sorted.groupby(df_sorted['event_data'].dt.date).size().reset_index()
        daily_counts.columns = ['Date', 'Count']

        fig_timeline = px.line(
            daily_counts,
            x='Date',
            y='Count',
            title="Daily Event Count",
            labels={'Count': 'Number of Events', 'Date': 'Date'}
        )
        st.plotly_chart(fig_timeline, use_container_width=True)

    # Top regions and importers in columns
    col1, col2 = st.columns(2)

    with col1:
        if 'regions' in df.columns:
            st.subheader("Top 10 Regions")
            region_counts = df['regions'].value_counts().head(10)
            fig_regions = px.pie(
                values=region_counts.values,
                names=region_counts.index,
                title="Distribution by Region"
            )
            st.plotly_chart(fig_regions, use_container_width=True)

    with col2:
        if 'importer_name' in df.columns:
            st.subheader("Top 10 Importers")
            importer_counts = df['importer_name'].value_counts().head(10)
            fig_importers = px.pie(
                values=importer_counts.values,
                names=importer_counts.index,
                title="Distribution by Importer"
            )
            st.plotly_chart(fig_importers, use_container_width=True)

def main():
    st.title("📊 Job Performance Dashboard")
    st.markdown("---")

    # Load data
    with st.spinner("Loading data from Google Sheets..."):
        df_raw, importer_mapping = load_data()
        df = df_raw.copy()
        df = apply_importer_mapping(df, importer_mapping)
        df = parse_date_column(df)

    # Sidebar filters
    st.sidebar.header("Filters")

    # Date range filter
    if 'event_data' in df.columns and pd.api.types.is_datetime64_any_dtype(df['event_data']):
        min_date = df['event_data'].min().date()
        max_date = df['event_data'].max().date()

        date_range = st.sidebar.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

        if len(date_range) == 2:
            df = df[(df['event_data'].dt.date >= date_range[0]) &
                   (df['event_data'].dt.date <= date_range[1])]

    # Occupation filter
    if 'occupation' in df.columns:
        occupations = sorted(df['occupation'].dropna().unique())
        selected_occupations = st.sidebar.multiselect(
            "Occupation",
            options=occupations,
            default=[]
        )
        if selected_occupations:
            df = df[df['occupation'].isin(selected_occupations)]

    # Region filter
    if 'regions' in df.columns:
        regions = sorted(df['regions'].dropna().unique())
        selected_regions = st.sidebar.multiselect(
            "Region",
            options=regions,
            default=[]
        )
        if selected_regions:
            df = df[df['regions'].isin(selected_regions)]

    # Organization filter
    if 'organization_name' in df.columns:
        organizations = sorted(df['organization_name'].dropna().unique())
        selected_orgs = st.sidebar.multiselect(
            "Organization",
            options=organizations,
            default=[]
        )
        if selected_orgs:
            df = df[df['organization_name'].isin(selected_orgs)]

    # Importer filter
    if 'importer_name' in df.columns:
        importers = sorted(df['importer_name'].dropna().unique())
        selected_importers = st.sidebar.multiselect(
            "Importer",
            options=importers,
            default=[]
        )
        if selected_importers:
            df = df[df['importer_name'].isin(selected_importers)]

    # Event name filter
    if 'event_name' in df.columns:
        event_names = sorted(df['event_name'].dropna().unique())
        selected_events = st.sidebar.multiselect(
            "Event Name",
            options=event_names,
            default=[]
        )
        if selected_events:
            df = df[df['event_name'].isin(selected_events)]

    # Reset filters button
    if st.sidebar.button("Reset All Filters"):
        st.rerun()

    # Refresh data button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.info(f"**Last updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Main content
    if len(df) == 0:
        st.warning("No data matches the selected filters.")
        return

    # Metrics
    create_metrics_cards(df)

    st.markdown("---")

    # Visualizations
    create_visualizations(df)

    st.markdown("---")

    # Data table
    st.subheader("Filtered Data")

    # Column selector
    all_columns = df.columns.tolist()
    default_columns = ['event_data', 'event_name', 'organization_name', 'occupation',
                      'regions', 'importer_name']
    # Only include default columns that exist in the dataframe
    default_columns = [col for col in default_columns if col in all_columns]

    selected_columns = st.multiselect(
        "Select columns to display",
        options=all_columns,
        default=default_columns
    )

    if selected_columns:
        display_df = df[selected_columns]
    else:
        display_df = df

    st.dataframe(display_df, use_container_width=True, height=400)

    # Export functionality
    st.subheader("Export Data")

    col1, col2 = st.columns(2)

    with col1:
        # Export to CSV
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"job_performance_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    with col2:
        # Export to Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            display_df.to_excel(writer, index=False, sheet_name='Job Performance Data')

        st.download_button(
            label="📥 Download as Excel",
            data=buffer.getvalue(),
            file_name=f"job_performance_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == "__main__":
    main()
