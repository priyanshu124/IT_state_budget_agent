# MITDP Dashboard Setup - Complete

## ✅ What's Been Done

### 1. **DuckDB Integration**
- ✅ Loaded 3 MITDP parquet tables into DuckDB (`mbtsa_work.duckdb`)
  - `mitdp.mitdp_projects` (60 rows × 53 cols)
  - `mitdp.mitdp_financials` (1,210 rows × 10 cols)
  - `mitdp.mitdp_metrics` (1,223 rows × 9 cols)
- ✅ Created `dashboard/sources/mitdp/connection.yaml` for Evidence.dev
- ✅ Data accessible via SQL queries in dashboard

### 2. **Evidence.dev Dashboard Pages**
- ✅ **Main MITDP Dashboard** ([it-projects/index.md](dashboard/pages/it-projects/index.md))
  - Portfolio summary KPIs (60 projects, $1.09B EAC, etc.)
  - Phase distribution pie/bar charts
  - Agency breakdown by budget
  - Funding mix stacked bar (ITIF vs Agency vs Federal)
  - Master project list table

- ✅ **Timeline & Details Page** ([it-projects/timeline-details.md](dashboard/pages/it-projects/timeline-details.md))
  - Project lifecycle overview
  - Budget burn & spend patterns
  - EAC estimate ranges (low-mid-high)
  - Cost remaining analysis
  - All data accessible via interactive tables

### 3. **Data Features**
- Phase tracking: Planning, Procurement, Implementation, O&M
- Budget metrics: EAC, FY25 actuals, FY26 forecasts, cost estimates
- Financial data: Funding mix (ITIF, Agency, Federal), time-series by fiscal year
- KPIs: Completion %, spend variance, funding ratios, risk metrics
- Lifecycle dates: Project start/end years, phase transitions
- DoIT enrichment: 128 enriched columns including lifecycle, spend variance, EAC ranges

### 4. **Available Visualizations**
- **Bar Charts**: Phase distribution, agency breakdown, spend patterns, EAC ranges
- **Pie/Donut**: Phase composition (filterable)
- **Stacked Bars**: Funding source mix by project
- **Tables**: Interactive, searchable, downloadable projects list
- **Multi-series**: FY25/FY26 spend comparison

---

## 🚀 Access the Dashboard

**Dashboard URL**: `http://localhost:3000/it-projects`

### Main Features:
1. **Executive Summary** - 4 KPI cards showing portfolio health
2. **Phase Distribution** - How many projects in each lifecycle phase
3. **Top Agencies** - Budget breakdown by agency
4. **Funding Mix** - ITIF % vs Agency % vs Federal % stacked bar
5. **Sortable Table** - All 60 projects with key metrics

### Timeline Page:
1. **Project Lifecycle** - Start/end years, elapsed/remaining time
2. **Spend Analysis** - FY25 actual vs forecast
3. **EAC Ranges** - Estimate certainty (low/mid/high)
4. **Cost Tracking** - Remaining budget, completion status

---

## 📊 Data Summary

| Metric | Value |
|--------|-------|
| Total Projects | 60 |
| Total EAC | $1.09 Billion |
| FY25 Actual Spend | $91.6 Million |
| FY26 Forecasted | $162.0 Million |
| Avg Completion | 32.5% |
| Implementation Phase | 23 projects |
| Top Agency | MDH (24 projects) |
| High-Risk Projects | 0 |

---

## 🔧 SQL Queries Available

All dashboard queries are **direct SQL** against DuckDB tables:

```sql
-- Portfolio summary
SELECT COUNT(*), SUM(eac_mid)/1e9 as total_eac_billions
FROM mitdp.mitdp_projects

-- Projects by phase
SELECT phase, COUNT(*) as project_count
FROM mitdp.mitdp_projects
GROUP BY phase

-- Funding mix
SELECT project_title, eac_mid, pct_itif_of_total_funding, 
       pct_agency_of_total_funding, pct_federal_of_total_funding
FROM mitdp.mitdp_projects
ORDER BY eac_mid DESC
```

---

## 📁 File Structure

```
dashboard/
├── pages/it-projects/
│   ├── index.md                    ← Main dashboard
│   └── timeline-details.md         ← Timeline & cost analysis
├── sources/mitdp/
│   └── connection.yaml             ← DuckDB connection config
```

---

## 🎯 Next Steps

1. **Customize filters** - Add agency/phase dropdowns to main page
2. **Add real-time updates** - Refresh button or scheduled refresh
3. **Drill-downs** - Click project name to see full details
4. **Export reports** - Generate PDF/Excel from dashboards
5. **Advanced analytics** - Risk scoring, variance tracking, forecasting

---

## ⚙️ Tech Stack

- **Data**: DuckDB (SQL engine)
- **Source**: 3 Parquet files (60+ MB total data)
- **Dashboard**: Evidence.dev with Svelte
- **Visualization**: Built-in charts (Bar, Pie, Line, Stacked, Table)
- **Styling**: Custom CSS with blue/purple theme

---

Generated: May 13, 2026
Dashboard Status: ✅ **LIVE** at http://localhost:3000/it-projects
