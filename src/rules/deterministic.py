"""
Deterministic Rules Engine for TBM Classification.

This is the "free accuracy" layer — no LLM needed.
Classifies rows based on hardcoded agency codes and subobject mappings.
"""

import polars as pl
from loguru import logger

from src.utils.config import get_config
from src.utils.schemas import ClassificationSource, TBMCostPool


def apply_deterministic_rules(df: pl.DataFrame, config: dict | None = None) -> pl.DataFrame:
    """
    Apply deterministic classification rules to a Polars DataFrame.

    Adds columns: is_it_related, tbm_cost_pool, classification_source

    Args:
        df: Raw budget DataFrame with standardized column names.
        config: TBM config dict. Loaded from YAML if not provided.

    Returns:
        DataFrame with classification columns added.
    """
    if config is None:
        config = get_config()

    logger.info(f"Applying deterministic rules to {df.height:,} rows")

    # Initialize classification columns
    df = df.with_columns(
        pl.lit(None).cast(pl.Boolean).alias("is_it_related"),
        pl.lit(None).cast(pl.Utf8).alias("tbm_cost_pool"),
        pl.lit(None).cast(pl.Utf8).alias("classification_source"),
    )

    # --- Rule 1: Known IT Agencies (Fast-Track) ---
    known_agency_codes = [
        a["agency_code"] for a in config.get("known_it_agencies", [])
    ]

    if known_agency_codes:
        agency_col = _find_col(df, ["agency_code", "unit_code"])
        if agency_col:
            df = df.with_columns(
                pl.when(pl.col(agency_col).is_in(known_agency_codes))
                .then(pl.lit(True))
                .otherwise(pl.col("is_it_related"))
                .alias("is_it_related"),

                pl.when(pl.col(agency_col).is_in(known_agency_codes))
                .then(pl.lit(ClassificationSource.DETERMINISTIC_AGENCY.value))
                .otherwise(pl.col("classification_source"))
                .alias("classification_source"),
            )
            n_agency = df.filter(
                pl.col("classification_source") == ClassificationSource.DETERMINISTIC_AGENCY.value
            ).height
            logger.info(f"  Rule 1 (Known IT Agency): {n_agency:,} rows classified")

    # --- Rule 2: Subobject Code → Cost Pool ---
    cost_pool_map = config.get("cost_pool_mappings", {})
    if cost_pool_map:
        subobject_col = _find_col(df, [
            "comptroller_subobject_name", "subobject_name", "subobject"
        ])
        if subobject_col:
            # Build mapping expressions
            cost_pool_expr = pl.col(subobject_col)  # start value doesn't matter
            is_it_expr = pl.col("is_it_related")
            source_expr = pl.col("classification_source")

            # Chain when/then for each mapping
            for subobj_name, pool in cost_pool_map.items():
                condition = pl.col(subobject_col).str.to_lowercase() == subobj_name.lower()

                cost_pool_expr = (
                    pl.when(condition & pl.col("tbm_cost_pool").is_null())
                    .then(pl.lit(pool))
                    .otherwise(pl.col("tbm_cost_pool"))
                )

                is_it_expr = (
                    pl.when(condition & pl.col("is_it_related").is_null())
                    .then(pl.lit(True))
                    .otherwise(pl.col("is_it_related"))
                )

                source_expr = (
                    pl.when(condition & pl.col("classification_source").is_null())
                    .then(pl.lit(ClassificationSource.DETERMINISTIC_SUBOBJECT.value))
                    .otherwise(pl.col("classification_source"))
                )

                # Apply iteratively (Polars evaluates lazily)
                df = df.with_columns(
                    cost_pool_expr.alias("tbm_cost_pool"),
                    is_it_expr.alias("is_it_related"),
                    source_expr.alias("classification_source"),
                )

            n_subobj = df.filter(
                pl.col("classification_source") == ClassificationSource.DETERMINISTIC_SUBOBJECT.value
            ).height
            logger.info(f"  Rule 2 (Subobject → Cost Pool): {n_subobj:,} rows classified")

    # --- Summary ---
    n_classified = df.filter(pl.col("is_it_related").is_not_null()).height
    n_remaining = df.height - n_classified
    logger.info(
        f"  Deterministic total: {n_classified:,} classified, "
        f"{n_remaining:,} remaining ({n_remaining/df.height*100:.1f}%)"
    )

    return df


def get_classification_summary(df: pl.DataFrame) -> pl.DataFrame:
    """Get a summary of classifications by source."""
    return (
        df.group_by("classification_source")
        .agg(
            pl.len().alias("row_count"),
            pl.col("is_it_related").sum().alias("it_related_count"),
        )
        .sort("row_count", descending=True)
    )


def _find_col(df: pl.DataFrame, candidates: list[str]) -> str | None:
    """Find the first matching column name (case-insensitive)."""
    cols_lower = {c.lower().replace(" ", "_"): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in cols_lower:
            return cols_lower[candidate.lower()]
    return None
