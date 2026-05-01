"""
Metric catalog for the LangGraph query agent.

Two parts:
  1. METRIC_CATALOG — static schema and rules (always in prompt)
  2. build_dynamic_catalog() — loads actual distinct values from DuckDB
     ONLY for AI-enriched columns so the agent uses exact category names.
"""

import duckdb
from loguru import logger


METRIC_CATALOG = """
TABLE: main_marts.fct_it_spend
This is the primary fact table. All queries run against this table.

AVAILABLE COLUMNS:
  spend_id            — Surrogate key (unique per row)
    fiscal_year         — Fiscal year as integer (2020-2027)
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
    it_designation      — Why it's IT: MITDP, ITIF, F50_AGENCY, shadow_it (can still appear on rows normalized to non-IT)
  it_tower            — TBM resource tower (null if not IT)
  it_sub_tower        — TBM sub-tower (null if not IT)
  tower_confidence    — Classification confidence 0.0-1.0 (null if not IT)
  cost_pool           — TBM cost pool (populated for ALL rows)
  cost_sub_pool       — TBM cost sub-pool (populated for ALL rows)
  amount              — Dollar amount (can be negative for adjustments)
  it_amount           — Dollar amount if IT, else 0
  non_it_amount       — Dollar amount if not IT, else 0

KEY RULES FOR QUERIES:
  - Always use main_marts.fct_it_spend as the table name
  - For IT-only analysis: WHERE is_it = true
    - Never reference fiscal years before 2020
  - For dollar sums: SUM(amount) for total, SUM(it_amount) for IT, SUM(non_it_amount) for non-IT
    - Rows where tower = 'NOT_IT' are normalized to is_it = false, and tower fields are null
  - it_tower and it_sub_tower are only populated when is_it = true
  - cost_pool and cost_sub_pool are populated for ALL rows
  - For YoY: use LAG() OVER (ORDER BY fiscal_year)
  - Round percentages to 1 decimal place
  - Use NULLIF to avoid division by zero

CRITICAL — FILTERING ON AI-ENRICHED COLUMNS:
  When the user asks about a concept (e.g. "cybersecurity", "networking", "software costs"),
  you MUST match it to the EXACT values listed below. Do NOT guess or invent values.
  Use ILIKE or IN with the exact values. If a user says "cybersecurity", check which
  it_tower or it_sub_tower values relate to security and use those exact strings.
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
    """Load actual distinct values for AI-enriched columns from DuckDB.

    Returns a string block to append to the system prompt so the agent
    knows exactly what values exist — no guessing, no hallucination.
    """
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

    catalog = "\n".join(lines)
    logger.info(f"Dynamic catalog loaded: {len(ENRICHED_COLUMNS)} columns")
    return catalog


EXAMPLE_QUERIES = [
    {
        "question": "What is the total IT spend for FY2020?",
        "sql": "SELECT SUM(it_amount) as it_spend FROM main_marts.fct_it_spend WHERE fiscal_year = 2020",
    },
    {
        "question": "Break down IT spend by tower for FY2020",
        "sql": "SELECT it_tower, SUM(it_amount) as it_spend FROM main_marts.fct_it_spend WHERE is_it = true AND fiscal_year = 2020 GROUP BY it_tower ORDER BY it_spend DESC",
    },
    {
        "question": "What percentage of total spend is IT?",
        "sql": "SELECT fiscal_year, ROUND(SUM(it_amount) * 100.0 / NULLIF(SUM(amount), 0), 1) as it_pct FROM main_marts.fct_it_spend GROUP BY fiscal_year ORDER BY fiscal_year",
    },
    {
        "question": "Show me the year-over-year change in IT spend",
        "sql": """
            WITH yearly AS (
                SELECT fiscal_year, SUM(it_amount) as it_spend
                FROM main_marts.fct_it_spend GROUP BY fiscal_year
            )
            SELECT fiscal_year, it_spend,
                it_spend - LAG(it_spend) OVER (ORDER BY fiscal_year) as yoy_change,
                ROUND((it_spend - LAG(it_spend) OVER (ORDER BY fiscal_year)) * 100.0
                    / NULLIF(LAG(it_spend) OVER (ORDER BY fiscal_year), 0), 1) as yoy_pct
            FROM yearly ORDER BY fiscal_year
        """,
    },
    {
        "question": "How much does DoIT spend on cybersecurity?",
        "sql": "SELECT fiscal_year, SUM(it_amount) as spend FROM main_marts.fct_it_spend WHERE agency_code = 'F50' AND it_tower = 'Security' AND is_it = true GROUP BY fiscal_year ORDER BY fiscal_year",
    },
    {
        "question": "Compare IT spend by cost pool across agencies",
        "sql": "SELECT agency_name, cost_pool, SUM(it_amount) as spend FROM main_marts.fct_it_spend WHERE is_it = true GROUP BY agency_name, cost_pool ORDER BY agency_name, spend DESC",
    },
    {
        "question": "What are the top 10 IT programs by spend?",
        "sql": "SELECT subprogram_name, agency_name, SUM(it_amount) as spend FROM main_marts.fct_it_spend WHERE is_it = true GROUP BY subprogram_name, agency_name ORDER BY spend DESC LIMIT 10",
    },
    {
        "question": "Show IT spend by tower and designation type",
        "sql": "SELECT it_tower, it_designation, SUM(it_amount) as spend FROM main_marts.fct_it_spend WHERE is_it = true GROUP BY it_tower, it_designation ORDER BY it_tower, spend DESC",
    },
]
