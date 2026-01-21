# Job Performance Dashboard Features

## Overview
A self-hosted Streamlit web application that provides interactive reporting and analysis of job performance data from Google Sheets.

## Key Features

### 📊 Real-Time Data Integration
- Direct connection to Google Sheets
- Auto-refresh capability
- 5-minute cache for performance
- Manual refresh button available

### 🔍 Advanced Filtering
- **Date Range**: Filter by event date range
- **Occupation**: Multi-select job types
- **Region**: Multi-select geographical locations
- **Organization**: Multi-select organizations
- **Importer**: Filter by data importer (displays names instead of IDs)
- **Event Name**: Filter by event types
- Reset all filters with one click

### 📈 Data Visualizations
- **Metrics Cards**: Total records, unique organizations, occupations, and regions
- **Top 10 Occupations**: Horizontal bar chart
- **Events Over Time**: Time series line chart
- **Regional Distribution**: Interactive pie chart
- **Importer Distribution**: Interactive pie chart with readable names

### 🎯 Importer ID Mapping
- Automatically converts numeric importer IDs to human-readable names
- Configured via separate Google Sheets tab
- Easy to maintain without code changes

### 📋 Data Table
- Interactive, sortable data table
- Customizable column selection
- Shows filtered results in real-time

### 💾 Export Capabilities
- **CSV Export**: Download filtered data as CSV
- **Excel Export**: Download filtered data as .xlsx
- Timestamped filenames
- Preserves all filters and selections

### 🔐 Security Features
- Service account authentication
- Read-only access to Google Sheets
- Credentials stored locally (not in code)
- .gitignore configured for sensitive files

### 🚀 Performance
- Cached data loading (5-minute TTL)
- Optimized data processing with pandas
- Responsive UI with Streamlit

## Technical Stack

- **Frontend/Backend**: Streamlit
- **Data Processing**: Pandas
- **Visualizations**: Plotly
- **API Integration**: gspread + Google Sheets API
- **Authentication**: Google Service Account
- **Export**: openpyxl for Excel, native CSV

## Use Cases

1. **Performance Analysis**: Track job events and trends over time
2. **Regional Reporting**: Analyze job distribution by geography
3. **Importer Monitoring**: Monitor data sources and quality
4. **Occupation Insights**: Identify most common job types
5. **Custom Reports**: Filter and export specific data subsets
6. **Executive Dashboards**: Quick metrics overview

## Customization Options

The application is designed to be easily customizable:

- Add new filters by modifying the sidebar section
- Create additional visualizations using Plotly
- Modify the metrics cards to show different KPIs
- Adjust the caching duration (currently 5 minutes)
- Add authentication layer for production use
- Customize the color scheme and branding

## Deployment Flexibility

- **Local Development**: Run on your machine
- **Internal Server**: Host on company network
- **Docker**: Containerized deployment
- **Cloud VM**: Deploy to AWS/GCP/Azure
- **Streamlit Cloud**: Public or private cloud hosting

## Future Enhancement Ideas

- User authentication and role-based access
- Saved filter presets
- Scheduled email reports
- Data quality monitoring
- Advanced analytics (cohort analysis, trends)
- Multiple data source support
- Custom dashboard builder
- Export to PDF reports
- API endpoint for programmatic access
