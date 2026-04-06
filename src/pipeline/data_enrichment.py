import polars as pl
from loguru import logger
import argparse
from pathlib import Path
from datetime import datetime

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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback = path.with_name(f"{path.stem}_{timestamp}{path.suffix}")
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
    """Join subprogram classifications (tower, is_it) back to all original rows.

    Args:
        classified_df: Deduped subprograms with tower classification columns.
        original_df: Original raw DataFrame with all rows.

    Returns:
        Original rows with tower classification columns attached.
    """
    classifications = _normalize_key_to_string(_dedup_lookup(classified_df, SUBPROGRAM_KEY), SUBPROGRAM_KEY)
    original_df = _normalize_key_to_string(original_df, SUBPROGRAM_KEY)
    classification_cols = [c for c in classifications.columns if c != SUBPROGRAM_KEY]

    # Prefer classified values for overlapping column names.
    overlaps = [c for c in classification_cols if c in original_df.columns]
    base = original_df.drop(overlaps) if overlaps else original_df

    result = base.join(classifications, on=SUBPROGRAM_KEY, how="left")

    matched = _count_matches(result, classification_cols)
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
    classification_cols = [c for c in classifications.columns if c != COST_POOL_KEY]

    # Prefer classified values for overlapping column names.
    overlaps = [c for c in classification_cols if c in original_df.columns]
    base = original_df.drop(overlaps) if overlaps else original_df

    result = base.join(classifications, on=COST_POOL_KEY, how="left")

    matched = _count_matches(result, classification_cols)
    logger.info(
        f"Cost pool reattach: {result.height:,} rows, "
        f"{matched:,} matched classifications"
    )
    return result


def reattach_all(
    subprogram_classified_df: pl.DataFrame,
    cost_pool_classified_df: pl.DataFrame,
    original_df: pl.DataFrame,
) -> pl.DataFrame:
    """Join both subprogram and cost pool classifications to original rows.

    Convenience function that calls both reattach functions in sequence.
    """
    original_cols = list(original_df.columns)
    sub_lookup = _normalize_key_to_string(_dedup_lookup(subprogram_classified_df, SUBPROGRAM_KEY), SUBPROGRAM_KEY)
    cost_lookup = _normalize_subobject_code(
        _normalize_key_to_string(_dedup_lookup(cost_pool_classified_df, COST_POOL_KEY), COST_POOL_KEY),
        COST_POOL_KEY,
    )
    original_df = _normalize_key_to_string(original_df, SUBPROGRAM_KEY)
    original_df = _normalize_subobject_code(_normalize_key_to_string(original_df, COST_POOL_KEY), COST_POOL_KEY)

    sub_cols = [c for c in sub_lookup.columns if c != SUBPROGRAM_KEY]
    cost_cols = [c for c in cost_lookup.columns if c != COST_POOL_KEY]

    # Join subprogram classifications first, preferring classified columns on overlap.
    sub_overlaps = [c for c in sub_cols if c in original_df.columns]
    base = original_df.drop(sub_overlaps) if sub_overlaps else original_df
    result = base.join(sub_lookup, on=SUBPROGRAM_KEY, how="left")

    # Then join cost-pool classifications; keep subprogram-derived columns if names collide.
    cost_overlaps = [c for c in cost_cols if c in original_cols and c in result.columns]
    if cost_overlaps:
        result = result.drop(cost_overlaps)
    result = result.join(cost_lookup, on=COST_POOL_KEY, how="left")

    # Final column order: all classified columns first, then remaining original columns.
    classified_cols = []
    for col in sub_lookup.columns + cost_lookup.columns:
        if col not in classified_cols:
            classified_cols.append(col)
    remaining_original_cols = [c for c in original_cols if c not in classified_cols]
    final_order = [c for c in (classified_cols + remaining_original_cols) if c in result.columns]
    result = result.select(final_order)

    logger.info(f"Full reattach complete: {result.height:,} rows with all classifications")
    return result


def main() -> None:
    """CLI entry point for final reattachment step."""
    parser = argparse.ArgumentParser(
        description=(
            "Reattach classified subprogram + cost-pool data back to the original budget dataset"
        )
    )
    parser.add_argument(
        "--subprogram-classified",
        type=str,
        default=str(DATA_PROCESSED / "subprograms.csv"),
        help="Classified subprogram dataset (.csv/.parquet)",
    )
    parser.add_argument(
        "--cost-pool-classified",
        type=str,
        default=str(DATA_PROCESSED / "subobjects.csv"),
        help="Classified cost-pool dataset (.csv/.parquet)",
    )
    parser.add_argument(
        "--original-budget",
        type=str,
        default=str(DATA_PROCESSED / "budget_cleaned.parquet"),
        help="Original budget dataset to enrich (.csv/.parquet)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DATA_DIR / "enriched" / "budget_enriched.csv"),
        help="Output path or stem; writes both .csv and .parquet",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    )

    args = parser.parse_args()
    setup_logging(level=args.log_level)

    subprogram_classified_df = _read_table(args.subprogram_classified)
    cost_pool_classified_df = _read_table(args.cost_pool_classified)
    original_df = _read_table(args.original_budget)

    enriched_df = reattach_all(subprogram_classified_df, cost_pool_classified_df, original_df)

    output_arg = Path(args.output)
    if output_arg.suffix.lower() in {".csv", ".parquet"}:
        stem_path = output_arg.with_suffix("")
    else:
        stem_path = output_arg

    csv_path = _write_table(enriched_df, stem_path.with_suffix(".csv"))
    parquet_path = _write_table(enriched_df, stem_path.with_suffix(".parquet"))

    logger.info(
        "Final enriched outputs saved: csv={} parquet={} (rows={}, cols={})",
        csv_path,
        parquet_path,
        enriched_df.height,
        enriched_df.width,
    )


if __name__ == "__main__":
    main()
