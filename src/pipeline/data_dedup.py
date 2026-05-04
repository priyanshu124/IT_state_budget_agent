"""
Deduplication Engine
=====================
Two dedup functions for the two classification paths:

1. Subprogram dedup (for tower classification):
   - Unique key: organization_sub_code
   - Keeps latest fiscal year record
   - Output feeds Agent 3 (Tower Classifier)

2. Cost pool dedup (for cost pool mapping):
   - Unique key: comptroller_subobject_code
   - Keeps latest fiscal year record
   - Output feeds Agent 2 (Cost Pool Mapper)

3. Reattachment: joins classifications back to all original rows.
"""

import argparse
from pathlib import Path

import polars as pl
from loguru import logger

from src.utils.config import DATA_PROCESSED
from src.utils.logging import setup_logging


# ── Subprogram Fields ──────────────────────────────────────────

SUBPROGRAM_KEY = "organization_sub_code"

SUBPROGRAM_FIELDS = [
    
    "organization_sub_code",
    "organization_code",
    "agency_code",
    "agency_name",
    "unit_code",
    "unit_name",
    "program_code",
    "program_name",
    "subprogram_code",
    "subprogram_name",
    "description",
    "category",
    "category_title"
]

# ── Cost Pool Fields ───────────────────────────────────────────

COST_POOL_KEY = "comptroller_subobject_code"

COST_POOL_FIELDS = [
    "object_code",
    "object_name",
    "comptroller_subobject_code",
    "comptroller_subobject_name",
]


# ── Subprogram Dedup ──────────────────────────────────────────

def dedup_subprograms(df: pl.DataFrame) -> pl.DataFrame:
    """Deduplicate to unique subprograms by organization_sub_code.

    Keeps the record from the latest fiscal year for each
    organization_sub_code. This gives the most current program
    name and description.

    Args:
        df: Raw budget DataFrame with all rows.

    Returns:
        One row per unique organization_sub_code with subprogram
        metadata fields.
    """
    fiscal_year_col = "fiscal_year"

    if SUBPROGRAM_KEY not in df.columns:
        raise ValueError(f"Missing required column: {SUBPROGRAM_KEY}")
    if fiscal_year_col not in df.columns:
        raise ValueError(f"Missing required column: {fiscal_year_col}")

    available = [c for c in SUBPROGRAM_FIELDS if c in df.columns]
    working_cols = [fiscal_year_col, *available]

    result = (
        df.select(working_cols)
        .with_columns(
            pl.when(pl.col(SUBPROGRAM_KEY).is_null())
            .then(pl.col("organization_code"))
            .otherwise(pl.col(SUBPROGRAM_KEY))
            .alias(SUBPROGRAM_KEY)
        )
        .with_columns(
            pl.col(fiscal_year_col).cast(pl.Int32, strict=False).alias("_fy_sort")
        )
        .sort(by=["_fy_sort"], descending=[True], nulls_last=True)
        .unique(subset=[SUBPROGRAM_KEY], keep="first")
        .drop(["_fy_sort", fiscal_year_col])
    )

    # Keep CSV row order deterministic for downstream joins/reviews.
    subprogram_sort_cols = [
        c for c in ["organization_sub_code", "organization_code"] if c in result.columns
    ]
    if subprogram_sort_cols:
        result = result.sort(by=subprogram_sort_cols, nulls_last=True)

    logger.info(
        f"Subprogram dedup: {df.height:,} rows → {result.height:,} unique "
        f"by {SUBPROGRAM_KEY} (latest fiscal year)"
    )
    return result


# ── Cost Pool Dedup ────────────────────────────────────────────

def dedup_cost_pools(df: pl.DataFrame) -> pl.DataFrame:
    """Deduplicate to unique subobject codes for cost pool mapping.

    Keeps the record from the latest fiscal year for each
    comptroller_subobject_code. This gives the most current
    subobject name.

    Args:
        df: Raw budget DataFrame with all rows.

    Returns:
        One row per unique comptroller_subobject_code with
        object/subobject metadata.
    """
    fiscal_year_col = "fiscal_year"

    if COST_POOL_KEY not in df.columns:
        raise ValueError(f"Missing required column: {COST_POOL_KEY}")
    if fiscal_year_col not in df.columns:
        raise ValueError(f"Missing required column: {fiscal_year_col}")

    available = [c for c in COST_POOL_FIELDS if c in df.columns]
    working_cols = [fiscal_year_col, *available]

    result = (
        df.select(working_cols)
        .with_columns(
            pl.col(fiscal_year_col).cast(pl.Int32, strict=False).alias("_fy_sort")
        )
        # Fallback: use object_code when comptroller_subobject_code is NULL
        .with_columns(
            pl.when(pl.col(COST_POOL_KEY).is_null())
            .then(pl.col("object_code"))
            .otherwise(pl.col(COST_POOL_KEY))
            .alias("_dedup_key")
        )
        .sort(by=["_fy_sort"], descending=[True], nulls_last=True)
        .unique(subset=["_dedup_key"], keep="first")
        .drop(["_fy_sort", "_dedup_key", fiscal_year_col])
    )

    # Keep CSV row order deterministic for downstream joins/reviews.
    cost_pool_sort_cols = [
        c for c in ["object_code", "comptroller_subobject_code"] if c in result.columns
    ]
    if cost_pool_sort_cols:
        result = result.sort(by=cost_pool_sort_cols, nulls_last=True)

    logger.info(
        f"Cost pool dedup: {df.height:,} rows → {result.height:,} unique "
        f"by {COST_POOL_KEY} (latest fiscal year)"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run dedup outputs from cleaned budget parquet"
    )
    parser.add_argument(
        "--input",
        default=str(DATA_PROCESSED / "2027_cleaned.parquet"),
        help="Path to cleaned parquet input",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DATA_PROCESSED),
        help="Directory where dedup outputs are written",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    )

    args = parser.parse_args()
    setup_logging(level=args.log_level)

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading cleaned dataset: {input_path}")
    df = pl.read_parquet(input_path)

    subprograms_df = dedup_subprograms(df)
    subobjects_df = dedup_cost_pools(df)

    subprograms_out = output_dir / "subprograms.csv"
    subobjects_out = output_dir / "subobjects.csv"
    
    subprograms_df.write_csv(subprograms_out)
    subobjects_df.write_csv(subobjects_out)

    logger.info(
        "Dedup complete | input_rows={} subprogram_rows={}", \
        "cost_pool_rows={}",
        df.height,
        subprograms_df.height,
        subobjects_df.height,
    )
    logger.info(f"Saved subprogram dedup: {subprograms_out}")
    #logger.info(f"Saved cost pool dedup: {subobjects_out}")


if __name__ == "__main__":
    main()


