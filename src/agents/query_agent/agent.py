"""
LangGraph Budget Query Agent — with Conversation Memory
=========================================================
Maintains a condensed conversation history per session so Claude
can reference prior questions and answers in follow-up queries.

Memory design:
  - Each turn stores: question, SQL, narrative, row_count, sample_rows
  - History is condensed (not full result sets) to control token cost
  - Max history: last 10 turns (~2K tokens overhead per turn)
  - History is passed as assistant/user message pairs to Claude

Usage:
    python -m src.agents.query_agent.agent --db mbtsa_work.duckdb --interactive
"""

import argparse
import re
from typing import TypedDict

from loguru import logger

from src.agents.query_agent.catalog import (
    METRIC_CATALOG,
    EXAMPLE_QUERIES,
    build_dynamic_catalog,
)
from src.agents.query_agent.tools import QueryTools


# ── Agent State ────────────────────────────────────────────────

class AgentState(TypedDict):
    question: str
    plan: str
    sql: str
    raw_results: dict
    formatted_table: str
    narrative: str
    error: str | None


class ConversationTurn(TypedDict):
    question: str
    sql: str
    narrative: str
    row_count: int
    sample_rows: str  # first 5 rows as text


# ── Graph Nodes ────────────────────────────────────────────────

class BudgetQueryAgent:

    MAX_HISTORY = 10  # Keep last N turns
    SAMPLE_ROWS = 5   # Rows to include per turn in history

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

        # Build full context: static catalog + dynamic values from DB
        dynamic = build_dynamic_catalog(db_path)
        self.full_catalog = METRIC_CATALOG + dynamic

        self.examples_str = "\n".join(
            f"Q: {ex['question']}\nSQL: {ex['sql'].strip()}\n"
            for ex in EXAMPLE_QUERIES
        )

        self.sql_context = f"""{self.full_catalog}

EXAMPLE QUERIES:
{self.examples_str}"""

        # Conversation memory
        self.history: list[ConversationTurn] = []

        logger.info("Agent initialized with dynamic catalog and conversation memory")

    # ── Memory Management ──────────────────────────────────────

    def _build_history_messages(self) -> list[dict]:
        """Convert conversation history into Claude message pairs.

        Returns alternating user/assistant messages that give Claude
        context about what was discussed earlier in the session.
        """
        messages = []
        for turn in self.history[-self.MAX_HISTORY:]:
            # User turn
            messages.append({
                "role": "user",
                "content": turn["question"],
            })
            # Assistant turn — condensed summary
            summary = f"{turn['narrative']}\n\n[Query returned {turn['row_count']} rows]"
            if turn["sample_rows"]:
                summary += f"\n[Sample data:\n{turn['sample_rows']}]"
            messages.append({
                "role": "assistant",
                "content": summary,
            })
        return messages

    def _condense_results(self, state: AgentState) -> ConversationTurn:
        """Create a condensed memory entry from the current turn."""
        raw = state.get("raw_results", {})
        row_count = raw.get("row_count", 0)

        # Build sample rows text
        sample = ""
        if raw.get("columns") and raw.get("rows"):
            cols = raw["columns"]
            rows = raw["rows"][:self.SAMPLE_ROWS]
            header = " | ".join(str(c) for c in cols)
            data_rows = "\n".join(
                " | ".join(str(v) for v in row) for row in rows
            )
            sample = f"{header}\n{data_rows}"

        return ConversationTurn(
            question=state["question"],
            sql=state["sql"],
            narrative=state.get("narrative", ""),
            row_count=row_count,
            sample_rows=sample,
        )

    def _add_to_history(self, turn: ConversationTurn):
        """Add a turn to history, trimming to MAX_HISTORY."""
        self.history.append(turn)
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]

    def clear_history(self):
        """Clear conversation memory."""
        self.history = []
        logger.info("Conversation history cleared")

    @staticmethod
    def _is_followup_question(question: str) -> bool:
        """Return True only when the user explicitly indicates follow-up context."""
        q = (question or "").strip().lower()
        if not q:
            return False

        followup_markers = [
            "break that down", "drill down", "drill into", "as above", "same as above",
            "that result", "those results", "previous", "earlier", "prior", "again",
            "instead", "now do", "also", "what about", "for that", "for those", "same",
        ]
        return any(marker in q for marker in followup_markers)

    @staticmethod
    def _question_requests_explicit_order(question: str) -> bool:
        """Return True when the user explicitly asks for a specific ordering."""
        q = (question or "").lower()
        order_terms = [
            "ascending", "descending", "asc", "desc", "sort",
            "order by", "alphabet", "a-z", "z-a", "chronological",
            "latest", "newest", "oldest", "by year",
        ]
        return any(term in q for term in order_terms)

    @staticmethod
    def _insert_before_limit(sql: str, clause: str) -> str:
        """Insert clause before the last LIMIT if present, else append at end."""
        limit_matches = list(re.finditer(r"\blimit\b", sql, flags=re.IGNORECASE))
        if not limit_matches:
            return sql.rstrip().rstrip(";") + "\n" + clause

        last = limit_matches[-1]
        return sql[:last.start()].rstrip() + "\n" + clause + "\n" + sql[last.start():].lstrip()

    def _ensure_default_budget_order(self, sql: str, question: str) -> str:
        """Apply default DESC ordering by budget/spend when user did not specify order."""
        sql_clean = (sql or "").strip()
        if not sql_clean:
            return sql_clean

        if self._question_requests_explicit_order(question):
            return sql_clean

        if not re.search(r"\bselect\b", sql_clean, flags=re.IGNORECASE):
            return sql_clean

        # Prefer common spend aliases from projected output columns only.
        projected_aliases = re.findall(
            r"\bas\s+\"?([A-Za-z_][A-Za-z0-9_]*|fy[_-]?\d{4}|\d{4})\"?",
            sql_clean,
            flags=re.IGNORECASE,
        )
        alias_lookup = {a.lower(): a for a in projected_aliases}
        alias_priority = [
            "total_amount", "it_spend", "total_spend", "spend", "budget", "it_amount", "non_it_amount",
        ]
        chosen_alias = next((alias_lookup[a] for a in alias_priority if a in alias_lookup), None)

        # For pivot outputs (fy_2020, 2020), sort by latest year column as fallback.
        if not chosen_alias:
            year_aliases = re.findall(r"\bas\s+\"?(fy[_-]?\d{4}|\d{4})\"?", sql_clean, flags=re.IGNORECASE)
            if year_aliases:
                chosen_alias = sorted(year_aliases, key=lambda x: int(re.sub(r"\D", "", x)))[-1]

        if not chosen_alias:
            return sql_clean

        # Quote aliases like "2027" when needed.
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", chosen_alias):
            order_expr = chosen_alias
        else:
            order_expr = f'"{chosen_alias}"'

        order_clause = f"ORDER BY {order_expr} DESC"

        # If SQL already has ORDER BY, wrap and enforce final ordering in outer query.
        if re.search(r"\border\s+by\b", sql_clean, flags=re.IGNORECASE):
            inner = sql_clean.rstrip().rstrip(";")
            return f"SELECT * FROM (\n{inner}\n) _ordered\n{order_clause}"

        return self._insert_before_limit(sql_clean, order_clause)

    @staticmethod
    def _select_clause_has_wildcard(select_clause: str) -> bool:
        """Return True for SELECT * or alias.* patterns (excluding function args like count(*))."""
        return bool(re.search(r"(^|,)\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)?\*\s*(,|$)", select_clause))

    def _violates_sql_column_policy(self, sql: str) -> str | None:
        """Block SQL that can expose prohibited columns in output."""
        if not sql or not sql.strip():
            return "Policy violation: SQL is empty."

        # Remove comments to avoid false positives.
        sql_no_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
        sql_no_comments = re.sub(r"--.*?$", " ", sql_no_comments, flags=re.MULTILINE)

        for match in re.finditer(r"\bselect\b(.*?)\bfrom\b", sql_no_comments, flags=re.IGNORECASE | re.DOTALL):
            select_clause = match.group(1)
            if self._select_clause_has_wildcard(select_clause):
                return "Policy violation: do not use SELECT *; explicitly list columns and exclude budget_type."
            if re.search(r"\bbudget_type\b", select_clause, flags=re.IGNORECASE):
                return "Policy violation: do not select budget_type column."

        return None

    # ── Node 1: Plan ───────────────────────────────────────────

    def plan(self, state: AgentState) -> AgentState:
        logger.info(f"Planning for: {state['question']}")

        history_msgs = self._build_history_messages()

        # Current question
        current_msg = {
            "role": "user",
            "content": f"New question: {state['question']}\n\nCreate a brief query plan (3-5 lines).",
        }

        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            system=f"""You are a government budget analyst AI. Given a stakeholder question about Maryland's budget, create a brief query plan.

{self.full_catalog}

You have conversation history from this session. If the user references
prior results (e.g. "break that down further", "now show me by year",
"what about just DoIT?"), use the context from earlier turns to understand
what they mean.

If the question does NOT explicitly indicate follow-up, treat it as a new standalone request.
Do not inherit prior filters, category scope, or IT/non-IT lens unless the user asks.
Honor the requested scope strictly. If the user asks for a specific category,
agency, fund type, or budget lens, keep plan and filters scoped to that request.
Do not add IT-specific scope unless the user explicitly asks for IT/technology.

When mapping user concepts to column values, use ONLY the exact values
listed in the catalog above.

Identify:
1. Which column(s) to aggregate
2. Which column(s) to group by
3. Which filters to apply using EXACT values
4. Whether this explicitly references a prior question""",
            messages=history_msgs + [current_msg],
        )

        state["plan"] = response.content[0].text
        logger.info(f"Plan: {state['plan'][:200]}")
        return state

    # ── Node 2: Write SQL ──────────────────────────────────────

    def write_sql(self, state: AgentState) -> AgentState:
        logger.info("Generating SQL...")

        # Include last SQL from history for "drill down" context
        prior_sql = ""
        if self.history:
            last = self.history[-1]
            prior_sql = f"\nPrevious query SQL (for context if user is drilling down):\n{last['sql']}\n"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=f"""You are a SQL expert for DuckDB. Generate a SQL query.

CRITICAL RULES:
- ALWAYS use main_marts.fct_it_spend as the full table name.
- ONLY use column names from the catalog. Dollar columns: amount, it_amount, non_it_amount.
- NEVER use SELECT *.
- NEVER include budget_type in the SELECT output.
- For AI-enriched columns, use ONLY exact values from the catalog.
- Use WHERE is_it = true ONLY when the user explicitly asks for IT/technology scope or asks for IT-specific fields.
- If the user asks for a specific scope (category/agency/program/fund), keep filters and selected metrics strictly within that scope.
- Do NOT add unrelated comparisons or side analyses that were not requested.
- Do NOT include it_amount, non_it_amount, it_tower, or it_sub_tower unless the user explicitly requests IT detail.
- Conversation history is available for context, but do NOT carry over old filters/scope into a new question unless the user clearly asks a follow-up.
- For YoY: LAG() OVER (ORDER BY fiscal_year)
- Round percentages to 1 decimal.
- Use NULLIF to avoid division by zero.
- Unless the user explicitly asks a different order, results must be ordered by budget/spend descending.
- Do not reference fiscal years earlier than 2020 anywhere in SQL.
- For pivot requests by fiscal_year, do NOT hardcode years that have no data.
    Build year columns only from years present in the filtered dataset.
- If building a pivot manually with CASE expressions, exclude empty years
    (no rows or all null/zero amounts in that year for the requested scope).
- If the user says "break that down" or "drill into that", modify the previous query.
- Return ONLY the SQL. No explanation, no markdown fences.

{self.sql_context}
{prior_sql}""",
            messages=[{
                "role": "user",
                "content": f"Question: {state['question']}\nPlan: {state['plan']}\n\nSQL:",
            }],
        )

        sql = response.content[0].text.strip()
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[1]
        if sql.endswith("```"):
            sql = sql.rsplit("```", 1)[0]

        state["sql"] = self._ensure_default_budget_order(sql.strip(), state["question"])
        logger.info(f"SQL: {state['sql'][:300]}")
        return state

    # ── Node 3: Execute ────────────────────────────────────────

    def execute(self, state: AgentState) -> AgentState:
        logger.info("Executing query...")

        policy_error = self._violates_sql_column_policy(state["sql"])
        if policy_error:
            state["error"] = policy_error
            state["raw_results"] = {
                "columns": [],
                "rows": [],
                "row_count": 0,
                "error": policy_error,
            }
            state["formatted_table"] = f"Error: {policy_error}"
            logger.error(policy_error)
            return state

        result = self.tools.run_sql(state["sql"])

        if result["error"]:
            state["error"] = result["error"]
            state["raw_results"] = result
            state["formatted_table"] = f"Error: {result['error']}"
            logger.error(f"Query failed: {result['error']}")
        else:
            state["raw_results"] = result
            state["formatted_table"] = self.tools.format_results_as_table(result)
            state["error"] = None
            logger.info(f"Got {result['row_count']} rows")

        return state

    # ── Node 3b: Fix SQL ───────────────────────────────────────

    def fix_sql(self, state: AgentState) -> AgentState:
        logger.info(f"Fixing SQL error: {state['error']}")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=f"""You are a SQL debugger for DuckDB. The previous SQL query failed. Fix it.

Use ONLY exact column and table names, and ONLY exact category values listed:
- NEVER use SELECT *.
- NEVER include budget_type in the SELECT output.

{self.sql_context}

Return ONLY the corrected SQL. No explanation.""",
            messages=[{
                "role": "user",
                "content": f"Original SQL:\n{state['sql']}\n\nError:\n{state['error']}\n\nFixed SQL:",
            }],
        )

        sql = response.content[0].text.strip()
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[1]
        if sql.endswith("```"):
            sql = sql.rsplit("```", 1)[0]

        state["sql"] = sql.strip()
        logger.info(f"Fixed SQL: {state['sql'][:300]}")
        return state

    # ── Node 4: Narrate ────────────────────────────────────────

    def narrate(self, state: AgentState) -> AgentState:
        logger.info("Generating narrative...")

        if state.get("error"):
            state["narrative"] = f"I wasn't able to answer that question. The query failed with: {state['error']}"
            return state

        # Include brief prior context for continuity
        prior_context = ""
        if self.history:
            last = self.history[-1]
            prior_context = f"\n\nPrior question was: \"{last['question']}\"\nPrior answer summary: {last['narrative'][:200]}..."

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=f"""You are a government budget analyst presenting findings to senior stakeholders.

Given a question and query results, write a clear narrative answer.

RULES:
- Start with the direct answer in the first sentence.
- Format dollar amounts using these rules:
    - >= 1,000,000,000: use $X.XB
    - >= 1,000,000: use $X.XM
    - >= 1,000: use $X.XK
    - < 1,000: use exact dollars ($123)
    - Use 1 decimal place for K/M/B values.
    - If the user asks for exact values, include exact dollars with commas instead.
- For trends, describe direction and magnitude.
- For comparisons, highlight largest and smallest.
- If this is a follow-up question, connect your answer to the prior context.
- Use ONLY facts present in the Results table.
- Do NOT introduce IT or technology statistics unless explicitly requested or present in the returned columns.
- If the question scope is specific (for example, a single category like Health), keep the narrative strictly in that scope.
- Do not carry over prior-turn assumptions unless the current question explicitly asks to continue or refine the previous analysis.
- Keep to 2-4 paragraphs max.
- End with one actionable insight if data supports it.
- Do NOT show SQL or mention technical details.
- Write in plain clear prose, no markdown formatting.
{prior_context}""",
            messages=[{
                "role": "user",
                "content": f"Question: {state['question']}\n\nResults:\n{state['formatted_table']}",
            }],
        )

        state["narrative"] = response.content[0].text
        return state

    # ── Run the full graph ─────────────────────────────────────

    def query(self, question: str) -> AgentState:
        state: AgentState = {
            "question": question,
            "plan": "",
            "sql": "",
            "raw_results": {},
            "formatted_table": "",
            "narrative": "",
            "error": None,
        }

        state = self.plan(state)
        state = self.write_sql(state)
        state = self.execute(state)

        if state["error"]:
            state = self.fix_sql(state)
            state = self.execute(state)

        state = self.narrate(state)

        # Save to memory
        turn = self._condense_results(state)
        self._add_to_history(turn)
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
    if not api_key or api_key.startswith("sk-ant-your"):
        print("ERROR: Set ANTHROPIC_API_KEY in your .env file")
        return

    agent = BudgetQueryAgent(api_key=api_key, db_path=args.db, model=args.model)

    if args.question:
        state = agent.query(args.question)
        agent.print_answer(state)

    elif args.interactive:
        print("\n  MBTSA Budget Query Agent (with memory)")
        print("  Type a question. Follow up with 'break that down' or 'now by year'.")
        print("  Type 'clear' to reset memory, 'quit' to exit.\n")

        while True:
            question = input("  You: ").strip()
            if question.lower() in ("quit", "exit", "q"):
                break
            if question.lower() == "clear":
                agent.clear_history()
                print("  Memory cleared.\n")
                continue
            if not question:
                continue
            state = agent.query(question)
            agent.print_answer(state)

    else:
        print("Run with --question or --interactive.\n")
        print("Examples:")
        print('  --question "What is the total IT spend by tower?"')
        print('  --interactive  (supports follow-up questions)')


if __name__ == "__main__":
    main()
