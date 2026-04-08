"""JGP Job Performance Dashboard - Branded UI version."""

import streamlit as st
from datetime import datetime

# Page configuration (must be first Streamlit command)
st.set_page_config(
    page_title="JGP Job Performance Dashboard",
    page_icon="\U0001F4CA",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject branded CSS
from theme.css import inject_css
inject_css()

# Import modules
from theme.components import sidebar_logo, main_logo
from data.loader import load_all_data, load_importer_mapping
from data.processing import (
    prepare_enriched_data,
    apply_importer_mapping,
    parse_upgrades,
    parse_dates_in_jobiqo,
    add_occupation_column,
    process_salary_columns,
)
from data.filters import create_sidebar_filters
from views.dashboard import render_dashboard
from views.performance import render_performance
from views.compare import render_compare
from views.salary import render_salary


def main():
    # === SIDEBAR ===
    with st.sidebar:
        # JGP Logo
        st.markdown(sidebar_logo(), unsafe_allow_html=True)

    # === DATA LOADING (fixed 365 days, no data settings exposed) ===
    with st.spinner("Loading data..."):
        df_raw, daily_totals = load_all_data(days_back=365, sample_size=None)
        importer_mapping = load_importer_mapping()

        df = df_raw.copy()
        df = prepare_enriched_data(df)
        df = apply_importer_mapping(df, importer_mapping)
        df = parse_upgrades(df)
        df = parse_dates_in_jobiqo(df)
        df = add_occupation_column(df)
        df = process_salary_columns(df)

    # Initialize session state
    for key in ['global_filters', 'comp_left_filters', 'comp_right_filters']:
        if key not in st.session_state:
            st.session_state[key] = None

    # === SIDEBAR FILTERS ===
    with st.sidebar:
        st.markdown('<div style="font-family:DM Sans,sans-serif;font-weight:700;font-size:14px;color:#9c67d3;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">Filters</div>', unsafe_allow_html=True)
        filters, apply_clicked = create_sidebar_filters(df)

        # Apply filters to session state
        if apply_clicked:
            st.session_state.global_filters = filters

        # Footer
        st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        st.caption(f"Total vacancies: {len(df):,}")
        if st.button("Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # === MAIN CONTENT ===
    # Logo above tabs
    st.markdown(main_logo(), unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Dashboard",
        "Performance",
        "Compare",
        "Salary Benchmarking",
    ])

    with tab1:
        render_dashboard(df, daily_totals=daily_totals)

    with tab2:
        render_performance(df)

    with tab3:
        render_compare(df)

    with tab4:
        render_salary(df)


if __name__ == "__main__":
    main()
