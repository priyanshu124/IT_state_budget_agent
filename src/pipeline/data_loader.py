"""
Data Ingestion and Deduplication Engine.

Phase 1 of the pipeline:
- Load raw CSV/Excel budget data
- Extract essential columns
- Build dedup keys and compress
- Provide reattachment mapping
"""

import hashlib
from pathlib import Path
from typing import Optional

import polars as pl
from loguru import logger

from src.pipeline.data_cleaner import clean_df
from src.utils.data_paths import resolve_input_path
from src.utils.config import DATA_DIR

COLUMN_ALIASES = {
# Canonical column rename map: original CSV header → snake_case DB column
    "Fiscal Year": "fiscal_year",
    "Agency Code": "agency_code",
    "Agency Name": "agency_name",
    "Unit Code": "unit_code",
    "Unit Name": "unit_name",
    "Program Code": "program_code",
    "Program Name": "program_name",
    "Subprogram Code": "subprogram_code",
    "Subprogram Name": "subprogram_name",
    "Object Code": "object_code",
    "Object Name": "object_name",
    "Comptroller Subobject Code": "comptroller_subobject_code",
    "Comptroller Subobject Name": "comptroller_subobject_name",
    "Agency Subobject Code": "agency_subobject_code",
    "Agency Subobject Name": "agency_subobject_name",
    "Fund Type Name": "fund_type_name",
    "Budget": "budget",
    "Type": "type",
    "Organization Code": "organization_code",
    "Organization Sub Code": "organization_sub_code",
    "Description": "description",
    "Category": "category",
    "Category Title": "category_title",
}

_CSV_SCHEMA_OVERRIDES = {
    column: pl.Utf8
    for column in [
        "Agency Subobject Code",
    ]
}
# -------------------------------------------------
# Data Loading
# -------------------------------------------------

def load_budget_data(
    filepath: str | Path,
) -> pl.DataFrame:
    """
    Load budget data from CSV file.

    Args:
        filepath: Path to CSV file

    Returns:
        Polars DataFrame with normalized column names
    """
    filepath = resolve_input_path(filepath)

    logger.info(f"Loading data from {filepath}")

    if filepath.suffix.lower() == ".csv":
        df = pl.read_csv(filepath, infer_schema_length=10000, schema_overrides=_CSV_SCHEMA_OVERRIDES)

    logger.info(f"Loaded {df.height} rows x {df.width} columns")
    df = rename_columns_by_aliases(df, COLUMN_ALIASES)
    df = clean_df(df)
    return df


def rename_columns_by_aliases(
    df: pl.DataFrame,
    column_aliases: Optional[dict[str, str]] = None,
) -> pl.DataFrame:
    """
    Rename incoming raw columns to canonical names using an alias dictionary.

    Args:
        df: Input DataFrame with raw source headers.
        column_aliases: Mapping of raw header -> canonical column name.

    Returns:
        DataFrame with matched columns renamed.
    """

    aliases = column_aliases or COLUMN_ALIASES
    rename_map = {col: aliases[col] for col in df.columns if col in aliases}

    if not rename_map:
        logger.warning("No matching source columns found in alias map; skipping rename")
        return df

    renamed_df = df.rename(rename_map)
    logger.info(f"Renamed {len(rename_map)} columns using alias mapping")
    return renamed_df



def _write_parquet(df: pl.DataFrame, output_path: Path) -> None:
    """Write the dataframe to Parquet, ensuring directories exist."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output_path)


