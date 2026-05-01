"""
Load classified budget data into DuckDB.
Run this BEFORE dbt run.

Usage:
    python load_data.py
    python load_data.py --input data/output/final_budget_enriched.parquet
"""

import argparse
from pathlib import Path

import duckdb


def load(input_path: str, db_path: str = "mbtsa.duckdb"):
    """Load Excel or CSV into DuckDB as the raw source table."""
    input_path = Path(input_path)
    con = duckdb.connect(db_path)

    if input_path.suffix == ".csv":
        con.execute(f"""
            CREATE OR REPLACE TABLE budget_line_items AS
            SELECT * FROM read_csv_auto(
                '{input_path}',
                all_varchar = true,
                sample_size = -1
            )
        """)
    elif input_path.suffix == ".parquet":
        con.execute(f"""
            CREATE OR REPLACE TABLE budget_line_items AS
            SELECT * FROM read_parquet('{input_path}')
        """)
    else:
        raise ValueError(f"Unsupported file type: {input_path.suffix}")

    count = con.execute("SELECT count(*) FROM budget_line_items").fetchone()[0]
    cols = con.execute("DESCRIBE budget_line_items").fetchall()

    print(f"Loaded {count:,} rows, {len(cols)} columns into {db_path}")
    print(f"Table: budget_line_items")

    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="data/output/final_budget_enriched.parquet",
        help="Path to Excel, CSV, or Parquet",
    )
    parser.add_argument("--db", default="dbt-sql/mbtsa_work.duckdb", help="DuckDB database path")
    args = parser.parse_args()
    load(args.input, args.db)
