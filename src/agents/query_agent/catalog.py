"""
Metric catalog for the LangGraph query agent.

Three parts:
  1. METRIC_CATALOG        — static schema and rules (always in prompt)
  2. CHART_TYPE_GUIDANCE   — maps analysis_type to chart type and output_shape
  3. OUTPUT_SHAPE_RULES    — what each output_shape requires from SQL
  4. build_dynamic_catalog() — actual distinct values from DuckDB for AI-enriched columns
"""

import duckdb
from loguru import logger


METRIC_CATALOG = """
TABLE: main_marts.fct_it_spend
This is the primary fact table. All queries run against this table.

AVAILABLE COLUMNS:
  spend_id            — Surrogate key (unique per row)
  fiscal_year         — Fiscal year as integer (all available years in the dataset)
  agency_code         — State agency code (e.g. F50, C00)
  agency_name         — Full agency name
  unit_code, unit_name — Organizational unit
  program_code, program_name — Budget program
  subprogram_code, subprogram_name — Budget subprogram (most granular org level)
  object_code, object_name — Accounting object category
  subobject_code, subobject_name — Detailed accounting subobject
  fund_type           — Fund type (General Funds, Special Funds)
  budget_type         — Budget type (Budget - Actual, Budget - Appropriation, etc.)
  category_code, category_name — Budget category
  is_it               — Boolean: true = confirmed IT program
  it_designation      — Why it's IT: MITDP, ITIF, F50_AGENCY, shadow_it
  it_tower            — TBM resource tower (null if not IT)
  it_sub_tower        — TBM sub-tower (null if not IT)
  tower_confidence    — Classification confidence 0.0-1.0 (null if not IT)
  cost_pool           — TBM cost pool (populated for ALL rows)
  cost_sub_pool       — TBM cost sub-pool (populated for ALL rows)
  amount              — Dollar amount (can be negative for adjustments)
  it_amount           — Dollar amount if IT, else 0
  non_it_amount       — Dollar amount if not IT, else 0
  description         — Human-readable description of the program or subprogram (free text, can be null)

MEASURE SELECTION RULES:
  - Total budget (all spending)  → SUM(amount) AS total_amount
  - IT spending only             → SUM(it_amount) AS it_spend   + WHERE is_it = true
  - Non-IT spending              → SUM(non_it_amount) AS non_it_spend
  - IT as % of total             → ROUND(SUM(it_amount)*100.0/NULLIF(SUM(amount),0),1) AS it_pct
  - YoY change                   → LAG() OVER (ORDER BY fiscal_year)

KEY RULES:
  - Always use main_marts.fct_it_spend as the table name
  - fiscal_year is an integer; no restriction on range
  - NEVER SELECT * or select budget_type
  - it_tower and it_sub_tower only populated when is_it = true
  - cost_pool and cost_sub_pool populated for ALL rows
  - Use NULLIF to avoid division by zero
  - Round percentages to 1 decimal place
  - For describe queries: description lives at the PROGRAM level, not subprogram.
      Always query at program level: GROUP BY program_name, agency_name (+ any other requested field)
      and take MAX(description) to get the program description.
      Use ILIKE '%term%' on program_name to match. Also filter by agency/unit if the user mentions one.
      Do NOT return subprogram rows — one row per program.
      LIMIT 5

CRITICAL — FILTERING ON AI-ENRICHED COLUMNS:
  Match user concepts to EXACT values listed in the dynamic catalog below.
  Do NOT guess or invent values. Use ILIKE or IN with exact strings.
"""


CHART_TYPE_GUIDANCE = """
CHART TYPE SELECTION RULES:

  analysis_type → recommended chart_type and output_shape:

  describe     → chart_type=none (text lookup, no chart)
                 output_shape=aggregated
                 fiscal_years=[] (descriptions don't change by year)
                 dimensions=[columns relevant to the question — always include program_name and agency_name]
                 measures=[] (no aggregation)

  total        → chart_type=none (single number, no chart needed)
                 output_shape=aggregated

  trend        → chart_type=line
                 output_shape=timeseries (fiscal_year as first dimension)
                 If broken down by a category: output_shape=long, chart_series=category_col

  breakdown    → chart_type=bar_h (horizontal, best for named categories)
                 output_shape=aggregated
                 If time + category: chart_type=stacked_bar, output_shape=long

  comparison   → chart_type=bar_h (named entities are usually long labels)
                 output_shape=aggregated or pivot
                 Use bar_v only when comparing a small number (<=4) of short labels

  ranking      → chart_type=bar_h (sorted descending, top N; always horizontal — agency/program names are long)
                 output_shape=aggregated, top_n=10 (unless user specifies)

  variance     → chart_type=bar_v ONLY when result has both positive and negative values
                 output_shape=aggregated
                 If all values positive, use bar_h instead

  SPECIAL CASES:
  - Share of total / composition → chart_type=pie (max 8 slices; use top N + "Other")
  - Multi-year multi-category    → chart_type=stacked_bar, output_shape=long
  - Single scalar answer         → chart_type=none
  - More than 20 categories      → chart_type=bar_h with top_n=15

  chart_x and chart_y MUST be exact aliases or column names present in the SQL output:
  - bar_h  : chart_x=measure_alias, chart_y=dimension_col
  - bar_v  : chart_x=dimension_col, chart_y=measure_alias
  - line   : chart_x=fiscal_year,   chart_y=measure_alias
  - stacked_bar: chart_x=fiscal_year, chart_y=measure_alias, chart_series=category_col
  - pie    : chart_x=dimension_col (label), chart_y=measure_alias (value)
"""


OUTPUT_SHAPE_RULES = """
OUTPUT SHAPE REQUIREMENTS:

  aggregated:
    - One row per unique combination of dimensions
    - GROUP BY all dimension columns
    - No fiscal_year column required (unless it is a dimension)
    - Example: agency_name | total_amount

  timeseries:
    - fiscal_year MUST be the first column
    - GROUP BY fiscal_year (plus other dimensions if any)
    - Rows ordered by fiscal_year ASC
    - Example: fiscal_year | it_spend

  long:
    - Required for multi-series line and stacked bar charts
    - fiscal_year + one category dimension + measure
    - One row per (fiscal_year, category) combination
    - chart_series must be set to the category dimension column name
    - Example: fiscal_year | it_tower | it_spend

  pivot:
    - One row per entity, one column per fiscal year
    - Use CASE WHEN fiscal_year = YYYY THEN amount END pattern
    - Only include years present in the filtered dataset
    - Example: agency_name | fy_2024 | fy_2025 | fy_2026
"""


# AI-enriched columns whose exact values the agent needs to know
ENRICHED_COLUMNS = [
    "it_tower",
    "it_sub_tower",
    "cost_pool",
    "cost_sub_pool",
    "it_designation",
    "category_code",
    "category_name",
]


def build_dynamic_catalog(db_path: str) -> str:
    """Load actual distinct values for AI-enriched columns from DuckDB."""
    try:
        con = duckdb.connect(db_path, read_only=True)
    except Exception as e:
        logger.error(f"Cannot connect to {db_path}: {e}")
        return ""

    lines = ["\nACTUAL VALUES IN DATABASE (use ONLY these exact strings for filtering):"]

    for col in ENRICHED_COLUMNS:
        try:
            rows = con.execute(
                f"SELECT DISTINCT {col} FROM main_marts.fct_it_spend "
                f"WHERE {col} IS NOT NULL ORDER BY {col}"
            ).fetchall()
            values = [str(r[0]) for r in rows]
            if values:
                lines.append(f"\n  {col}:")
                for v in values:
                    lines.append(f"    - {v}")
        except Exception as e:
            logger.warning(f"Could not load values for {col}: {e}")

    con.close()
    logger.info(f"Dynamic catalog loaded: {len(ENRICHED_COLUMNS)} columns")
    return "\n".join(lines)


EXAMPLE_QUERIES = [
    {
        "question": "What is the total IT spend for FY2020?",
        "sql": "SELECT SUM(it_amount) AS it_spend FROM main_marts.fct_it_spend WHERE fiscal_year = 2020",
    },
    {
        "question": "Break down IT spend by tower for FY2025",
        "sql": (
            "SELECT it_tower, SUM(it_amount) AS it_spend "
            "FROM main_marts.fct_it_spend "
            "WHERE is_it = true AND fiscal_year = 2025 "
            "GROUP BY it_tower ORDER BY it_spend DESC"
        ),
    },
    {
        "question": "What percentage of total spend is IT by year?",
        "sql": (
            "SELECT fiscal_year, "
            "ROUND(SUM(it_amount)*100.0/NULLIF(SUM(amount),0),1) AS it_pct "
            "FROM main_marts.fct_it_spend "
            "GROUP BY fiscal_year ORDER BY fiscal_year"
        ),
    },
    {
        "question": "Year-over-year change in IT spend (trend/timeseries)",
        "sql": """
WITH yearly AS (
    SELECT fiscal_year, SUM(it_amount) AS it_spend
    FROM main_marts.fct_it_spend GROUP BY fiscal_year
)
SELECT fiscal_year, it_spend,
    it_spend - LAG(it_spend) OVER (ORDER BY fiscal_year) AS yoy_change,
    ROUND((it_spend - LAG(it_spend) OVER (ORDER BY fiscal_year))*100.0
        / NULLIF(LAG(it_spend) OVER (ORDER BY fiscal_year),0),1) AS yoy_pct
FROM yearly ORDER BY fiscal_year""",
    },
    {
        "question": "IT spend by tower over all years (long format for multi-series line)",
        "sql": (
            "SELECT fiscal_year, it_tower, SUM(it_amount) AS it_spend "
            "FROM main_marts.fct_it_spend "
            "WHERE is_it = true "
            "GROUP BY fiscal_year, it_tower "
            "ORDER BY fiscal_year, it_spend DESC"
        ),
    },
    {
        "question": "What is the MITDP program and what does it do?",
        "sql": (
            "SELECT program_name, agency_name, MAX(unit_name) AS unit_name, MAX(description) AS description "
            "FROM main_marts.fct_it_spend "
            "WHERE program_name ILIKE '%MITDP%' "
            "GROUP BY program_name, agency_name "
            "HAVING MAX(description) IS NOT NULL "
            "LIMIT 5"
        ),
    },
    {
        "question": "Describe the Community Services program in Developmental Disabilities Administration",
        "sql": (
            "SELECT program_name, agency_name, MAX(unit_name) AS unit_name, MAX(description) AS description "
            "FROM main_marts.fct_it_spend "
            "WHERE program_name ILIKE '%Community Services%' "
            "AND unit_name ILIKE '%Developmental Disabilities%' "
            "GROUP BY program_name, agency_name "
            "HAVING MAX(description) IS NOT NULL "
            "LIMIT 5"
        ),
    },
    {
        "question": "What fund type does the Medicaid program use?",
        "sql": (
            "SELECT program_name, agency_name, MAX(fund_type) AS fund_type "
            "FROM main_marts.fct_it_spend "
            "WHERE program_name ILIKE '%Medicaid%' "
            "GROUP BY program_name, agency_name "
            "LIMIT 5"
        ),
    },
    {
        "question": "What IT tower is the cybersecurity program classified under?",
        "sql": (
            "SELECT program_name, agency_name, MAX(it_tower) AS it_tower, MAX(it_sub_tower) AS it_sub_tower "
            "FROM main_marts.fct_it_spend "
            "WHERE is_it = true "
            "AND program_name ILIKE '%cyber%' "
            "GROUP BY program_name, agency_name "
            "LIMIT 5"
        ),
    },
    {
        "question": "Top 10 IT programs by spend",
        "sql": (
            "SELECT subprogram_name, agency_name, SUM(it_amount) AS it_spend "
            "FROM main_marts.fct_it_spend "
            "WHERE is_it = true "
            "GROUP BY subprogram_name, agency_name "
            "ORDER BY it_spend DESC LIMIT 10"
        ),
    },
    {
        "question": "Agency spend pivot by fiscal year",
        "sql": """
SELECT agency_name,
    SUM(CASE WHEN fiscal_year = 2024 THEN amount END) AS fy_2024,
    SUM(CASE WHEN fiscal_year = 2025 THEN amount END) AS fy_2025,
    SUM(CASE WHEN fiscal_year = 2026 THEN amount END) AS fy_2026
FROM main_marts.fct_it_spend
GROUP BY agency_name
ORDER BY fy_2026 DESC NULLS LAST""",
    },
    {
        "question": "Compare MITDP vs ITIF budget",
        "sql": (
            "SELECT it_designation, fiscal_year, SUM(it_amount) AS it_spend "
            "FROM main_marts.fct_it_spend "
            "WHERE is_it = true AND it_designation IN ('MITDP','ITIF') "
            "GROUP BY it_designation, fiscal_year "
            "ORDER BY fiscal_year, it_spend DESC"
        ),
    },
]