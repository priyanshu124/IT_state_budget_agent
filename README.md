# Maryland Budget Intelligence Tool (MBIT)

A comprehensive data engineering and AI-powered analytics platform for exploring Maryland state budget data with deep technology business management (TBM) classifications and intelligent querying capabilities.

**Live Dashboard:** https://md-budget-intel.netlify.app/
---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Running the Application](#running-the-application)
- [Core Components](#core-components)
- [Data Pipeline](#data-pipeline)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Contributing](#contributing)

---

## Overview

Maryland Budget Intelligence combines data engineering, machine learning, and interactive analytics to provide deep insights into state budget allocations, particularly IT spending. The system automatically classifies budget line items into Technology Business Management (TBM) cost pools and IT tower categories, enabling structured analysis across fiscal years and organizational hierarchies.

The platform serves two primary use cases:

1. **Interactive Dashboard** – Visual exploration of budget data, trends, anomalies, and comparisons
2. **Natural Language Queries** – Ask questions about the budget in plain English, get AI-generated SQL, and receive formatted answers

---

## Key Features

- ✅ **IT Spending Classification** – Automatically identifies and categorizes IT-related spending
- ✅ **TBM Cost Pool Mapping** – Maps accounting codes to standard TBM cost pools
- ✅ **Tower Classification** – Classifies IT spending across TBM resource towers and sub-towers
- ✅ **Interactive Dashboard** – Real-time budget exploration with filters, charts, and trend analysis
- ✅ **Natural Language Query** – Ask questions about budget data in plain English
- ✅ **Year-over-Year Analysis** – Track spending changes across fiscal years
- ✅ **Anomaly Detection** – Identify unusual spending patterns and variances
- ✅ **Agency-Level Breakdowns** – Deep dives into specific agencies and programs

---

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+ (for dashboard)
- Anthropic API key (for AI features)

### 1. Clone & Setup Environment

```bash
cd IT_state_budget_agent
chmod +x setup.sh
./setup.sh
```

### 2. Activate Virtual Environment

**macOS/Linux:**
```bash
source .venv/bin/activate
```

**Windows PowerShell:**
```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Load Data & Build Models

```bash
# Load budget data into DuckDB
python load_data.py --input data/output/final_budget_enriched.parquet

# Build DBT models
cd dbt-sql
dbt build
cd ..
```

### 4. Run the Dashboard

```bash
cd dashboard
npm install
npm run dev
```

Dashboard will be available at `http://localhost:5173`

### 5. (Optional) Run the Query Interface

```bash
streamlit run app.py
```

Query interface will be available at `http://localhost:8501`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Raw Budget Data (CSV/Parquet)               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
            ┌────────────────────────────┐
            │    Data Ingestion Layer    │
            │  (load_data.py → DuckDB)   │
            └────────────┬───────────────┘
                         │
                         ▼
            ┌────────────────────────────┐
            │   DBT Transformation       │
            │   (dbt-sql/models)         │
            └────────────┬───────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
    ┌────────┐    ┌────────────┐    ┌─────────┐
    │ Staging│    │AI Agents   │    │ Marts   │
    │Models  │    │Classification    │Tables  │
    └────────┘    └────────────┘    └─────────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
                         ▼
            ┌────────────────────────────┐
            │  Analytical Tables         │
            │  (fct_it_spend, etc.)      │
            └────────────┬───────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
    ┌─────────┐    ┌──────────┐    ┌──────────┐
    │ Evidence│    │Streamlit │    │ API      │
    │Dashboard│    │ Query    │    │ Backend  │
    └─────────┘    │Interface │    └──────────┘
                   └──────────┘
```

---

## Technology Stack

### Backend & Data Processing

| Component | Technology |
|-----------|------------|
| **Database** | DuckDB (analytical) |
| **Language** | Python 3.9+ |
| **Data Transform** | DBT (data build tool) |
| **Data Wrangling** | Pandas, Polars |
| **LLM** | Anthropic Claude API |
| **AI Framework** | LangChain |
| **Query Interface** | Streamlit |

### Frontend & Visualization

| Component | Technology |
|-----------|------------|
| **Dashboard Framework** | Evidence.dev |
| **Frontend Framework** | Svelte |
| **Charts** | ECharts, Evidence components |
| **Build Tool** | Vite |
| **Package Manager** | npm |

### Deployment

| Component | Service |
|-----------|---------|
| **Static Site** | Netlify |
| **Source Control** | Git |

---

## Project Structure

```
IT_state_budget_agent/
├── configs/                          # Configuration files
│   ├── it_programs.yaml             # IT program taxonomy
│   ├── llm.yaml                     # LLM agent configuration
│   └── tbm.yaml                     # TBM cost pool taxonomy
│
├── dashboard/                        # Evidence.dev dashboard project
│   ├── pages/                       # Dashboard pages (Svelte + markdown)
│   │   ├── budget-office/           # Budget office analytics page
│   │   ├── technology/              # Technology spending page
│   │   ├── variance-analysis/       # Year-over-year variance
│   │   ├── anomaly-detection/       # Spending anomalies
│   │   └── ask-questions/           # Natural language query interface
│   ├── components/                  # Reusable Svelte components
│   ├── build/                       # Compiled dashboard (auto-generated)
│   ├── evidence.config.yaml         # Dashboard configuration
│   └── package.json                 # Frontend dependencies
│
├── dbt-sql/                         # DBT transformation project
│   ├── models/                      # SQL transformation models
│   │   ├── staging/                 # Raw data cleaning and type casting
│   │   ├── marts/                   # Analytics-ready tables
│   │   ├── metrics/                 # Metrics definitions
│   │   └── custom_metrics_calendar/ # Time dimension
│   ├── dbt_project.yml             # DBT project configuration
│   ├── profiles.yml                # DuckDB connection config
│   ├── mbtsa_work.duckdb           # DuckDB database file
│   └── README.md                   # DBT-specific documentation
│
├── src/                            # Python application source code
│   ├── agents/                     # AI classification and query agents
│   │   ├── base_agent.py          # Base agent class
│   │   ├── cost_pool_mapper.py    # TBM cost pool classification
│   │   ├── tower_classifier.py    # IT tower classification
│   │   └── query_agent/           # Natural language query agent
│   │       ├── agent.py           # Query agent implementation
│   │       ├── catalog.py         # Budget data catalog
│   │       └── prompts/           # Agent prompts
│   │
│   ├── pipeline/                  # Data processing pipeline
│   │   ├── run_pipeline.py        # Main pipeline orchestrator
│   │   ├── build_final_enriched.py# Final data enrichment
│   │   ├── data_cleaner.py        # Data cleaning logic
│   │   ├── data_dedup.py          # Deduplication
│   │   └── data_enrichment.py     # Enrichment with classifications
│   │
│   ├── fte/                       # FTE (Full-Time Equivalent) processing
│   │   ├── load.py                # FTE data loading
│   │   ├── cleaning.py            # FTE cleaning
│   │   └── run_pipeline.py        # FTE pipeline
│   │
│   ├── schemas/                   # Pydantic data schemas
│   │   └── taxonomy.py            # Taxonomy schema definitions
│   │
│   ├── utils/                     # Shared utilities
│   │   ├── config.py              # Configuration management
│   │   ├── logging.py             # Logging setup
│   │   ├── tbm_reference.py       # TBM taxonomy utilities
│   │   └── helpers.py             # Helper functions
│   │
│   └── __init__.py
│
├── data/                           # Data directory (not committed)
│   ├── raw/                       # Raw input data
│   │   ├── budget/
│   │   ├── fte/
│   │   ├── funding_source/
│   │   └── tbm/
│   ├── processed/                 # Intermediate processing outputs
│   │   ├── *.json                 # Processed lookups
│   │   └── *.csv
│   ├── enriched/                  # Classification outputs
│   │   └── budget/
│   └── output/                    # Final output files
│       ├── final_budget_enriched.csv
│       └── cost_pool_mappings.csv
│
├── notebooks/                      # Jupyter notebooks
│   └── explore.ipynb              # Data exploration notebook
│
├── logs/                          # Application logs
│
├── app.py                         # Streamlit query interface
├── load_data.py                   # Data ingestion script
├── requirements.txt               # Python dependencies
├── pyproject.toml                # Project metadata
├── setup.sh                       # Setup script
├── .env.example                   # Environment variable template
└── README.md                      # This file
```

---

## Setup & Installation

### System Requirements

- **Python:** 3.9 or higher
- **Node.js:** 18 or higher (for dashboard only)
- **Disk Space:** 5GB+ (for data and models)
- **API Access:** Anthropic Claude API key (for AI features)

### Step 1: Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd IT_state_budget_agent

# Run automated setup
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Create a Python virtual environment (`.venv`)
- Upgrade pip, setuptools, and wheel
- Install all Python dependencies from `requirements.txt`
- Create `.env` file from `.env.example` if needed

### Step 2: Configure Environment Variables

Edit `.env` with your API keys and configuration:

```bash
# Required for AI features
ANTHROPIC_API_KEY=sk-ant-...

# Optional
MBTSA_DB=dbt-sql/mbtsa_work.duckdb
CLAUDE_MODEL=claude-3-5-sonnet-20241022
```

### Step 3: Activate Virtual Environment

**macOS/Linux:**
```bash
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

### Step 4: Install Dependencies (if needed)

```bash
pip install -r requirements.txt
```

---

## Running the Application

### Data Ingestion

Load your budget CSV or Parquet file into DuckDB:

```bash
python load_data.py \
  --input data/output/final_budget_enriched.parquet \
  --table budget_line_items
```

### Build DBT Models

Transform raw data into analytical tables:

```bash
cd dbt-sql
dbt build                    # Build all models
dbt run --models staging     # Run only staging models
dbt test                     # Run data quality tests
cd ..
```

The primary output table is `main_marts.fct_it_spend`, which contains all enriched budget data with IT classifications.

### Run the Interactive Dashboard

```bash
cd dashboard
npm install                  # Install frontend dependencies (first time only)
npm run dev                  # Start development server at http://localhost:5173
```

**Available pages:**
- `/` – Budget overview and summary
- `/budget-office` – Budget office analytics
- `/technology` – Technology spending analysis
- `/variance-analysis` – Year-over-year changes
- `/anomaly-detection` – Spending anomalies
- `/ask-questions` – Natural language query interface

### Run the Query Interface (Optional)

```bash
streamlit run app.py
```

Access at `http://localhost:8501`. This provides a conversational interface for asking questions about budget data.

### Build Production Dashboard

```bash
cd dashboard
npm run build               # Creates optimized build in `build/`
```

---

## Core Components

### 1. Cost Pool Mapper (`src/agents/cost_pool_mapper.py`)

Maps accounting subobject codes (e.g., "1200", "3401") to TBM cost pools and sub-pools.

**Features:**
- Uses Claude to classify codes based on names and descriptions
- Caches results for efficiency
- Reuses previous classifications automatically

**Usage:**
```python
from src.agents.cost_pool_mapper import CostPoolMapper

mapper = CostPoolMapper()
result = mapper.classify_cost_pools(df)
```

### 2. Tower Classifier (`src/agents/tower_classifier.py`)

Classifies IT programs into TBM resource towers and sub-towers.

**Supported classifications:**
- Maryland IT Delivery Platform (MITDP)
- IT Infrastructure Fund (ITIF)
- Confirmed IT agencies
- Shadow IT

**Usage:**
```python
from src.agents.tower_classifier import TowerClassifier

classifier = TowerClassifier()
result = classifier.classify_towers(df)
```

### 3. Query Agent (`src/agents/query_agent/agent.py`)

Converts natural-language questions into SQL, executes them, and returns formatted answers.

**Capabilities:**
- Understands budget dimensions (agencies, programs, towers, cost pools, fiscal years)
- Generates safe, auditable SQL
- Returns results with narrative explanations
- Supports aggregations, filters, and complex queries

**Usage:**
```python
from src.agents.query_agent.agent import BudgetQueryAgent

agent = BudgetQueryAgent()
response = agent.query("What was IT spending by agency in 2024?")
```

### 4. Evidence Dashboard

Interactive visual analytics built with Evidence.dev and Svelte.

**Key pages:**
- **Budget Office** – Treasury overview and spending summaries
- **Technology** – IT spending by tower, agency, and program
- **Variance Analysis** – Year-over-year changes and trends
- **Anomaly Detection** – Unusual spending patterns
- **Ask Questions** – Embedded Streamlit query interface

**Pages use:**
- SQL queries embedded in `.md` files
- Svelte components for interactivity
- ECharts for complex visualizations
- Evidence components (BarChart, DataTable, etc.)

### 5. Streamlit Query Interface (`app.py`)

Conversational budget exploration with natural-language input.

**Features:**
- Chat-like interface
- Returns SQL, results table, and narrative explanation
- Integrated with Query Agent
- Supports follow-up questions

---

## Data Pipeline

### High-Level Flow

```
Raw CSV/Parquet
    ↓
[load_data.py] → DuckDB (budget_line_items)
    ↓
[dbt build] → Staging models (cleaning, type casting)
    ↓
[AI Classification]
  ├─ Cost Pool Mapper (subobject → cost_pool)
  └─ Tower Classifier (program → tower)
    ↓
[Enrichment] → Add classifications to data
    ↓
[DBT Marts] → Analytical tables (fct_it_spend, etc.)
    ↓
[Dashboard & Query] → Evidence + Streamlit
```

### Key Tables

| Table | Location | Purpose |
|-------|----------|---------|
| `budget_line_items` | Raw → DuckDB | Raw ingested data |
| `stg_budget_line_items` | Staging | Cleaned, typed, normalized |
| `fct_it_spend` | Marts | Main analytical table with IT classifications |
| `dim_agency` | Dims | Agency dimension |
| `dim_program` | Dims | Program dimension |
| `cost_pool_level` | Aggs | Pre-aggregated by cost pool |

### DBT Transformation Models

- **Staging:** `stg_budget_line_items` – Raw data cleaning, type casting, trimming
- **Intermediate:** Bridge tables joining classifications
- **Marts:** `fct_it_spend` – Facts; `dim_*` – Dimensions
- **Aggregations:** Pre-aggregated tables for dashboard performance

---

## Deployment

### Live Dashboard

The Evidence dashboard is deployed to **Netlify**:

**URL:** https://md-budget-intel.netlify.app/

**Deployment flow:**
1. Commit changes to GitHub
2. Netlify automatically builds and deploys on push
3. Evidence generates a static site from dashboard pages
4. Query interface (Streamlit) can run as separate backend service

### Local Production Build

```bash
cd dashboard
npm run build
```

Creates an optimized, production-ready build in `dashboard/build/`.

### Deploy to Netlify (via CLI)

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Deploy
cd dashboard
netlify deploy --prod --dir=build
```

---

## Troubleshooting

### "Module not found" errors

Ensure virtual environment is activated and dependencies are installed:

```bash
source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Dashboard shows "No data available"

1. Check that DBT models have been built: `cd dbt-sql && dbt build`
2. Verify data is loaded: `python load_data.py --input <path>`
3. Confirm DuckDB file exists at `dbt-sql/mbtsa_work.duckdb`

### Query interface is slow

- Add indexes to frequently-queried columns in DBT models
- Pre-aggregate common queries in separate marts
- Cache LLM classification results (already implemented)

### API key errors

Verify `ANTHROPIC_API_KEY` is set in `.env`:

```bash
echo $ANTHROPIC_API_KEY  # macOS/Linux
echo %ANTHROPIC_API_KEY% # Windows cmd
$env:ANTHROPIC_API_KEY   # Windows PowerShell
```

### Dashboard build fails

```bash
cd dashboard
npm ci              # Clean install dependencies
npm run build       # Rebuild
```

---

## Known Limitations

1. **LLM Cost** – Classification of large datasets can be expensive. Caching mitigates this, but batching and rate-limiting should be considered.

2. **Query Agent Scope** – The query agent is tailored for budget data. Complex cross-domain queries may not be supported.

3. **Streamlit Dependency** – The query interface requires a running Streamlit backend. The static dashboard will work without it.

4. **Data Freshness** – Classification results are cached. Updated taxonomies require manual cache invalidation.

5. **Shadow IT Detection** – Shadow IT classification relies on program name patterns and may miss non-obvious IT spending.

---

## Contributing

### Code Style

- Python: Follow PEP 8, use `black` for formatting
- SQL: Use lowercase keywords, meaningful aliases
- JavaScript/Svelte: Use standard Prettier formatting

### Testing

```bash
# Run DBT tests
cd dbt-sql
dbt test

# Run Python unit tests (if available)
pytest src/
```

### Adding New Pages

1. Create `.md` file in `dashboard/pages/<section>/`
2. Add SQL queries in ` ```sql` blocks
3. Add visualizations using Evidence components or Svelte
4. Update navigation in `dashboard/pages/+layout.svelte`

### Adding New Classification Logic

1. Create new agent in `src/agents/`
2. Extend `BaseAgent` class
3. Implement `classify()` method
4. Add to pipeline in `src/pipeline/run_pipeline.py`
5. Update DBT models to use new classification

---

## Additional Resources

- **DBT Documentation:** https://docs.getdbt.com/
- **Evidence.dev Docs:** https://docs.evidence.dev/
- **DuckDB Guide:** https://duckdb.org/docs/
- **Streamlit Docs:** https://docs.streamlit.io/
- **Anthropic API:** https://docs.anthropic.com/

---

## License

[Add license information if applicable]

---

## Support & Contact

For questions or issues, please:
- Check existing documentation in `dbt-sql/README.md` and `dashboard/README.md`
- Review the technical handoff document for deeper architecture details
- Contact the development team

---

**Last Updated:** May 2026  
**Status:** Active Development
