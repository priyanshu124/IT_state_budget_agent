"""Cleaning utilities for FTE records."""

from __future__ import annotations

import polars as pl
from loguru import logger


def clean_fte_df(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize the imported FTE table for downstream joins and rollups."""

    logger.info("cleaning_fte_dataframe", rows=len(df), columns=len(df.columns))

    result = df

    # Keep only the columns we know how to use downstream.
    required_columns = [
        "agency_code",
        "unit_code",
        "program_code",
        "fte_count",
        "fiscal_year",
        "organization_code",
        "agency_name",
        "unit_name",
        "program_name",
    ]
    existing_columns = [column for column in required_columns if column in result.columns]
    if existing_columns:
        result = result.select(existing_columns)

    string_columns = [
        column for column, dtype in zip(result.columns, result.dtypes)
        if dtype in (pl.Utf8, pl.String)
    ]
    if string_columns:
        result = result.with_columns([pl.col(column).str.strip_chars() for column in string_columns])

    if "fiscal_year" in result.columns:
        result = result.with_columns(
            pl.col("fiscal_year").cast(pl.Int32, strict=False).alias("fiscal_year")
        )

    if "fte_count" in result.columns:
        result = result.with_columns(
            pl.col("fte_count")
            .cast(pl.Utf8)
            .str.replace_all(",", "", literal=True)
            .cast(pl.Float64, strict=False)
            .fill_null(0.0)
            .alias("fte_count")
        )

    for column in ["agency_code", "unit_code", "program_code", "organization_code"]:
        if column in result.columns:
            result = result.with_columns(pl.col(column).cast(pl.Utf8).str.strip_chars().alias(column))

    logger.info("fte_cleaning_complete", rows=len(result))
    return result