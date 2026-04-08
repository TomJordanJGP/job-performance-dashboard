"""BigQuery data loading and caching functions."""

import os
import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
from google.cloud import bigquery
from datetime import datetime, timedelta

# BigQuery configuration
BQ_PROJECT_ID = "site-monitoring-421401"
BQ_DATASET_ID = "job_data_export"
BQ_TABLE_ID = "dashboard_vacancy_summary"
BQ_DAILY_TOTALS_TABLE_ID = "dashboard_daily_totals"

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/bigquery',
]


@st.cache_resource(ttl=None)
def get_bigquery_client():
    """Initialize and cache the BigQuery client."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # service_account.json is in the project root, one level up from data/
    project_root = os.path.dirname(script_dir)
    service_account_path = os.path.join(project_root, 'service_account.json')

    try:
        use_secrets = False
        try:
            if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
                use_secrets = True
        except Exception:
            use_secrets = False

        if use_secrets:
            creds = Credentials.from_service_account_info(
                st.secrets['gcp_service_account'],
                scopes=SCOPES
            )
        else:
            if not os.path.exists(service_account_path):
                st.error("No authentication found!")
                st.error(f"Local file does not exist at: {service_account_path}")
                st.error("Please either:")
                st.error("1. Add secrets to Streamlit Cloud (Settings > Secrets), OR")
                st.error("2. Add service_account.json file to the app directory")
                st.stop()

            creds = Credentials.from_service_account_file(
                service_account_path,
                scopes=SCOPES
            )

        client = bigquery.Client(credentials=creds, project=BQ_PROJECT_ID)
        return client
    except FileNotFoundError as e:
        st.error(f"Service account credentials not found at: {service_account_path}")
        st.error("Please add them to Streamlit secrets or place service_account.json in the app directory")
        st.stop()
    except Exception as e:
        st.error(f"Unexpected error initializing BigQuery client: {type(e).__name__}")
        st.error(f"Error message: {str(e)}")
        st.stop()


@st.cache_data(ttl=14400)
def load_all_data(days_back=30, sample_size=None):
    """Load vacancy summary and daily totals in a single BigQuery call."""
    try:
        client = get_bigquery_client()
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        limit_clause = f"LIMIT {sample_size}" if sample_size else ""

        # Core fields always present in dashboard_vacancy_summary
        core_fields = """
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
            employment_type"""

        # Salary fields (added after running updated create_aggregated_tables.sql)
        salary_fields = """,
            min_salary,
            max_salary,
            currency_code,
            salary_free_text,
            salary_exact,
            salary_unit"""

        vacancy_query = f"""
        SELECT {core_fields}{salary_fields}
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

        # Try with salary fields; fall back to core-only if table not yet updated
        try:
            vacancy_job = client.query(vacancy_query)
            vacancy_job.result()
        except Exception:
            vacancy_query = f"""
            SELECT {core_fields}
            FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.{BQ_TABLE_ID}`
            WHERE last_event_date >= '{cutoff_date}'
            {limit_clause}
            """
            vacancy_job = client.query(vacancy_query)
            vacancy_job.result()

        daily_job = client.query(daily_query)
        daily_job.result()

        vacancy_df = vacancy_job.to_dataframe(create_bqstorage_client=False)
        daily_df = daily_job.to_dataframe(create_bqstorage_client=False)

        return vacancy_df, daily_df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
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
        # Look for CSV in project root
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        csv_path = os.path.join(project_root, 'importer_mapping.csv')

        mapping_df = pd.read_csv(csv_path, encoding='utf-8-sig')
        if 'importer_id' in mapping_df.columns and 'importer_name' in mapping_df.columns:
            mapping_df = mapping_df[mapping_df['importer_id'].notna()]
            mapping_df = mapping_df[mapping_df['importer_id'].astype(str).str.strip() != '']
            importer_mapping = dict(zip(
                mapping_df['importer_id'].astype(str).str.strip(),
                mapping_df['importer_name'].str.strip()
            ))
            return importer_mapping
        return {}
    except Exception as e:
        st.error(f"Error loading importer mapping: {e}")
        return {}
