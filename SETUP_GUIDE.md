# Setup Guide

## Quick Start Guide for Job Performance Dashboard

### Step 1: Install Python Dependencies

Navigate to the project directory and install the required packages:

```bash
cd job-performance-dashboard
pip install -r requirements.txt
```

Or if you prefer using a virtual environment (recommended):

```bash
cd job-performance-dashboard
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Set Up Google Sheets API Access

#### Creating a Service Account (Recommended)

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/

2. **Create or Select a Project**
   - Click on the project dropdown at the top
   - Click "New Project" or select an existing one

3. **Enable Google Sheets API**
   - Go to "APIs & Services" > "Library"
   - Search for "Google Sheets API"
   - Click on it and press "Enable"

4. **Create a Service Account**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Enter a name (e.g., "job-dashboard-reader")
   - Click "Create and Continue"
   - Skip the optional steps and click "Done"

5. **Create and Download Key**
   - Click on the service account you just created
   - Go to the "Keys" tab
   - Click "Add Key" > "Create New Key"
   - Select "JSON" format
   - Click "Create"
   - The JSON file will download automatically

6. **Save the Key File**
   - Rename the downloaded file to `service_account.json`
   - Move it to the `job-performance-dashboard` directory
   - **IMPORTANT**: Never commit this file to git (it's already in .gitignore)

7. **Share Google Sheet with Service Account**
   - Open the downloaded `service_account.json` file
   - Find the `client_email` field (looks like: `xxx@xxx.iam.gserviceaccount.com`)
   - Go to your Google Sheet
   - Click the "Share" button
   - Paste the service account email
   - Set permission to "Viewer" (read-only is sufficient)
   - Uncheck "Notify people"
   - Click "Share"

### Step 3: Verify Google Sheets Structure

Make sure your Google Sheet has these two tabs:

1. **job-performance-details_combined_2** - Your main data
2. **importer_mapping** - Two columns:
   - `importer_id` (numeric values)
   - `importer_name` (text names)

Example importer_mapping structure:
```
importer_id | importer_name
------------|---------------
1           | Data Team
2           | HR System
3           | External API
```

### Step 4: Run the Dashboard

```bash
streamlit run app.py
```

The dashboard will automatically open in your browser at `http://localhost:8501`

### Step 5: Using the Dashboard

#### Filters (Left Sidebar)
- **Date Range**: Select start and end dates
- **Occupation**: Filter by job types
- **Region**: Filter by location
- **Organization**: Filter by organization name
- **Importer**: Filter by data importer (now shows names instead of IDs)
- **Event Name**: Filter by event type

#### Main Dashboard Features
- **Metrics Cards**: Quick overview of total records, organizations, occupations, and regions
- **Visualizations**:
  - Top 10 Occupations bar chart
  - Events over time line chart
  - Regional distribution pie chart
  - Importer distribution pie chart
- **Data Table**: Customizable column display
- **Export**: Download filtered data as CSV or Excel

#### Buttons
- **Reset All Filters**: Clear all active filters
- **🔄 Refresh Data**: Reload data from Google Sheets (cache refreshes every 5 minutes automatically)
- **📥 Download as CSV/Excel**: Export filtered data

### Troubleshooting

#### "Service account credentials not found"
- Make sure `service_account.json` is in the `job-performance-dashboard` directory
- Check the file name is exactly `service_account.json`

#### "Permission denied" or "The caller does not have permission"
- Verify you shared the Google Sheet with the service account email
- Check the service account has at least "Viewer" permission

#### "Worksheet not found"
- Verify the sheet tab names match exactly:
  - `job-performance-details_combined_2`
  - `importer_mapping`

#### Importer names not showing
- Check the `importer_mapping` sheet has columns named exactly `importer_id` and `importer_name`
- Verify the importer_id values match those in the main data sheet

#### No data appears
- Check filters aren't too restrictive
- Click "Reset All Filters" to clear all filters
- Click "🔄 Refresh Data" to reload from Google Sheets

### Self-Hosting Options

#### Option 1: Run on Local Network
```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```
Access from other computers on your network using: `http://YOUR_IP_ADDRESS:8501`

#### Option 2: Docker Container
Create a `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0"]
```

Build and run:
```bash
docker build -t job-dashboard .
docker run -p 8501:8501 job-dashboard
```

#### Option 3: Cloud VM (AWS/GCP/Azure)
1. Provision a small VM
2. Install Python and dependencies
3. Set up as a systemd service or use screen/tmux
4. Configure firewall to allow port 8501
5. Optionally set up nginx reverse proxy with SSL

### Security Notes

- The `service_account.json` file contains sensitive credentials - never share or commit it
- For production deployment, consider adding authentication (Streamlit supports this)
- Run behind a VPN or add IP whitelisting for internal-only access
- Regularly review who has access to your Google Sheet

### Next Steps

- Customize the dashboard layout and visualizations in `app.py`
- Add more filters or metrics as needed
- Set up automated backups of the Google Sheet
- Consider adding user authentication for production use
