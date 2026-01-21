"""
Vacancy View - Streamlit page for vacancy-level reporting
"""

import streamlit as st
import pandas as pd
from utils.region_parser import extract_region_from_address

def create_vacancy_view(df):
    """
    Create vacancy-level view with aggregated metrics.

    Expected DataFrame columns:
    - title (or job title column)
    - organization_name
    - entity_id (job ID)
    - regions (location/address)
    - event_name (to identify clicks vs applies)
    - event_data (date)

    And optionally from Jobiqo export:
    - start_date
    - end_date
    """

    st.header("📋 Vacancy View")

    # Filter for relevant events
    click_events = df[df['event_name'] == 'job_visit'].copy() if 'event_name' in df.columns else df.copy()
    apply_events = df[df['event_name'] == 'job_apply_start'].copy() if 'event_name' in df.columns else pd.DataFrame()

    # Group by vacancy
    vacancy_metrics = []

    # Get unique job IDs
    job_id_col = 'entity_id' if 'entity_id' in df.columns else df.columns[0]
    title_col = 'title' if 'title' in df.columns else 'organization_name'
    org_col = 'organization_name' if 'organization_name' in df.columns else 'entity_name'
    location_col = 'regions' if 'regions' in df.columns else None

    unique_jobs = df[job_id_col].unique()

    for job_id in unique_jobs:
        job_data = df[df[job_id_col] == job_id].iloc[0]

        # Count clicks and applies
        clicks = len(click_events[click_events[job_id_col] == job_id])
        applies = len(apply_events[apply_events[job_id_col] == job_id]) if not apply_events.empty else 0

        # Calculate ratio
        apply_click_ratio = (applies / clicks * 100) if clicks > 0 else 0

        # Extract region from address
        location = job_data.get(location_col, 'Unknown') if location_col else 'Unknown'
        region = extract_region_from_address(location) if location_col else 'Unknown'

        vacancy_metrics.append({
            'Title': job_data.get(title_col, 'Unknown'),
            'Organisation': job_data.get(org_col, 'Unknown'),
            'Job ID': job_id,
            'Start Date': job_data.get('start_date', 'N/A'),
            'End Date': job_data.get('end_date', 'N/A'),
            'Location (Region)': region,
            'Total Clicks': clicks,
            'Total Apply Start': applies,
            'Apply Click Ratio (%)': round(apply_click_ratio, 2)
        })

    # Create DataFrame
    vacancy_df = pd.DataFrame(vacancy_metrics)

    # Sort by clicks (descending)
    vacancy_df = vacancy_df.sort_values('Total Clicks', ascending=False)

    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Vacancies", len(vacancy_df))
    with col2:
        st.metric("Total Clicks", vacancy_df['Total Clicks'].sum())
    with col3:
        st.metric("Total Applies", vacancy_df['Total Apply Start'].sum())
    with col4:
        avg_ratio = vacancy_df['Apply Click Ratio (%)'].mean()
        st.metric("Avg Apply Rate", f"{avg_ratio:.2f}%")

    # Filters
    st.subheader("Filters")
    col1, col2 = st.columns(2)

    with col1:
        selected_regions = st.multiselect(
            "Filter by Region",
            options=sorted(vacancy_df['Location (Region)'].unique()),
            default=[]
        )

    with col2:
        selected_orgs = st.multiselect(
            "Filter by Organisation",
            options=sorted(vacancy_df['Organisation'].unique()),
            default=[]
        )

    # Apply filters
    filtered_df = vacancy_df.copy()
    if selected_regions:
        filtered_df = filtered_df[filtered_df['Location (Region)'].isin(selected_regions)]
    if selected_orgs:
        filtered_df = filtered_df[filtered_df['Organisation'].isin(selected_orgs)]

    # Display table
    st.subheader(f"Vacancy Data ({len(filtered_df)} vacancies)")

    # Make columns sortable
    st.dataframe(
        filtered_df,
        use_container_width=True,
        height=600,
        column_config={
            "Apply Click Ratio (%)": st.column_config.ProgressColumn(
                "Apply Click Ratio (%)",
                help="Percentage of clicks that resulted in apply starts",
                format="%.2f%%",
                min_value=0,
                max_value=100,
            ),
        }
    )

    # Export
    st.subheader("Export")
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Vacancy Report as CSV",
        data=csv,
        file_name=f"vacancy_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

    return filtered_df
