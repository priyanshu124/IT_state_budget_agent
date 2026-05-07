"""FTE ingestion helpers.

This module keeps the raw FTE file import separate from the budget pipeline so
the dataset can be cleaned and enriched independently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import polars as pl
from loguru import logger

from src.utils.data_paths import resolve_input_path

FTE_COLUMN_ALIASES = {
    "Agency Code": "agency_code",
    "Unit Code": "unit_code",
    "Program Code": "program_code",
    "Count": "fte_count",
    "Fiscal Year": "fiscal_year",
    "Organization Code": "organization_code",
    "Agency Name": "agency_name",
    "Unit Name": "unit_name",
    "Program Name": "program_name",
}

_CSV_SCHEMA_OVERRIDES = {
    "Agency Code": pl.Utf8,
    "Unit Code": pl.Utf8,
    "Program Code": pl.Utf8,
    "Organization Code": pl.Utf8,
    "Fiscal Year": pl.Int32,
    "Count": pl.Utf8,
}


def load_fte_data(filepath: str | Path) -> pl.DataFrame:
    """Load an FTE file and normalize the raw headers to snake_case."""

    filepath = resolve_input_path(filepath)
    logger.info("Loading FTE data from {}", filepath)

    if filepath.suffix.lower() == ".csv":
        df = pl.read_csv(filepath, infer_schema_length=10000, schema_overrides=_CSV_SCHEMA_OVERRIDES)
    elif filepath.suffix.lower() in {".xlsx", ".xls"}:
        df = pl.read_excel(filepath)
    elif filepath.suffix.lower() == ".parquet":
        df = pl.read_parquet(filepath)
    else:
        raise ValueError(f"Unsupported FTE file format: {filepath.suffix}")

    logger.info("Loaded FTE data: {} rows x {} columns", df.height, df.width)
    return rename_columns_by_aliases(df, FTE_COLUMN_ALIASES)


def rename_columns_by_aliases(
    df: pl.DataFrame,
    column_aliases: Optional[dict[str, str]] = None,
) -> pl.DataFrame:
    """Rename raw FTE headers to the canonical pipeline names."""

    aliases = column_aliases or FTE_COLUMN_ALIASES
    rename_map = {column: aliases[column] for column in df.columns if column in aliases}

    if not rename_map:
        logger.warning("No matching FTE source columns found in alias map; skipping rename")
        return df

    renamed_df = df.rename(rename_map)
    logger.info("Renamed {} FTE columns using alias mapping", len(rename_map))
    return renamed_df