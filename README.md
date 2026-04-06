# Maryland TBM Budget Pipeline (Handoff README)

This project processes Maryland budget data and enriches it with TBM taxonomy mappings using a mix of deterministic pipeline steps and LLM-powered agents.

This README is written for a new teammate taking over the repo.

## 1) What Is Already Done

The following has been implemented and is currently in use:

1. Pipeline foundation is working.
2. Agent base class exists and is used for shared run flow and token logging.
3. TBM taxonomy extraction workflow exists.
4. TBM tower extraction workflow exists.
5. Subobject-to-cost-pool mapper exists.
6. IT subprogram-to-tower classifier exists.
7. Config-driven defaults are defined in `configs/tbm.yaml`.
8. Logging writes to `logs/tbm_pipeline_YYYY-MM-DD.log`.
9. Notebook workflow exists for final enrichment joins and exports.

## 2) High-Level Data Flow

1. Raw budget input -> cleaned parquet + profile + dedup dimension.
2. TBM taxonomy PDF -> cost pool taxonomy YAML.
3. TBM taxonomy PDF -> tower taxonomy YAML.
4. Subobject codes CSV + taxonomy YAML -> cost pool mapping YAML.
5. IT subprogram CSV + towers YAML -> tower classifications (YAML + CSV).
6. Notebook joins budget + IT subprograms + subobject mappings -> enriched outputs.

## 3) Current Project Layout

```text
Agentic/
├── configs/
│   ├── tbm.yaml
│   └── tbm_config.yaml
├── data/
│   ├── raw/
│   ├── processed/
│   └── output/
├── logs/
├── notebooks/
│   └── explore.ipynb
├── src/
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── cost_pool_extractor.py
│   │   ├── cost_pool_mapper.py
│   │   ├── tower_extractor.py
│   │   └── tower_classifier.py
│   ├── pipeline/
│   │   ├── data_loader.py
│   │   ├── data_profiler.py
│   │   ├── data_depdup.py
│   │   └── run_pipeline.py
│   └── utils/
│       ├── config.py
│       └── logging.py
├── requirements.txt
└── README.md
```

## 4) Environment Setup

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create `.env` from `.env.example` and set:

```env
ANTHROPIC_API_KEY=your_key_here
```

## 5) Runbook (End-to-End)

Run from repo root `Agentic/`.

### Step A: Run base data pipeline

```powershell
python -m src.pipeline.run_pipeline --input data/raw/budget.csv
```

Expected artifacts in `data/processed/`:

1. `budget_cleaned.parquet`
2. `budget_profile.json` (path naming depends on input filename stem)
3. `budget_dim.parquet`

### Step B: Extract TBM cost pool taxonomy from PDF

```powershell
python -m src.agents.cost_pool_extractor --pdf data/raw/tbm_v5.pdf --pages 7-11 --output data/output/tbm_taxonomy.yaml
```

### Step C: Extract TBM towers from PDF

```powershell
python -m src.agents.tower_extractor --pdf data/raw/tbm_v5.pdf --pages 12-20 --output data/output/tbm_towers.yaml
```

### Step D: Map subobject codes to TBM cost pools

```powershell
python -m src.agents.cost_pool_mapper --codes data/processed/subobject_codes.csv --taxonomy data/output/tbm_taxonomy.yaml --output configs/cost_pool_mappings.yaml
```

### Step E: Classify IT subprograms into towers

```powershell
python -m src.agents.tower_classifier --subprograms data/processed/subprogram.csv --towers data/output/tbm_towers.yaml --output data/output/tower_classifications.yaml --csv data/output/tower_classifications.csv
```

### Step F: Final enrichment in notebook

Use `notebooks/explore.ipynb` to join:

1. `budget_cleaned.parquet`
2. `it_subprograms.csv`
3. `subobject_codes.csv`

Then export enriched dataset to `data/enriched/`.

## 6) Config You Should Know

Primary config: `configs/tbm.yaml`

Important sections:

1. `taxonomy_extractor`
2. `tower_extractor`
3. `tower_classifier`
4. `pipeline`

These provide defaults for file paths, page ranges, and model selection.

## 6.1) Key Fields Added by Agents

Use this as a quick reference for what columns are added during enrichment.

### A) Cost pool mapping enrichment

Source artifacts:

1. `configs/cost_pool_mappings.yaml`
2. `data/processed/subobject_codes.csv` (after mapping join in notebook)

Key added fields:

1. `cost_pool`
2. `cost_sub_post`

Join key used:

1. `comptroller_subobject_code`

### B) Tower classification enrichment

Source artifacts:

1. `data/output/tower_classifications.yaml`
2. `data/output/tower_classifications.csv`

Key classification fields produced by agent:

1. `organization_sub_code` (primary key used by classifier)
2. `tower`
3. `sub_tower`
4. `confidence`

Additional context fields emitted in classification output:

5. `is_it`
6. `it_designation` # F50, MITDP, ITIF

Join key used:

1. `organization_sub_code`

### C) Final enriched budget dataset

In `notebooks/explore.ipynb`, budget rows are enriched by joining on:

1. `organization_sub_code` (for tower labels)
2. `comptroller_subobject_code` (for cost pool labels)

Most important added analytical fields in final enriched output:

1. `tower`
2. `sub_tower`
3. `confidence`
4. `cost_pool`
5. `cost_sub_post`
6. `is_it`
7. `it_designation` # F50, MITDP, ITIF

## 7) Logging and Token Usage

1. Logs are written to `logs/tbm_pipeline_YYYY-MM-DD.log`.
2. Agent token usage is logged in a consistent format via `BaseAgent`.
3. Console still shows summary output for quick run checks.

## 8) Common Issues and Fixes

### Join key datatype mismatch in notebook

Symptom:

`SchemaError: datatypes of join keys don't match`

Fix:

Cast both sides of join keys to a common type (usually `Utf8`) before joining.

### Duplicate column name after joins

Symptom:

`DuplicateError: column with name '<name>_right' already exists`

Fix options:

1. Select only needed right-side columns before join.
2. Rename conflicting columns before join.
3. Use explicit `suffix` and avoid repeated joins that create the same suffixed names.

### Virtual environment activation in PowerShell fails

If `.\.venv\Scripts\activate` fails, run commands with explicit interpreter path:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.pipeline.run_pipeline
```

## 9) Handoff Notes for New Contributor

1. Start by running `python -m src.pipeline.run_pipeline` and `python -m src.agents.tower_classifier` to verify local setup.
2. Review `configs/tbm.yaml` before running agents so paths/models match your machine.
3. Use `notebooks/explore.ipynb` for final data joins and ad hoc QA.
4. Check `logs/` after every run for token usage and failure context.

## 10) Next Steps

1. Currently: only tose whcih we know are IT programs like F50, MITDP, ITIF have been enriched.
Pending: enriching programs that are IT inside different agencies

## 11) Web Deployment (Dashboard + Query Agent)

Use the single-site deployment assets in repo root:

1. `Dockerfile`
2. `render.yaml`
3. `requirements.deploy.txt`
4. `DEPLOYMENT.md`

See `DEPLOYMENT.md` for local Docker and Render deployment steps.
