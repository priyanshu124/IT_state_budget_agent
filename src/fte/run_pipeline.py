"""One-command FTE pipeline runner.

This is the single endpoint for the FTE dataset:
load raw data -> clean -> write parquet -> load DuckDB table for dbt.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
from loguru import logger

from src.fte.cleaning import clean_fte_df
from src.fte.load import load_fte_data
from src.utils.config import DATA_DIR, DATA_PROCESSED
from src.utils.logging import setup_logging


def _write_duckdb_table(parquet_path: Path, db_path: Path, table_name: str) -> None:
    """Load the cleaned parquet into DuckDB as a source table."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT * FROM read_parquet('{parquet_path.as_posix()}')
            """
        )
        row_count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        logger.info("Loaded {} rows into DuckDB table {}", row_count, table_name)
    finally:
        con.close()


def run_fte_pipeline(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    db_path: str | Path | None = None,
    table_name: str = "fte_line_items",
) -> dict[str, Path]:
    """Run the FTE pipeline and persist parquet + DuckDB outputs."""

    source_path = Path(input_path)
    out_dir = Path(output_dir) if output_dir else (DATA_PROCESSED / "fte")
    out_dir.mkdir(parents=True, exist_ok=True)

    cleaned_path = out_dir / f"{source_path.stem}_cleaned.parquet"
    logger.info("FTE pipeline start: {}", source_path)

    raw_df = load_fte_data(source_path)
    cleaned_df = clean_fte_df(raw_df)
    cleaned_df.write_parquet(cleaned_path)
    logger.info("Saved cleaned FTE parquet: {}", cleaned_path)

    if db_path:
        _write_duckdb_table(cleaned_path, Path(db_path), table_name)

    logger.info("FTE pipeline complete | rows={} cols={}", cleaned_df.height, cleaned_df.width)

    return {"cleaned": cleaned_path}


def main() -> None:
    """CLI entry point for the FTE pipeline."""

    parser = argparse.ArgumentParser(description="Run the FTE pipeline and load DuckDB")
    parser.add_argument(
        "--input",
        default=str(DATA_DIR / "raw" / "fte" / "*.csv"),
        help="Path to the raw FTE CSV/XLSX/Parquet file",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DATA_PROCESSED / "fte"),
        help="Directory for cleaned parquet output",
    )
    parser.add_argument(
        "--db",
        default=str(Path("dbt-sql") / "mbtsa_work.duckdb"),
        help="DuckDB database path to load the cleaned table into",
    )
    parser.add_argument(
        "--table",
        default="fte_line_items",
        help="DuckDB table name to create or replace",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    )

    args = parser.parse_args()
    setup_logging(level=args.log_level)

    run_fte_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        db_path=args.db,
        table_name=args.table,
    )


if __name__ == "__main__":
    main()