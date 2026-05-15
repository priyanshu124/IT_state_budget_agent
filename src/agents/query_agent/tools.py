"""
Tools available to the LangGraph query agent.

Each tool is a function the agent can call during its reasoning.
Tools connect the agent to the DuckDB database and metric catalog.
"""

from typing import Any

import duckdb
from loguru import logger


class QueryTools:
    """Tools the agent uses to interact with the data warehouse."""

    def __init__(self, db_path: str = "mbtsa.duckdb"):
        self.db_path = db_path

    def run_sql(self, sql: str) -> dict[str, Any]:
        """Execute a SQL query against DuckDB and return results.

        Returns:
            {
                "columns": ["col1", "col2"],
                "rows": [[val1, val2], ...],
                "row_count": 10,
                "error": None
            }
        """
        logger.info(f"Executing SQL: {sql[:200]}...")

        try:
            con = duckdb.connect(self.db_path, read_only=True)
            result = con.execute(sql)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            con.close()

            # Convert to serializable types
            clean_rows = []
            for row in rows:
                clean_row = []
                for val in row:
                    if val is None:
                        clean_row.append(None)
                    elif isinstance(val, (int, float, str, bool)):
                        clean_row.append(val)
                    else:
                        clean_row.append(str(val))
                clean_rows.append(clean_row)

            logger.info(f"Query returned {len(rows)} rows, {len(columns)} columns")

            return {
                "columns": columns,
                "rows": clean_rows,
                "row_count": len(rows),
                "error": None,
            }

        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            return {
                "columns": [],
                "rows": [],
                "row_count": 0,
                "error": str(e),
            }

    def get_table_schema(self, table_name: str = "main_marts.fct_it_spend") -> str:
        """Get column names and types for a table."""
        try:
            con = duckdb.connect(self.db_path, read_only=True)
            result = con.execute(f"DESCRIBE {table_name}").fetchall()
            con.close()

            lines = [f"  {row[0]}: {row[1]}" for row in result]
            return f"Table: {table_name}\n" + "\n".join(lines)

        except Exception as e:
            return f"Error describing {table_name}: {e}"

    def get_sample_values(self, column: str, table: str = "main_marts.fct_it_spend", limit: int = 20) -> list:
        """Get distinct values for a dimension column (for filter suggestions)."""
        try:
            con = duckdb.connect(self.db_path, read_only=True)
            rows = con.execute(
                f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL ORDER BY {column} LIMIT {limit}"
            ).fetchall()
            con.close()
            return [row[0] for row in rows]

        except Exception as e:
            logger.error(f"Error getting sample values: {e}")
            return []

    def validate_columns(self, result: dict, required: list[str]) -> list[str]:
        """Return list of required column names missing from query results."""
        if not result.get("columns"):
            return required
        actual = {str(c).lower() for c in result["columns"]}
        return [c for c in required if c.lower() not in actual]

    def format_results_as_table(self, result: dict) -> str:
        """Format SQL results as a readable text table for the narrative prompt.

        For large result sets, includes all rows plus a summary block so the
        narrative covers the full data range rather than just the first N rows.
        """
        if result.get("error"):
            return f"Error: {result['error']}"

        if not result["rows"]:
            return "No results found."

        columns = result["columns"]
        rows = result["rows"]

        # Calculate column widths
        widths = [len(str(c)) for c in columns]
        for row in rows:
            for i, val in enumerate(row):
                widths[i] = max(widths[i], len(str(val) if val is not None else "null"))

        header = " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(columns))
        separator = "-+-".join("-" * w for w in widths)

        # All rows — no cap, narrative needs full picture
        formatted_rows = []
        for row in rows:
            formatted = " | ".join(
                str(val if val is not None else "null").ljust(widths[i])
                for i, val in enumerate(row)
            )
            formatted_rows.append(formatted)

        table = f"{header}\n{separator}\n" + "\n".join(formatted_rows)

        # For large result sets append a summary so Claude doesn't miss range extremes
        if len(rows) > 30:
            table += f"\n\n[Summary: {len(rows)} total rows"
            # Fiscal year range if present
            fy_idx = next((i for i, c in enumerate(columns) if str(c).lower() == "fiscal_year"), None)
            if fy_idx is not None:
                years = [r[fy_idx] for r in rows if r[fy_idx] is not None]
                if years:
                    table += f" | fiscal_year range: {min(years)}–{max(years)}"
            # Numeric column min/max
            for i, col in enumerate(columns):
                if col == "fiscal_year":
                    continue
                try:
                    vals = [float(r[i]) for r in rows if r[i] is not None]
                    if vals:
                        table += f" | {col}: min={min(vals):,.1f} max={max(vals):,.1f} total={sum(vals):,.1f}"
                except (TypeError, ValueError):
                    pass
            table += "]"

        return table