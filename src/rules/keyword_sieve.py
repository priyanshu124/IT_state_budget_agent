"""
Keyword Sieve for Shadow IT Detection.

Applies regex patterns to non-IT agency rows to catch
technology spend hidden outside of known IT departments.
Rows that hit no keywords are dropped (saving ~90% from hitting LLM).
"""

import re

import polars as pl
from loguru import logger

from src.utils.config import get_config
from src.utils.schemas import ClassificationSource


def apply_keyword_sieve(
    df: pl.DataFrame,
    config: dict | None = None,
    text_columns: list[str] | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Apply keyword regex sieve to unclassified rows.

    Args:
        df: DataFrame with classification columns from deterministic rules.
        config: TBM config dict.
        text_columns: Columns to search for keywords. Auto-detected if None.

    Returns:
        Tuple of (hits_df, dropped_df):
        - hits_df: Rows that matched keywords (need LLM agent review)
        - dropped_df: Rows dropped by sieve (no tech signal found)
    """
    if config is None:
        config = get_config()

    # Only process unclassified rows
    unclassified = df.filter(pl.col("is_it_related").is_null())
    already_classified = df.filter(pl.col("is_it_related").is_not_null())

    logger.info(f"Keyword sieve input: {unclassified.height:,} unclassified rows")

    if unclassified.height == 0:
        return already_classified, pl.DataFrame()

    # Auto-detect text columns to search
    if text_columns is None:
        text_columns = _detect_text_columns(unclassified)
    logger.info(f"  Searching columns: {text_columns}")

    # Build combined text column for regex matching
    text_exprs = [pl.col(c).fill_null("").cast(pl.Utf8) for c in text_columns if c in unclassified.columns]
    if not text_exprs:
        logger.warning("  No text columns found for keyword sieve")
        return already_classified, unclassified

    unclassified = unclassified.with_columns(
        pl.concat_str(text_exprs, separator=" ").alias("_sieve_text")
    )

    # Load keyword patterns from config
    keywords_config = config.get("shadow_it_keywords", {})
    all_patterns = []
    pattern_labels = []

    for confidence_level in ["high_confidence", "medium_confidence", "low_confidence"]:
        patterns = keywords_config.get(confidence_level, [])
        for p in patterns:
            all_patterns.append(p)
            pattern_labels.append(f"{confidence_level}:{p}")

    if not all_patterns:
        logger.warning("  No keyword patterns found in config")
        return already_classified, unclassified

    logger.info(f"  Loaded {len(all_patterns)} keyword patterns")

    # Apply regex patterns
    # Build a single combined pattern for efficiency
    combined_pattern = "|".join(f"({p})" for p in all_patterns)

    try:
        compiled = re.compile(combined_pattern, re.IGNORECASE)
    except re.error as e:
        logger.error(f"  Regex compilation error: {e}")
        return already_classified, unclassified

    # Use Polars string contains for the initial broad match
    unclassified = unclassified.with_columns(
        pl.col("_sieve_text")
        .str.contains(f"(?i){combined_pattern}")
        .alias("_keyword_hit")
    )

    # For rows that hit, find which specific keywords matched
    hits = unclassified.filter(pl.col("_keyword_hit"))
    dropped = unclassified.filter(~pl.col("_keyword_hit"))

    # Add keyword hit details to hits
    if hits.height > 0:
        hit_details = []
        for row in hits.iter_rows(named=True):
            text = row["_sieve_text"]
            matched = []
            for pattern, label in zip(all_patterns, pattern_labels):
                if re.search(pattern, text, re.IGNORECASE):
                    matched.append(label)
            hit_details.append("; ".join(matched))

        hits = hits.with_columns(
            pl.Series("keyword_hits", hit_details),
            pl.lit(ClassificationSource.KEYWORD_SIEVE.value).alias("classification_source"),
        )

    # Mark dropped rows
    if dropped.height > 0:
        dropped = dropped.with_columns(
            pl.lit(False).alias("is_it_related"),
            pl.lit(ClassificationSource.DROPPED.value).alias("classification_source"),
        )

    # Clean up temp columns
    cleanup_cols = ["_sieve_text", "_keyword_hit"]
    hits = hits.drop([c for c in cleanup_cols if c in hits.columns])
    dropped = dropped.drop([c for c in cleanup_cols if c in dropped.columns])

    logger.info(
        f"  Sieve results: {hits.height:,} keyword hits, "
        f"{dropped.height:,} dropped ({dropped.height/unclassified.height*100:.1f}% filtered)"
    )

    # Recombine: classified + hits go forward, dropped is returned separately
    forward_df = pl.concat([already_classified, hits], how="diagonal_relaxed")

    return forward_df, dropped


def audit_dropped_rows(
    dropped_df: pl.DataFrame,
    sample_size: int = 200,
    seed: int = 42,
) -> pl.DataFrame:
    """
    Sample dropped rows for manual audit.

    This is critical for validating the keyword sieve isn't
    silently dropping real Shadow IT.
    """
    if dropped_df.height == 0:
        logger.info("No dropped rows to audit")
        return dropped_df

    sample_n = min(sample_size, dropped_df.height)
    sample = dropped_df.sample(n=sample_n, seed=seed)

    logger.info(
        f"Audit sample: {sample_n} rows from {dropped_df.height:,} dropped "
        f"(review for missed Shadow IT)"
    )

    return sample


def _detect_text_columns(df: pl.DataFrame) -> list[str]:
    """Auto-detect which columns are useful for keyword matching."""
    priority_names = [
        "program_name", "subprogram_name", "description",
        "object_name", "comptroller_subobject_name", "subobject_name",
        "agency_name",
    ]
    cols_lower = {c.lower().replace(" ", "_"): c for c in df.columns}

    found = []
    for name in priority_names:
        if name in cols_lower:
            found.append(cols_lower[name])
        else:
            # Partial match fallback
            for col_key, col_orig in cols_lower.items():
                if name.split("_")[0] in col_key and col_orig not in found:
                    found.append(col_orig)
                    break

    return found if found else [c for c in df.columns if df[c].dtype == pl.Utf8]
