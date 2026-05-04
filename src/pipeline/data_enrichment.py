import polars as pl
from loguru import logger
import argparse
from pathlib import Path

from src.utils.config import DATA_DIR, DATA_PROCESSED
from src.utils.logging import setup_logging

SUBPROGRAM_KEY = "organization_sub_code"
COST_POOL_KEY = "comptroller_subobject_code"


def _dedup_lookup(df: pl.DataFrame, key: str) -> pl.DataFrame:
    """Return one lookup row per join key while preserving all columns."""
    if key not in df.columns:
        raise ValueError(f"Missing join key '{key}' in classified dataframe")

    return df.unique(subset=[key], keep="first")


def _normalize_key_to_string(df: pl.DataFrame, key: str) -> pl.DataFrame:
    """Cast join key to Utf8 for stable joins across mixed source schemas."""
    if key not in df.columns:
        raise ValueError(f"Missing join key '{key}' in dataframe")

    return df.with_columns(pl.col(key).cast(pl.Utf8))


def _normalize_subobject_code(df: pl.DataFrame, key: str) -> pl.DataFrame:
    """Normalize subobject code values so padded and unpadded forms match."""
    if key not in df.columns:
        raise ValueError(f"Missing join key '{key}' in dataframe")

    return df.with_columns(
        pl.when(pl.col(key).is_null())
        .then(None)
        .otherwise(
            pl.col(key)
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.replace(r"\.0$", "")
            .str.pad_start(4, "0")
        )
        .alias(key)
    )


def _read_table(path: str | Path) -> pl.DataFrame:
    """Read CSV or Parquet based on extension."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pl.read_csv(path)
    if suffix == ".parquet":
        return pl.read_parquet(path)
    raise ValueError(f"Unsupported file format for {path}. Use .csv or .parquet")


def _write_table(df: pl.DataFrame, path: str | Path) -> Path:
    """Write CSV or Parquet based on extension."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            df.write_csv(path)
        elif suffix == ".parquet":
            df.write_parquet(path)
        else:
            raise ValueError(f"Unsupported output format for {path}. Use .csv or .parquet")
    except OSError:
        fallback = path.with_name(f"{path.stem}_enriched{path.suffix}")
        logger.warning("Output path is locked. Writing fallback file: {}", fallback)
        if suffix == ".csv":
            df.write_csv(fallback)
        elif suffix == ".parquet":
            df.write_parquet(fallback)
        path = fallback

    return path


def _count_matches(df: pl.DataFrame, candidate_cols: list[str]) -> int:
    """Return matched row count using first available non-key classified column."""
    for col in candidate_cols:
        if col in df.columns:
            return df.filter(pl.col(col).is_not_null()).height
    return 0

# ── Reattachment ───────────────────────────────────────────────

def reattach_subprogram_classifications(
    classified_df: pl.DataFrame,
    original_df: pl.DataFrame,
) -> pl.DataFrame:
    """Join subprogram classifications back to all original rows by organization_sub_code.

    Args:
        classified_df: Deduped subprograms with tower classification columns.
        original_df: Original raw DataFrame with all rows.

    Returns:
        All original rows with tower classification columns attached where codes match.
        Preserves all original metadata (agency_name, subprogram_name, etc.) for non-matched rows.
    """
    classifications = _normalize_key_to_string(
        _dedup_lookup(classified_df, SUBPROGRAM_KEY),
        SUBPROGRAM_KEY,
    )
    original_df = _normalize_key_to_string(original_df, SUBPROGRAM_KEY)
    
    # Remove any existing tower classification columns from original to avoid duplication
    existing_tower_cols = [c for c in original_df.columns if c in ["tower", "sub_tower", "confidence", "tower_right", "sub_tower_right", "confidence_right"]]
    if existing_tower_cols:
        original_df = original_df.drop(existing_tower_cols)
    
    # Only take tower classification columns, not the metadata columns.
    # Metadata (agency_name, subprogram_name, etc.) must come from the original file
    # to preserve data for non-matched rows (is_it=false).
    tower_cols = [c for c in classifications.columns if c in ["tower", "sub_tower", "confidence"]]
    classifications_tower_only = classifications.select([SUBPROGRAM_KEY] + tower_cols)

    # Left join keeps all original rows and only adds tower columns where codes match.
    result = original_df.join(classifications_tower_only, on=SUBPROGRAM_KEY, how="left")

    # If classifier marked row as NOT_IT or no tower-classification row matched,
    # clear IT classification fields.
    if "tower" in result.columns:
        no_match_expr = pl.col("tower").is_null()
        not_it_expr = pl.col("tower").cast(pl.Utf8, strict=False).str.to_uppercase() == "NOT_IT"
        clear_it_expr = no_match_expr | not_it_expr
        exprs: list[pl.Expr] = []

        if "is_it" in result.columns:
            exprs.append(
                pl.when(clear_it_expr)
                .then(pl.lit(False))
                .otherwise(pl.col("is_it"))
                .alias("is_it")
            )

        if "shadow_it_reason" in result.columns:
            exprs.append(
                pl.when(clear_it_expr)
                .then(pl.lit(None).cast(pl.Utf8))
                .otherwise(pl.col("shadow_it_reason"))
                .alias("shadow_it_reason")
            )

        for col in ["it_designation", "tower", "sub_tower", "confidence"]:
            if col in result.columns:
                exprs.append(
                    pl.when(clear_it_expr)
                    .then(pl.lit(None).cast(result.schema[col]))
                    .otherwise(pl.col(col))
                    .alias(col)
                )

        if exprs:
            result = result.with_columns(exprs)

    matched = _count_matches(result, tower_cols)
    logger.info(
        f"Subprogram reattach: {result.height:,} rows, "
        f"{matched:,} matched classifications"
    )
    return result


def reattach_cost_pool_classifications(
    classified_df: pl.DataFrame,
    original_df: pl.DataFrame,
) -> pl.DataFrame:
    """Join cost pool classifications back to all original rows.

    Args:
        classified_df: Deduped subobjects with cost pool columns.
        original_df: Original raw DataFrame with all rows.

    Returns:
        Original rows with cost pool columns attached.
    """
    classifications = _normalize_subobject_code(
        _normalize_key_to_string(_dedup_lookup(classified_df, COST_POOL_KEY), COST_POOL_KEY),
        COST_POOL_KEY,
    )
    original_df = _normalize_subobject_code(
        _normalize_key_to_string(original_df, COST_POOL_KEY),
        COST_POOL_KEY,
    )
    
    # Ensure comptroller_subobject_code is padded to 4 characters in processed file
    if COST_POOL_KEY in original_df.columns:
        original_df = original_df.with_columns(
            pl.col(COST_POOL_KEY).cast(pl.Utf8).str.pad_start(4, "0").alias(COST_POOL_KEY)
        )
    # Only bring the requested cost-pool columns from mapper output.
    requested_cols = [
        c for c in ["cost_pool", "cost_sub_pool"] if c in classifications.columns
    ]
    classifications = classifications.select([COST_POOL_KEY] + requested_cols)
    classification_cols = requested_cols

    # Prefer classified values for overlapping column names.
    overlaps = [c for c in classification_cols if c in original_df.columns]
    base = original_df.drop(overlaps) if overlaps else original_df

    result = base.join(classifications, on=COST_POOL_KEY, how="left")
    
    # Ensure comptroller_subobject_code remains as padded string in final result
    if COST_POOL_KEY in result.columns:
        result = result.with_columns(
            pl.col(COST_POOL_KEY).cast(pl.Utf8).str.pad_start(4, "0").alias(COST_POOL_KEY)
        )

    matched = _count_matches(result, classification_cols)
    logger.info(
        f"Cost pool reattach: {result.height:,} rows, "
        f"{matched:,} matched classifications"
    )
    return result


def main() -> None:
    """CLI entry point for enriching processed subprogram and subobject files."""
    parser = argparse.ArgumentParser(
        description=(
            "Left-join tower/cost-pool outputs into processed subprogram/subobject datasets"
        )
    )
    parser.add_argument(
        "--subprograms-input",
        type=str,
        default=str(DATA_PROCESSED / "subprograms.csv"),
        help="Processed subprograms CSV/Parquet to enrich",
    )
    parser.add_argument(
        "--subprogram-classified",
        type=str,
        default=str(DATA_DIR / "output" / "tower_classifications.csv"),
        help="Tower-classifier output (.csv/.parquet)",
    )
    parser.add_argument(
        "--subprograms-output",
        type=str,
        default=str(DATA_PROCESSED / "subprograms.csv"),
        help="Output path for enriched subprograms (.csv/.parquet)",
    )
    parser.add_argument(
        "--subobjects-input",
        type=str,
        default=str(DATA_PROCESSED / "subobject_codes.csv"),
        help="Processed subobject codes CSV/Parquet to enrich",
    )
    parser.add_argument(
        "--cost-pool-classified",
        type=str,
        default=str(DATA_DIR / "output" / "cost_pool_mappings.csv"),
        help="Cost-pool mapper output (.csv/.parquet)",
    )
    parser.add_argument(
        "--subobjects-output",
        type=str,
        default=str(DATA_PROCESSED / "subobject_codes.csv"),
        help="Output path for enriched subobject codes (.csv/.parquet)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    )

    args = parser.parse_args()
    setup_logging(level=args.log_level)

    # Enrich subprograms with tower columns only.
    subprogram_classified_df = _read_table(args.subprogram_classified)
    original_subprograms_df = _read_table(args.subprograms_input)
    subprograms_enriched = reattach_subprogram_classifications(
        subprogram_classified_df,
        original_subprograms_df,
    )
    subprogram_out = _write_table(subprograms_enriched, args.subprograms_output)

    # Enrich subobject codes with cost-pool columns only.
    cost_pool_classified_df = _read_table(args.cost_pool_classified)
    original_subobjects_df = _read_table(args.subobjects_input)
    subobjects_enriched = reattach_cost_pool_classifications(cost_pool_classified_df, original_subobjects_df)
    subobjects_out = _write_table(subobjects_enriched, args.subobjects_output)

    logger.info(
        "Enriched outputs saved: subprograms={} (rows={}, cols={}), subobjects={} (rows={}, cols={})",
        subprogram_out,
        subprograms_enriched.height,
        subprograms_enriched.width,
        subobjects_out,
        subobjects_enriched.height,
        subobjects_enriched.width,
    )


if __name__ == "__main__":
    main()
