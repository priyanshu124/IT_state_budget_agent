import polars as pl
from loguru import logger

# -------------------------------------------------
# Deduplication Engine
# -------------------------------------------------

# Fields that form the dedup key
DEDUP_KEY_FIELDS = [
    "agency_code",
    "agency_name",
    "unit_code",
    "unit_name",
    "program_code",
    "program_name",
    "subprogram_code",
    "subprogram_name",
    "object_code",
    "object_name",
    "comptroller_subobject_code",
    "comptroller_subobject_name",
    "organization_code",
    "organization_sub_code",
]

# Fields that ride along (not part of key, but kept for context)
CONTEXT_FIELDS = [
    "description",
]


def latest_subprogram_subobject(df: pl.DataFrame) -> pl.DataFrame:
    """
    Build a DataFrame with DEDUP_KEY_FIELDS + CONTEXT_FIELDS, unique by
    (subprogram_code, comptroller_subobject_code), keeping the latest fiscal year.

    Supports both snake_case and legacy non-underscore column variants.
    """
    subprogram_col = "subprogram_code"
    comptroller_col = "comptroller_subobject_code"
    fiscal_year_col = "fiscal_year"

    missing_required = [
        col for col in [subprogram_col, comptroller_col, fiscal_year_col]
        if col not in df.columns
    ]
    if missing_required:
        raise ValueError(
            "Missing required columns for latest-record dedup: "
            + ", ".join(missing_required)
        )

    selected_cols = [c for c in DEDUP_KEY_FIELDS + CONTEXT_FIELDS if c in df.columns]

    # Project first to the minimum needed dataset, keep fiscal_year only for ranking.
    working_cols = selected_cols + [fiscal_year_col]
    projected_df = df.select(working_cols)

    latest_df = (
        projected_df
        .with_columns(pl.col(fiscal_year_col).cast(pl.Int32, strict=False).alias("_fy_sort"))
        .sort(by=["_fy_sort"], descending=[True], nulls_last=True)
        .unique(subset=[subprogram_col, comptroller_col], keep="first")
        .drop(["_fy_sort", fiscal_year_col])
    )

    logger.info(
        "latest_records_built",
        input_rows=df.height,
        output_rows=latest_df.height,
        subprogram_col=subprogram_col,
        comptroller_col=comptroller_col,
        fiscal_year_col=fiscal_year_col,
    )
    return latest_df


def reattach_classifications(
    classified_dedup_df: pl.DataFrame,
    original_df: pl.DataFrame,
) -> pl.DataFrame:
    """
    Join classification results back to the original raw rows.

    Args:
        classified_dedup_df: Dedup rows with classification columns
        original_df: Original raw DataFrame (with row_id)

    Returns:
        Original rows with TBM classification columns attached
    """
    join_keys = ["subprogram_code", "comptroller_subobject_code"]

    # Extract only classification columns from dedup results
    classification_cols = [
         "is_it_related", "tbm_cost_pool", "tbm_it_tower",
        "classification_source", "agent_route", "confidence",
        "needs_human_review", "agent_reasoning",
    ]
    available_cols = [c for c in classification_cols if c in classified_dedup_df.columns]

    classifications = (
        classified_dedup_df
        .select(join_keys + available_cols)
        .unique(subset=join_keys, keep="first")
    )

    # Join classifications directly on natural keys.
    result = (
        original_df
        .join(classifications, on=join_keys, how="left")
    )

    logger.info(
        f"Reattachment complete: {result.height} rows with classifications"
    )

    return result
