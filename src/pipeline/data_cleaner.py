"""Text cleaning utilities for budget records.

:func:`clean_df` is the single entry point — vectorized, no row loops.
Called in ``stage_0_ingest.run()`` after column renaming and before DuckDB ingest.
"""

from __future__ import annotations

import polars as pl
from loguru import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Mojibake replacements — ORDER MATTERS: longest/most-specific patterns first
# so the 2-char catch-all (â€) never consumes the prefix of 3-char sequences.
_MOJIBAKE_MAP: list[tuple[str, str]] = [
    ("\u00e2\u20ac\u2122", "'"),       # â€™ → ' (apostrophe)
    ("\u00e2\u20ac\u0153", '"'),       # â€œ → " (left double quote)
    ("\u00e2\u20ac\u201c", "\u2013"),  # â€" → – (en dash)
    ("\u00e2\u20ac\u201d", "\u2014"),  # â€" → — (em dash)
    ("\u00e2\u20ac\u02dc", "\u2018"),  # â€˜ → ' (left single quote)
    ("\u00e2\u20ac",       '"'),       # â€  → " (catch-all)
]

# Text fields that receive full mojibake + _x000D_ cleaning.
# All other string columns get whitespace-strip only.
_TEXT_FIELDS: frozenset[str] = frozenset({
    "description",
    "agency_name", "unit_name", "program_name", "subprogram_name",
    "object_name", "comptroller_subobject_name", "agency_subobject_name",
    "fund_type_name", "category_title", "type",
})

# Short name fields where abbreviations are expanded (values < 40 chars only).
_ABBREV_FIELDS: frozenset[str] = frozenset({
    'agency_name', "program_name", "unit_name", "subprogram_name", 'description', 'comptroller_subobject_name', "agency_subobject_name", 'object_name', 'fund_type_name', 'category_title', 'type',
})

# Abbreviation patterns applied to short name values (RE2 syntax, case-insensitive).
_ABBREVIATIONS: list[tuple[str, str]] = [
    (r"(?i)\bSW\b",    "Software"),
    (r"(?i)\bLIC\b",   "Licenses"),
    (r"(?i)\bMAINT\b", "Maintenance"),
    (r"(?i)\bIT\b", "Information Technology"),
    (r"(?i)\bDOIT\b", "Department of Information Technology"),
    (r"(?i)&",         "and"),
]

# Integer columns: cast to Int32, null → 0
# NOTE: comptroller_subobject_code is NOT cast to Int32 because it needs to stay as string
# for proper zero-padding (e.g., "0101" not "101"). Padding is handled in _CODE_PAD_WIDTHS.
_INT_COLUMNS: dict[str, pl.PolarsDataType] = {
    "fiscal_year":                pl.Int32,
    "object_code":                pl.Int32,
}

# Code columns: zero-pad to required digit width ("4" → "04")
_CODE_PAD_WIDTHS: dict[str, int] = {
    "program_code":          2,
    "comptroller_subobject_code": 4,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_subprogram_code(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize subprogram codes to _0000 format.
    
    Rules:
    - Normalize organization_sub_code and subprogram_code to end with _0000.
    - Deduplication is intentionally NOT performed here; it is handled by the
      dedicated deduplication stage (`src.pipeline.data_dedup`).
    """
    def _pad_suffix_to_4(expr: pl.Expr) -> pl.Expr:
        """Pad trailing numeric suffix after last '_' to 4 digits.

        Examples:
        - 'B75_A01_04_0' -> 'B75_A01_04_0000'
        - 'W00_A01_08_8616' -> 'W00_A01_08_8616' (unchanged)
        - non-numeric suffixes are left unchanged
        """

        # Build an expression that extracts a trailing numeric suffix, pads it,
        # and recombines. Avoid per-row Python `apply` to remain vectorized.
        expr_utf8 = expr.cast(pl.Utf8)
        suffix = expr_utf8.str.extract(r'_(\d+)$', 1)
        base = expr_utf8.str.replace_all(r'_(\d+)$', '', literal=False)
        padded = pl.when(suffix.is_not_null()).then(suffix.str.zfill(4)).otherwise(pl.lit(None).cast(pl.Utf8))
        return pl.when(suffix.is_not_null()).then(base + pl.lit("_") + padded).otherwise(expr_utf8)

    # Normalize organization_sub_code by padding numeric suffix to 4 digits
    if "organization_sub_code" in df.columns:
        df = df.with_columns(
            _pad_suffix_to_4(pl.col("organization_sub_code")).alias("organization_sub_code")
        )
    
    # Normalize subprogram_code if present (also pad trailing numeric part to 4 digits)
    if "subprogram_code" in df.columns:
        df = df.with_columns(
            _pad_suffix_to_4(pl.col("subprogram_code")).alias("subprogram_code")
        )
    
    return df


def _filter_data(df: pl.DataFrame) -> pl.DataFrame:
    # Filter on Fiscal year >=2017, then normalize subprogram codes and deduplicate
    df = df.filter(
        (pl.col("fiscal_year") >= 2017)
    )
    return _normalize_subprogram_code(df)

def _apply_text_cleaning(expr: pl.Expr) -> pl.Expr:
    """Strip _x000D_ artifacts and fix mojibake on a string Expr."""
    expr = expr.str.replace_all(r"_x000D_", "", literal=False)
    for bad, good in _MOJIBAKE_MAP:
        expr = expr.str.replace_all(bad, good, literal=True)
    return expr


def _apply_abbreviations(expr: pl.Expr) -> pl.Expr:
    """Expand common abbreviations on short values (< 40 chars)."""
    expanded = expr
    for pattern, replacement in _ABBREVIATIONS:
        ci_pattern = pattern if pattern.startswith("(?i)") else f"(?i){pattern}"
        expanded = expanded.str.replace_all(ci_pattern, replacement, literal=False)
    return pl.when(expr.str.len_chars() < 100).then(expanded).otherwise(expr)




# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_df(df: pl.DataFrame) -> pl.DataFrame:
    """Apply all cleaning rules to a raw budget DataFrame.

    Rules applied in order:
    0. Filter fiscal year >= 2017, normalize org_sub_code to _0000 format, deduplicate by latest fiscal year.
    1. Strip whitespace — all string columns.
    2. Mojibake + _x000D_ fix — all ``_TEXT_FIELDS`` columns.
    3. Abbreviation expansion — short values in ``_ABBREV_FIELDS`` columns.
    4. Budget — strip commas, cast Float64, null → 0.0.
    5. Integer columns — cast Int32, null → 0.
    6. Code columns — zero-pad to required digit width.
    """
    logger.info("cleaning_dataframe", rows=len(df), columns=len(df.columns))
    result = _filter_data(df)

    # 1. Strip whitespace from all string columns
    str_cols = [c for c, t in zip(df.columns, df.dtypes) if t in (pl.Utf8, pl.String)]
    if str_cols:
        result = result.with_columns([pl.col(c).str.strip_chars() for c in str_cols])

    # 2. Mojibake + _x000D_ fix for known text fields
    text_cols = [c for c in _TEXT_FIELDS if c in result.columns]
    if text_cols:
        result = result.with_columns(
            [_apply_text_cleaning(pl.col(c)).alias(c) for c in text_cols]
        )

    # 3. Abbreviation expansion for short name values
    abbrev_cols = [c for c in _ABBREV_FIELDS if c in result.columns]
    if abbrev_cols:
        result = result.with_columns(
            [_apply_abbreviations(pl.col(c)).alias(c) for c in abbrev_cols]
        )

    # 4. Budget: strip thousands-separator commas, cast, fill null
    if "budget" in result.columns:
        result = result.with_columns(
            pl.col("budget")
            .cast(pl.Utf8)
            .str.replace_all(",", "", literal=True)
            .cast(pl.Float64, strict=False)
            .fill_null(0.0)
        )

    # 5. Integer columns: cast and fill null → 0
    int_exprs = [
        pl.col(c).cast(t, strict=False).fill_null(0)
        for c, t in _INT_COLUMNS.items()
        if c in result.columns
    ]
    if int_exprs:
        result = result.with_columns(int_exprs)

    # 6. Code columns: zero-pad
    pad_exprs = [
        pl.col(c).cast(pl.Utf8).str.zfill(w)
        for c, w in _CODE_PAD_WIDTHS.items()
        if c in result.columns
    ]
    if pad_exprs:
        result = result.with_columns(pad_exprs)

    logger.info("cleaning_complete", rows=len(result), text_cols_cleaned=len(text_cols))
    return result