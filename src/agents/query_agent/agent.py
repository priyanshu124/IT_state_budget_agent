"""
LangGraph Budget Query Agent — QueryPlan-driven
=================================================
All nodes share a structured QueryPlan artifact so SQL generation,
validation, chart rendering, and narration work from the same contract.

Flow:
    plan()       → QueryPlan via tool_use (structured JSON)
    write_sql()  ← receives QueryPlan fields explicitly in prompt
    execute()
    validate()   ← checks result columns match plan; triggers fix if not
    fix_sql()    ← fires on SQL error or validation failure
    narrate()    ← scoped to QueryPlan.analysis_type
"""

import argparse
import json
import re
from typing import Literal, TypedDict

from loguru import logger
from pydantic import BaseModel, Field

from src.agents.query_agent.catalog import (
    METRIC_CATALOG,
    CHART_TYPE_GUIDANCE,
    OUTPUT_SHAPE_RULES,
    EXAMPLE_QUERIES,
    build_dynamic_catalog,
)
from src.agents.query_agent.tools import QueryTools


# ── QueryPlan ──────────────────────────────────────────────────

class QueryPlan(BaseModel):
    # Intent
    analysis_type: Literal["total", "trend", "breakdown", "comparison", "ranking", "variance", "describe"]
    fiscal_years: list[int] = Field(default_factory=list)

    # Data contract — tells write_sql exactly what to produce
    dimensions: list[str] = Field(default_factory=list)
    measures: list[str] = Field(default_factory=list)     # e.g. "SUM(it_amount) AS it_spend"
    filters: dict[str, list[str]] = Field(default_factory=dict)
    top_n: int | None = None
    output_shape: Literal["aggregated", "timeseries", "long", "pivot"] = "aggregated"

    # Chart contract — drives render_chart() in app.py, no heuristics needed
    chart_type: Literal["line", "bar_h", "bar_v", "stacked_bar", "pie", "none"]
    chart_x: str
    chart_y: str
    chart_series: str | None = None
    chart_title: str
    chart_sort_desc: bool = True

    is_followup: bool = False


# ── Agent State ────────────────────────────────────────────────

class AgentState(TypedDict):
    question: str
    query_plan: dict
    sql: str
    raw_results: dict
    formatted_table: str
    narrative: str
    error: str | None
    validation_error: str | None


class ConversationTurn(TypedDict):
    question: str
    sql: str
    narrative: str
    row_count: int
    sample_rows: str
    query_plan: dict


# ── Tool schema for structured plan ───────────────────────────

PLAN_TOOL = {
    "name": "create_query_plan",
    "description": "Create a structured query plan for the Maryland budget question.",
    "input_schema": {
        "type": "object",
        "properties": {
            "analysis_type": {
                "type": "string",
                "enum": ["total", "trend", "breakdown", "comparison", "ranking", "variance", "describe"],
            },
            "fiscal_years": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Fiscal years to filter on. Rules: "
                    "(1) If user asks about trend, changes, increases, decreases, growth, YoY, or 'over the years' → empty list (all years). "
                    "(2) If user mentions a specific year → use exactly that year. "
                    "(3) If no year mentioned and NOT a trend question → use [LATEST_YEAR] as the default single-year filter."
                ),
            },
            "dimensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exact column names to GROUP BY.",
            },
            "measures": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Measure expressions as 'SUM(col) AS alias'. Use it_amount for IT, amount for total.",
            },
            "filters": {
                "type": "object",
                "additionalProperties": {"type": "array", "items": {"type": "string"}},
                "description": "Column → list of exact catalog values to filter on.",
            },
            "top_n": {"type": ["integer", "null"]},
            "output_shape": {
                "type": "string",
                "enum": ["aggregated", "timeseries", "long", "pivot"],
                "description": "Required SQL output shape for chart rendering.",
            },
            "chart_type": {
                "type": "string",
                "enum": ["line", "bar_h", "bar_v", "stacked_bar", "pie", "none"],
            },
            "chart_x": {"type": "string", "description": "Column/alias for x-axis."},
            "chart_y": {"type": "string", "description": "Column/alias for y-axis (the measure alias)."},
            "chart_series": {
                "type": ["string", "null"],
                "description": "Column for multi-series grouping. Null for single series.",
            },
            "chart_title": {"type": "string"},
            "chart_sort_desc": {"type": "boolean"},
            "is_followup": {"type": "boolean"},
        },
        "required": [
            "analysis_type", "fiscal_years", "dimensions", "measures",
            "filters", "top_n", "output_shape",
            "chart_type", "chart_x", "chart_y", "chart_series",
            "chart_title", "chart_sort_desc", "is_followup",
        ],
    },
}


# ── Agent ──────────────────────────────────────────────────────

class BudgetQueryAgent:

    MAX_HISTORY = 10
    SAMPLE_ROWS = 5

    def __init__(
        self,
        api_key: str,
        db_path: str = "mbtsa_work.duckdb",
        model: str = "claude-sonnet-4-20250514",
    ):
        try:
            import anthropic
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.tools = QueryTools(db_path)

        dynamic = build_dynamic_catalog(db_path)
        self.full_catalog = METRIC_CATALOG + dynamic
        self.latest_fiscal_year = self._fetch_latest_fiscal_year(db_path)
        self._has_description_col = self._check_column_exists(db_path, "description")

        if not self._has_description_col:
            self.full_catalog += (
                "\n\nNOTE: The 'description' column does NOT exist in this database. "
                "For describe queries, select program_name, subprogram_name, unit_name, "
                "and agency_name instead. Do NOT reference a description column."
            )

        self.examples_str = "\n".join(
            f"Q: {ex['question']}\nSQL: {ex['sql'].strip()}\n"
            for ex in EXAMPLE_QUERIES
        )

        self.sql_context = f"""{self.full_catalog}

{CHART_TYPE_GUIDANCE}

{OUTPUT_SHAPE_RULES}

EXAMPLE QUERIES:
{self.examples_str}"""

        self.history: list[ConversationTurn] = []
        logger.info("Agent initialized")

    @staticmethod
    def _check_column_exists(db_path: str, column: str) -> bool:
        try:
            import duckdb
            con = duckdb.connect(db_path, read_only=True)
            cols = [r[0].lower() for r in con.execute(
                "DESCRIBE main_marts.fct_it_spend"
            ).fetchall()]
            con.close()
            exists = column.lower() in cols
            logger.info(f"Column '{column}' exists: {exists}")
            return exists
        except Exception as e:
            logger.warning(f"Could not check column '{column}': {e}")
            return False

    @staticmethod
    def _fetch_latest_fiscal_year(db_path: str) -> int:
        try:
            import duckdb
            con = duckdb.connect(db_path, read_only=True)
            row = con.execute(
                "SELECT MAX(fiscal_year) FROM main_marts.fct_it_spend"
            ).fetchone()
            con.close()
            year = int(row[0]) if row and row[0] else 2027
            logger.info(f"Latest fiscal year in DB: {year}")
            return year
        except Exception as e:
            logger.warning(f"Could not fetch latest fiscal year: {e}; defaulting to 2027")
            return 2027

    # ── Memory ─────────────────────────────────────────────────

    def _build_history_messages(self) -> list[dict]:
        messages = []
        for turn in self.history[-self.MAX_HISTORY:]:
            messages.append({"role": "user", "content": turn["question"]})
            summary = f"{turn['narrative']}\n\n[Query returned {turn['row_count']} rows]"
            if turn["sample_rows"]:
                summary += f"\n[Sample data:\n{turn['sample_rows']}]"
            messages.append({"role": "assistant", "content": summary})
        return messages

    def _condense_results(self, state: AgentState) -> ConversationTurn:
        raw = state.get("raw_results", {})
        sample = ""
        if raw.get("columns") and raw.get("rows"):
            cols = raw["columns"]
            rows = raw["rows"][:self.SAMPLE_ROWS]
            header = " | ".join(str(c) for c in cols)
            data_rows = "\n".join(" | ".join(str(v) for v in row) for row in rows)
            sample = f"{header}\n{data_rows}"
        return ConversationTurn(
            question=state["question"],
            sql=state["sql"],
            narrative=state.get("narrative", ""),
            row_count=raw.get("row_count", 0),
            sample_rows=sample,
            query_plan=state.get("query_plan", {}),
        )

    def _add_to_history(self, turn: ConversationTurn):
        self.history.append(turn)
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]

    def clear_history(self):
        self.history = []
        logger.info("Conversation history cleared")

    # ── SQL guards ─────────────────────────────────────────────

    @staticmethod
    def _select_clause_has_wildcard(select_clause: str) -> bool:
        return bool(re.search(r"(^|,)\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)?\*\s*(,|$)", select_clause))

    def _violates_sql_column_policy(self, sql: str) -> str | None:
        if not sql or not sql.strip():
            return "Policy violation: SQL is empty."
        sql_clean = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
        sql_clean = re.sub(r"--.*?$", " ", sql_clean, flags=re.MULTILINE)
        for match in re.finditer(r"\bselect\b(.*?)\bfrom\b", sql_clean, flags=re.IGNORECASE | re.DOTALL):
            clause = match.group(1)
            if self._select_clause_has_wildcard(clause):
                return "Policy violation: do not use SELECT *."
            if re.search(r"\bbudget_type\b", clause, flags=re.IGNORECASE):
                return "Policy violation: do not select budget_type."
        return None

    # ── Node 1: Plan ───────────────────────────────────────────

    def plan(self, state: AgentState) -> AgentState:
        logger.info(f"Planning: {state['question']}")

        history_msgs = self._build_history_messages()
        prior_plan = ""
        if self.history and self.history[-1].get("query_plan"):
            prior_plan = f"\nPrior QueryPlan (for follow-up context only):\n{json.dumps(self.history[-1]['query_plan'], indent=2)}"

        system = f"""You are a government budget analyst AI for Maryland state budget data.

{self.full_catalog}

{CHART_TYPE_GUIDANCE}

{OUTPUT_SHAPE_RULES}

FISCAL YEAR RULES (apply every question):
  Latest fiscal year in the database: {self.latest_fiscal_year}

  DESCRIBE question (keywords: what is, what does, describe, tell me about, explain,
    what's the purpose of, overview of, details about, what does X do, what is X program,
    which unit, which agency, what unit does X belong to, what fund, what tower, what type):
    → analysis_type = describe
    → fiscal_years = []
    → chart_type = none
    → measures = []
    → dimensions = [program_name, agency_name] + any other field the user is asking about
    → SQL pattern (description is at PROGRAM level — always aggregate to program level):
        SELECT program_name, agency_name,
               MAX(unit_name) AS unit_name,        ← include if user asks about unit
               MAX(description) AS description,     ← always include for describe
               MAX(fund_type) AS fund_type,         ← include if user asks about fund
               MAX(it_tower) AS it_tower            ← include if user asks about tower
        FROM main_marts.fct_it_spend
        WHERE program_name ILIKE '%term%'
          [AND agency_name ILIKE '%agency%'  ← add if user mentions an agency/unit]
        GROUP BY program_name, agency_name
        HAVING MAX(description) IS NOT NULL
        LIMIT 5
    → Do NOT use SELECT DISTINCT with subprogram columns — that returns duplicate rows per subprogram

  TREND question (keywords: trend, change, changes, increase, increases, decrease, decreases,
    growth, decline, over the years, over time, by year, year over year, YoY, history, historical):
    → fiscal_years = []  (all years)
    → analysis_type = trend
    → output_shape = timeseries
    → chart_type = line

  SPECIFIC YEAR mentioned by user (e.g. "in FY2025", "for 2024"):
    → fiscal_years = [that year]
    → output_shape = aggregated (unless also a trend)

  NO YEAR mentioned + NOT a trend question:
    → fiscal_years = [{self.latest_fiscal_year}]  ← always default to latest year
    → output_shape = aggregated

PLANNING RULES:
- Treat each question as standalone unless the user explicitly references prior results.
- Map all filter values to EXACT strings from the catalog. Never invent values.
- measures must be expressions like "SUM(it_amount) AS it_spend" — include the alias.
- chart_x and chart_y must exactly match the alias or dimension column name in the SQL output.
- For multi-series charts: output_shape=long, chart_series=the grouping dimension column.
{prior_plan}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            tools=[PLAN_TOOL],
            tool_choice={"type": "any"},
            messages=history_msgs + [{"role": "user", "content": state["question"]}],
        )

        plan_input = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "create_query_plan":
                plan_input = block.input
                break

        if not plan_input:
            logger.warning("plan() got no tool_use block; using fallback")
            plan_input = {
                "analysis_type": "breakdown",
                "fiscal_years": [],
                "dimensions": ["agency_name"],
                "measures": ["SUM(amount) AS total_amount"],
                "filters": {},
                "top_n": 20,
                "output_shape": "aggregated",
                "chart_type": "bar_h",
                "chart_x": "total_amount",
                "chart_y": "agency_name",
                "chart_series": None,
                "chart_title": state["question"],
                "chart_sort_desc": True,
                "is_followup": False,
            }

        try:
            qp = QueryPlan(**plan_input)
            state["query_plan"] = qp.model_dump()
        except Exception as e:
            logger.error(f"QueryPlan validation failed: {e}")
            state["query_plan"] = plan_input

        logger.info(f"QueryPlan: {state['query_plan']}")
        return state

    @staticmethod
    def _extract_sql(text: str) -> str:
        """Extract pure SQL from model response, stripping prose and fences."""
        text = text.strip()

        # Pull content from ```sql ... ``` or ``` ... ``` fences
        fenced = re.search(r"```(?:sql)?\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()

        # If no fence, find the first SELECT/WITH and take everything from there
        sql_start = re.search(r"\b(SELECT|WITH)\b", text, re.IGNORECASE)
        if sql_start:
            return text[sql_start.start():].strip()

        return text

    # ── Node 2: Write SQL ──────────────────────────────────────

    def write_sql(self, state: AgentState) -> AgentState:
        logger.info("Generating SQL from QueryPlan...")

        qp = state["query_plan"]
        prior_sql = ""
        if self.history and qp.get("is_followup"):
            prior_sql = f"\nPrevious SQL (user drilling down):\n{self.history[-1]['sql']}\n"

        contract = f"""
QUERY CONTRACT — follow exactly:
  analysis_type : {qp.get('analysis_type')}
  output_shape  : {qp.get('output_shape')}
  dimensions    : {qp.get('dimensions')}
  measures      : {qp.get('measures')}
  filters       : {qp.get('filters')}
  fiscal_years  : {qp.get('fiscal_years')} (empty = no year filter; single value = filter to that year)
  latest_year   : {self.latest_fiscal_year}
  top_n         : {qp.get('top_n')}
  chart_x alias : {qp.get('chart_x')}   ← SELECT alias MUST match exactly
  chart_y alias : {qp.get('chart_y')}   ← SELECT alias MUST match exactly
  chart_series  : {qp.get('chart_series')}

OUTPUT SHAPE REQUIREMENTS:
  aggregated  → GROUP BY dimensions, one row per combination
  timeseries  → fiscal_year as first column, GROUP BY fiscal_year + dimensions
  long        → fiscal_year + series dimension + measure; one row per (year, series)
  pivot       → one row per entity, one column per fiscal year (CASE expressions)
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=f"""You are a SQL expert for DuckDB. Generate SQL from the QueryPlan contract.

HARD RULES:
- Table: main_marts.fct_it_spend
- NEVER SELECT *
- NEVER select budget_type
- Use only column names from the catalog
- WHERE is_it = true ONLY when analysis requires IT scope
- NULLIF for division
- Return ONLY SQL, no explanation, no fences

{self.sql_context}
{contract}
{prior_sql}""",
            messages=[{"role": "user", "content": f"Question: {state['question']}\n\nSQL:"}],
        )

        state["sql"] = self._extract_sql(response.content[0].text)
        logger.info(f"SQL: {state['sql'][:300]}")
        return state

    # ── Node 3: Execute ────────────────────────────────────────

    def execute(self, state: AgentState) -> AgentState:
        logger.info("Executing query...")

        policy_error = self._violates_sql_column_policy(state["sql"])
        if policy_error:
            state["error"] = policy_error
            state["raw_results"] = {"columns": [], "rows": [], "row_count": 0, "error": policy_error}
            state["formatted_table"] = f"Error: {policy_error}"
            return state

        result = self.tools.run_sql(state["sql"])
        if result["error"]:
            state["error"] = result["error"]
            state["raw_results"] = result
            state["formatted_table"] = f"Error: {result['error']}"
        else:
            state["raw_results"] = result
            state["formatted_table"] = self.tools.format_results_as_table(result)
            state["error"] = None
            logger.info(f"Got {result['row_count']} rows")

        return state

    # ── Node 4: Validate ───────────────────────────────────────

    def validate(self, state: AgentState) -> AgentState:
        """Verify result columns satisfy the QueryPlan contract."""
        state["validation_error"] = None

        if state.get("error"):
            return state

        raw = state.get("raw_results", {})
        result_cols = [str(c).lower() for c in raw.get("columns", [])]
        qp = state.get("query_plan", {})
        problems = []

        # Skip chart column checks for non-chart queries
        is_no_chart = qp.get("chart_type") == "none" or qp.get("analysis_type") == "describe"

        if not is_no_chart:
            for field in ("chart_x", "chart_y"):
                val = (qp.get(field) or "").lower()
                if val and val not in result_cols:
                    problems.append(f"{field}='{val}' missing from results {result_cols}")

            series = (qp.get("chart_series") or "").lower()
            if series and series not in result_cols:
                problems.append(f"chart_series='{series}' missing from results {result_cols}")

        if qp.get("output_shape") == "timeseries" and "fiscal_year" not in result_cols:
            problems.append("output_shape=timeseries but fiscal_year not in results")

        if raw.get("row_count", 0) == 0:
            problems.append("Query returned 0 rows — filters may be too restrictive or term not found")

        if problems:
            state["validation_error"] = "; ".join(problems)
            logger.warning(f"Validation: {state['validation_error']}")

        return state

    # ── Node 5: Fix SQL ────────────────────────────────────────

    def fix_sql(self, state: AgentState) -> AgentState:
        error = state.get("error") or state.get("validation_error", "")
        logger.info(f"Fixing SQL: {error}")

        qp = state["query_plan"]
        contract = f"""
FIX AGAINST THIS CONTRACT:
  dimensions   : {qp.get('dimensions')}
  measures     : {qp.get('measures')}
  filters      : {qp.get('filters')}
  output_shape : {qp.get('output_shape')}
  chart_x alias: {qp.get('chart_x')}   ← SELECT alias MUST match
  chart_y alias: {qp.get('chart_y')}   ← SELECT alias MUST match
  chart_series : {qp.get('chart_series')}
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=f"""You are a SQL debugger for DuckDB. Fix the SQL to satisfy the QueryPlan contract.
- NEVER SELECT *
- NEVER select budget_type
- SELECT aliases MUST exactly match chart_x and chart_y
- Return ONLY corrected SQL

{self.sql_context}
{contract}""",
            messages=[{
                "role": "user",
                "content": f"Original SQL:\n{state['sql']}\n\nProblem:\n{error}\n\nFixed SQL:",
            }],
        )

        state["sql"] = self._extract_sql(response.content[0].text)
        state["error"] = None
        state["validation_error"] = None
        logger.info(f"Fixed SQL: {state['sql'][:300]}")
        return state

    # ── Data context label ──────────────────────────────────────

    def _build_data_context(self, qp: dict, raw: dict) -> str:
        """Build a short deterministic data-scope line from the QueryPlan.

        Examples:
          Showing: FY2027 · All agencies · Total budget · 42 rows
          Showing: all available years (up to FY2027) · Agency: Dept of Health · IT spend · 8 rows
        """
        parts = []

        # Fiscal year scope
        fiscal_years = qp.get("fiscal_years", [])
        if not fiscal_years:
            parts.append(f"all available years (up to FY{self.latest_fiscal_year})")
        elif len(fiscal_years) == 1:
            parts.append(f"FY{fiscal_years[0]}")
        else:
            parts.append(f"FY{min(fiscal_years)}–FY{max(fiscal_years)}")

        # Active filters — skip is_it since it's an internal flag
        filters = qp.get("filters", {})
        for col, values in filters.items():
            if col == "is_it":
                continue
            label = col.replace("_", " ").replace(" code", "").replace(" name", "").title()
            val_str = ", ".join(str(v) for v in values[:3])
            if len(values) > 3:
                val_str += f" +{len(values)-3} more"
            parts.append(f"{label}: {val_str}")

        # Measure description
        measures = qp.get("measures", [])
        if measures:
            # Pull the AS alias from the first measure expression
            first = measures[0]
            alias_match = re.search(r"\bAS\s+(\w+)", first, re.IGNORECASE)
            if alias_match:
                alias = alias_match.group(1).replace("_", " ").title()
                parts.append(alias)

        # Row count
        row_count = raw.get("row_count", 0)
        parts.append(f"{row_count} rows")

        return "Showing: " + " · ".join(parts)

    def _format_describe_results(self, raw: dict) -> str:
        """Format describe query results — show program name + raw field values, no narrative."""
        rows = raw.get("rows", [])
        cols = [str(c).lower() for c in raw.get("columns", [])]

        if not rows:
            return "No matching programs found. Try a broader search term."

        col_idx = {c: i for i, c in enumerate(cols)}
        entries = []

        for row in rows:
            parts = []

            # Program / agency header
            name = row[col_idx["program_name"]] if "program_name" in col_idx else ""
            agency = row[col_idx["agency_name"]] if "agency_name" in col_idx else ""
            header = f"{name}"
            if agency:
                header += f" ({agency})"
            parts.append(header)

            # All other fields except program_name and agency_name
            skip = {"program_name", "agency_name"}
            for col in cols:
                if col in skip:
                    continue
                val = row[col_idx[col]]
                if val is None or str(val).strip() == "":
                    continue
                label = col.replace("_", " ").title()
                parts.append(f"{label}: {val}")

            entries.append("\n".join(parts))

        return "\n\n---\n\n".join(entries)

    # ── Node 6: Narrate ────────────────────────────────────────

    def narrate(self, state: AgentState) -> AgentState:
        logger.info("Generating narrative...")

        if state.get("error"):
            state["narrative"] = f"I wasn't able to answer that question. Query failed: {state['error']}"
            return state

        qp = state.get("query_plan", {})
        analysis_type = qp.get("analysis_type", "breakdown")

        # For describe queries: skip Claude narration entirely.
        # Just surface the raw description text from the results.
        if analysis_type == "describe":
            state["narrative"] = self._format_describe_results(state.get("raw_results", {}))
            return state
        chart_title = qp.get("chart_title", "")
        filters = qp.get("filters", {})
        fiscal_years = qp.get("fiscal_years", [])

        scope_lines = []
        if filters:
            scope_lines.append(f"Filters applied: {filters}")
        if fiscal_years:
            scope_lines.append(f"Fiscal years: {fiscal_years}")
        scope_note = "\n".join(scope_lines)

        prior_context = ""
        if self.history and qp.get("is_followup"):
            last = self.history[-1]
            prior_context = f"\n\nPrior question: \"{last['question']}\"\nPrior answer: {last['narrative'][:200]}..."

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=f"""You are a government budget analyst presenting findings to Maryland senior stakeholders.

Analysis type: {analysis_type}
Chart shown to user: {chart_title}
{scope_note}

NARRATIVE RULES:
- Open with the direct answer in the first sentence.
- Dollar formatting: >=1B → $X.XB, >=1M → $X.XM, >=1K → $X.XK, <1K → exact.
- trend     → describe direction, magnitude, and any inflection points.
- breakdown → highlight top and bottom entries by name and value.
- comparison → explicitly state the delta between entities.
- ranking   → name the top entries and the gap between first and last.
- variance  → call out anomalies and likely causes.
- describe  → present the results in plain language based on whatever columns were returned.
               State the program/entity name clearly, then answer the user's specific question
               using the returned field values (description, unit, fund type, tower, etc).
               If multiple rows matched, present each as a numbered entry.
               Do not invent information not present in the results.
- Stay strictly within the scope of returned data. Do not introduce outside metrics.
- Do not carry over prior-turn scope unless this is a follow-up.
- 2-4 paragraphs. End with one actionable insight if data supports it.
- Plain prose. No markdown, no SQL, no technical jargon.
- Do NOT restate the data scope (fiscal year, filters, row count) — that is shown separately.
{prior_context}""",
            messages=[{
                "role": "user",
                "content": f"Question: {state['question']}\n\nResults:\n{state['formatted_table']}",
            }],
        )

        data_context = self._build_data_context(qp, state.get("raw_results", {}))
        # describe queries don't need a scope line — no fiscal year or measure involved
        if qp.get("analysis_type") == "describe":
            state["narrative"] = response.content[0].text
        else:
            state["narrative"] = data_context + "\n\n" + response.content[0].text
        return state

    # ── Run ────────────────────────────────────────────────────

    def query(self, question: str) -> AgentState:
        state: AgentState = {
            "question": question,
            "query_plan": {},
            "sql": "",
            "raw_results": {},
            "formatted_table": "",
            "narrative": "",
            "error": None,
            "validation_error": None,
        }

        state = self.plan(state)
        state = self.write_sql(state)
        state = self.execute(state)

        if state["error"]:
            state = self.fix_sql(state)
            state = self.execute(state)

        state = self.validate(state)

        if state["validation_error"]:
            state = self.fix_sql(state)
            state = self.execute(state)

        state = self.narrate(state)

        self._add_to_history(self._condense_results(state))
        logger.info(f"History: {len(self.history)} turns")
        return state

    def print_answer(self, state: AgentState):
        print(f"\n{'='*70}")
        print(f"  Question: {state['question']}")
        print(f"{'='*70}")
        print(f"\n{state['narrative']}")
        if state["formatted_table"] and not state.get("error"):
            print(f"\n{'─'*70}")
            print(state["formatted_table"])
        print(f"\n{'─'*70}")
        print(f"  SQL: {state['sql'][:200]}{'...' if len(state['sql']) > 200 else ''}")
        if state.get("query_plan"):
            qp = state["query_plan"]
            print(f"  Chart: {qp.get('chart_type')} x={qp.get('chart_x')} y={qp.get('chart_y')} series={qp.get('chart_series')}")
        print(f"{'='*70}\n")


# ── CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Query Maryland budget with natural language")
    parser.add_argument("--db", default="mbtsa_work.duckdb")
    parser.add_argument("--model", default="claude-sonnet-4-20250514")
    parser.add_argument("--question", type=str, default=None)
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()

    import os
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: Set ANTHROPIC_API_KEY")
        return

    agent = BudgetQueryAgent(api_key=api_key, db_path=args.db, model=args.model)

    if args.question:
        agent.print_answer(agent.query(args.question))
    elif args.interactive:
        print("\n  MBTSA Budget Query Agent")
        print("  'clear' to reset memory, 'quit' to exit.\n")
        while True:
            q = input("  You: ").strip()
            if q.lower() in ("quit", "exit", "q"):
                break
            if q.lower() == "clear":
                agent.clear_history()
                print("  Memory cleared.\n")
                continue
            if q:
                agent.print_answer(agent.query(q))
    else:
        print("Run with --question or --interactive.")


if __name__ == "__main__":
    main()