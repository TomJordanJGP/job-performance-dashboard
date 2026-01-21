# Enhanced Dashboard Guide

## 🎉 What's New

The dashboard has been completely rebuilt with advanced benchmarking and comparison features!

## 🚀 Quick Start

```bash
cd /Users/ThomasJordan/Documents/001_Claude_Code/001_Data_Layer/job-performance-dashboard
./run.sh
```

Access at: **http://localhost:8502**

---

## 📊 Dashboard Structure

### **Tab 1: Overview Dashboard**
**Purpose:** High-level KPIs and performance trends

**Features:**
- ✅ 6 Key Metrics with benchmark indicators (🟢🟡🔴)
  - Total Vacancies
  - Total Clicks
  - Total Applies
  - Apply/Click Ratio
  - Clicks per Vacancy
  - Applies per Vacancy
- ✅ Time series chart showing clicks & applies trends
- ✅ Performance by Importer (bar chart)
- ✅ Performance by Region (bar chart)
- ✅ Conversion funnel visualization

### **Tab 2: Deep Dive**
**Purpose:** Detailed cross-dimensional benchmarking

**Features:**
- ✅ Benchmark comparison table
  - Group by: Importer, Region, Occupation, or Company
  - Sortable columns
  - CSV export
- ✅ Performance heatmap (Region × Importer)
  - Color-coded by Apply/Click ratio
  - Green = high performance, Red = low performance

### **Tab 3: Vacancy Performance**
**Purpose:** Individual job-level analysis

**Features:**
- ✅ Enhanced vacancy table with:
  - Title, Company, Job ID
  - Start Date, End Date, Days Active
  - Clicks, Applies, Ratio %
  - **Clicks/Day** (performance rate)
  - **Applies/Day** (performance rate)
  - Region, Importer
  - **Upgrades** (Premium, Boost, etc.)
- ✅ Summary metrics
- ✅ CSV export

### **Tab 4: Comparison**
**Purpose:** Side-by-side A/B comparison

**Features:**
- ✅ Independent filters for Side A and Side B
- ✅ Metrics comparison with % difference
- ✅ Color-coded indicators (🟢 better, 🔴 worse)
- ✅ Visual bar chart comparison

---

## 🔍 Filters (Available on All Tabs)

Each tab has its own independent set of filters:

1. **Date Range** (default: last 6 months)
   - Vacancies must be active during this period
   - Only events within this period are counted

2. **Importer** (multi-select)
   - ATS feed
   - Civil Service
   - Scrape
   - Backfill

3. **Company** (multi-select)
   - Filter by organization name

4. **Region** (multi-select)
   - All UK regions (auto-extracted from locations)

5. **Occupation** (multi-select)
   - Job categories

6. **Upgrades** (multi-select) - NEW!
   - Boosted job
   - Featured job
   - Highlight job
   - Export job
   - Top Job
   - Multifrontend

7. **Job Title Search** (text input) - NEW!
   - Partial match search
   - Example: "Housing Director"

8. **🔄 Apply Filters Button**
   - Click to apply your filter selections
   - Prevents slow recalculation while selecting

---

## 📈 Benchmark Indicators

Performance is color-coded relative to overall average:

- 🟢 **Green**: >10% above average (excellent)
- 🟡 **Amber**: Within ±10% of average (normal)
- 🔴 **Red**: >10% below average (needs attention)

---

## 🎯 Key Metrics Explained

| Metric | Description | Formula |
|--------|-------------|---------|
| Total Vacancies | Unique job postings | Count of unique `entity_id` |
| Total Clicks | Job page visits | Count of `job_visit` events |
| Total Applies | Application starts | Count of `job_apply_start` events |
| Apply/Click % | Conversion rate | (Applies ÷ Clicks) × 100 |
| Clicks/Vacancy | Avg clicks per job | Total Clicks ÷ Total Vacancies |
| Applies/Vacancy | Avg applies per job | Total Applies ÷ Total Vacancies |
| Clicks/Day | Performance rate | Clicks ÷ Days Active |
| Applies/Day | Performance rate | Applies ÷ Days Active |

---

## 💡 Use Cases

### **Compare Regions**
1. Go to Deep Dive tab
2. Select filters (date range, importer, etc.)
3. Click Apply Filters
4. Group by: "Region"
5. Review benchmark table
6. Export CSV for reporting

### **Find Top Performers**
1. Go to Vacancy Performance tab
2. Set date range (e.g., last 3 months)
3. Click Apply Filters
4. Sort by "Ratio %" or "Clicks/Day"
5. Identify high-performing jobs
6. Export for analysis

### **A/B Test Importers**
1. Go to Comparison tab
2. Side A: Select "ATS feed" importer
3. Click Apply Filters
4. Side B: Select "Scrape" importer
5. Click Apply Filters
6. Review comparison metrics

### **Track Upgrade Impact**
1. Go to Overview tab
2. Select specific upgrade (e.g., "Boosted job")
3. Click Apply Filters
4. Review KPIs vs overall average
5. Check benchmark indicators

---

## 📤 Exports

All tabs support CSV export:
- Overview: N/A (use charts for reporting)
- Deep Dive: Benchmark comparison table
- Vacancy Performance: Full vacancy details
- Comparison: N/A (use screenshot)

---

## 🔧 Technical Details

### **Date Filter Logic**
```
To include a vacancy:
1. Vacancy must overlap with date range
   (start_date ≤ range_end AND end_date ≥ range_start)
2. Only count events where event_date is within date range
```

### **Upgrades Parsing**
- Source: BigQuery `upgrades` column
- Format: Values separated by ` | `
- Example: `"Boosted job | Featured job | Highlight job"`
- Filter: Match ANY selected upgrade

### **Data Refresh**
- BigQuery data: Cached for 1 hour
- Importer mapping: Cached for 5 minutes
- Jobiqo CSV: Cached for 5 minutes
- Manual refresh: Click "🔄 Refresh Data" in sidebar

---

## 🐛 Troubleshooting

### Filters not applying
- Make sure to click "🔄 Apply Filters" button
- Check that date range is valid
- Verify data exists for your filter selections

### Importer shows "ID: X"
- Check `importer_mapping.csv` file exists
- Verify column names: `importer_id`, `importer_name`
- Ensure CSV is UTF-8 encoded

### Upgrades not showing
- Verify BigQuery table has `upgrades` column
- Check for NULL values
- Ensure upgrades are separated by ` | `

### Regions showing "Unknown"
- Check `jobs-export.csv` has `locations` column
- Verify locations contain UK addresses
- Check UK postcode or city names are present

---

## 📝 Files

- `app.py` - Main dashboard application (enhanced version)
- `app_old.py` - Previous version (backup)
- `app_backup_YYYYMMDD_HHMMSS.py` - Timestamped backup
- `importer_mapping.csv` - Importer ID to name mapping
- `jobs-export.csv` - Daily Jobiqo export
- `service_account.json` - BigQuery credentials
- `utils/region_parser.py` - UK region extraction
- `FILTER_GUIDE.md` - Filter explanations
- `ENHANCED_DASHBOARD_GUIDE.md` - This file

---

## 🎓 Best Practices

1. **Start Broad** - Apply minimal filters first, then narrow down
2. **Use Date Range** - Always set an appropriate date range for valid comparisons
3. **Export Regularly** - Download CSV files for offline analysis
4. **Compare Apples to Apples** - Use same date range when comparing different segments
5. **Check Benchmarks** - Look for 🟢🟡🔴 indicators to identify outliers
6. **Monitor Trends** - Use Overview tab to track performance over time

---

## 🚀 What's Next?

Potential future enhancements:
- PDF report generation
- Automated email reports
- Custom date comparisons (e.g., this month vs last month)
- Advanced statistical analysis
- Geographic map visualization
- Predictive analytics

---

**Dashboard Version:** 2.0 Enhanced
**Last Updated:** January 20, 2026
**Support:** Check GitHub issues or contact your admin

Enjoy benchmarking! 📊✨
