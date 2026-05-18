# MBIT — dbt Project

Maryland Budget Technology Spend Analysis — dbt models, metrics, and semantic layer.

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Load data into DuckDB
python load_data.py --input data/enriched/budget_enriched.parquet

# 3. Install dbt packages
dbt deps

# 4. Run models
dbt run

# 5. Test
dbt test

# 6. Query metrics (examples)
mf query --metrics it_spend --group-by metric_time
mf query --metrics it_spend --group-by it_tower
mf query --metrics it_spend_yoy_pct --group-by agency_name
mf query --metrics it_spend_pct --group-by fiscal_year
```

## Project Structure

```
models/
├── staging/
│   ├── _sources.yml              # Raw data source definition
│   └── stg_budget_line_items.sql # Clean + type raw data
├── marts/
│   ├── fct_it_spend.sql          # Fact table: all spend with TBM classifications
│   ├── dim_agency.sql            # Agency dimension
│   ├── dim_program.sql           # Program/subprogram dimension
│   ├── dim_fiscal_year.sql       # Time spine for MetricFlow
│   └── _marts.yml                # Tests
├── metrics/
│   ├── sem_it_spend.yml          # Semantic model (MetricFlow)
│   └── metrics.yml               # Metric definitions
```

## Available Metrics

| Metric | Description | Stakeholder |
|---|---|---|
| total_spend | Total budget amount | All |
| it_spend | IT-classified spend | All |
| non_it_spend | Non-IT spend | CFO |
| it_spend_pct | IT as % of total | CFO |
| it_spend_yoy_change | IT spend YoY absolute change | CIO, CFO |
| it_spend_yoy_pct | IT spend YoY % change | CIO, CFO |
| total_spend_yoy_pct | Total spend YoY % change | CFO |

## Available Dimensions

| Dimension | Example Query |
|---|---|
| fiscal_year | Trend over time |
| agency_name | By agency |
| it_tower | CIO view — by technology function |
| cost_pool | CFO view — by financial category |
| cost_sub_pool | Detailed financial breakdown |
| it_designation | MITDP vs ITIF vs F50 |
| fund_type | General vs Special funds |
| program_name | By program |
| subprogram_name | By subprogram (most granular) |
```
