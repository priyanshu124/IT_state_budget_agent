"""
Data Profiler for Maryland Budget CSVs.

Run this first on any new dataset to understand structure,
coverage, nulls, and value distributions before building rules.

Usage:
    python -m src.pipeline.profiler data/raw/your_file.csv
"""

import json
from pathlib import Path

import polars as pl
from loguru import logger

from src.utils.logging import setup_logging


def _load_profile_input(data: pl.DataFrame | str | Path) -> pl.DataFrame:
    """Accept a DataFrame or file path and return a DataFrame."""
    if isinstance(data, pl.DataFrame):
        return data

    path = Path(data)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pl.read_csv(path, infer_schema_length=10000, ignore_errors=True)
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in (".xlsx", ".xls"):
        return pl.read_excel(path)
    raise ValueError(f"Unsupported input type: {suffix}")


def profile_dataset(data: pl.DataFrame | str | Path) -> dict:
    """
    Profile a budget CSV/Excel file and print a comprehensive summary.

    Returns a dict of profiling stats for downstream use.
    """
    df = _load_profile_input(data)
    logger.info(f"Profiling DataFrame: {df.width} columns, {df.height} rows")

    stats = {
        "rows": df.height,
        "columns": df.width,
        "column_names": df.columns,
    }

    # --- Null Analysis ---
    null_counts = df.null_count()
    null_rates: dict[str, dict[str, float | int]] = {}
    for col in df.columns:
        null_ct = null_counts[col][0]
        null_pct = (null_ct / df.height) * 100 if df.height > 0 else 0
        null_rates[col] = {"null_count": int(null_ct), "null_pct": round(float(null_pct), 2)}
    stats["null_rates"] = null_rates

    # --- Unique Value Counts ---
    unique_counts: dict[str, int] = {}
    for col in df.columns:
        n_unique = df[col].n_unique()
        unique_counts[col] = int(n_unique)
    stats["unique_counts"] = unique_counts

    # --- Key Field Distributions ---
    # Try to find agency, subobject, and program columns by fuzzy match
    key_fields = _find_key_columns(df)
    stats["key_fields"] = key_fields

    top_values: dict[str, list[dict[str, str | int | float]]] = {}
    for label, col_name in key_fields.items():
        if col_name and col_name in df.columns:
            value_counts = (
                df.group_by(col_name)
                .agg(pl.len().alias("count"))
                .sort("count", descending=True)
                .head(20)
            )
            rows_for_json: list[dict[str, str | int | float]] = []
            for row in value_counts.iter_rows(named=True):
                val = row[col_name] or "(null)"
                ct = row["count"]
                pct = (ct / df.height) * 100
                rows_for_json.append(
                    {"value": str(val), "count": int(ct), "pct": round(float(pct), 2)}
                )
            top_values[label] = rows_for_json
    stats["top_values"] = top_values

    # --- Amount Summary ---
    amount_col = _find_amount_column(df)
    if amount_col:
        stats["amount_column"] = amount_col
        amounts = df[amount_col].drop_nulls().cast(pl.Float64, strict=False).drop_nulls()
        if amounts.len() > 0:
            stats["amount_summary"] = {
                "total": float(amounts.sum()),
                "mean": float(amounts.mean()),
                "median": float(amounts.median()),
                "min": float(amounts.min()),
                "max": float(amounts.max()),
                "zeros": int((amounts == 0).sum()),
                "negative": int((amounts < 0).sum()),
            }

    # --- Dedup Preview ---
    # Try a few candidate dedup key combos
    text_cols = [c for c in df.columns if df[c].dtype == pl.Utf8]
    if text_cols:
        # All text columns combined
        concat_expr = pl.concat_str([pl.col(c).fill_null("") for c in text_cols], separator="|")
        n_unique_all = df.select(concat_expr.alias("key")).n_unique()
        ratio = n_unique_all / df.height * 100
        stats["dedup_potential"] = {
            "all_text_unique": int(n_unique_all),
            "all_text_unique_pct": round(float(ratio), 2),
        }

        # Just the key classification fields
        key_cols = [v for v in key_fields.values() if v and v in text_cols]
        if len(key_cols) >= 2:
            concat_key = pl.concat_str([pl.col(c).fill_null("") for c in key_cols], separator="|")
            n_unique_key = df.select(concat_key.alias("key")).n_unique()
            ratio_key = n_unique_key / df.height * 100
            stats["dedup_potential"]["key_fields"] = key_cols
            stats["dedup_potential"]["key_fields_unique"] = int(n_unique_key)
            stats["dedup_potential"]["key_fields_unique_pct"] = round(float(ratio_key), 2)

    logger.info(
        "Profile complete: rows={} cols={} key_fields_found={}",
        stats["rows"],
        stats["columns"],
        len([k for k, v in key_fields.items() if v]),
    )

    return stats


def _find_key_columns(df: pl.DataFrame) -> dict[str, str | None]:
    """Fuzzy-match column names to expected budget fields."""
    cols_lower = {c.lower().replace(" ", "_"): c for c in df.columns}

    mappings = {
        "agency": ["agency", "agency_name", "unit_name", "department"],
        "agency_code": ["agency_code", "unit_code", "agency_id"],
        "program": ["program_name", "program", "prog_name"],
        "subprogram": ["subprogram_name", "subprogram", "subprog"],
        "object": ["object_name", "object", "obj_name"],
        "subobject": [
            "comptroller_subobject_name", "subobject_name",
            "subobject", "sub_object", "comp_subobject",
        ],
        "description": ["description", "desc", "narrative", "text"],
    }

    found = {}
    for label, candidates in mappings.items():
        found[label] = None
        for candidate in candidates:
            if candidate in cols_lower:
                found[label] = cols_lower[candidate]
                break
        # Fallback: partial match
        if found[label] is None:
            for col_key, col_orig in cols_lower.items():
                if label in col_key:
                    found[label] = col_orig
                    break

    return found


def _find_amount_column(df: pl.DataFrame) -> str | None:
    """Find the dollar amount column."""
    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ["amount", "budget", "expenditure", "appropriation", "total"]):
            return col
    # Fallback: first numeric column
    for col in df.columns:
        if df[col].dtype in (pl.Float64, pl.Float32, pl.Int64, pl.Int32):
            return col
    return None

def _write_profile_json(profile: dict, output_path: Path) -> None:
    """Write profile dict to JSON with stable formatting."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, default=str)


# --- CLI Entry Point ---
if __name__ == "__main__":
    import sys

    setup_logging()

    if len(sys.argv) < 2:
        logger.error("Usage: python -m src.pipeline.data_profiler <path_to_file> [output_json_path]")
        sys.exit(1)

    profile = profile_dataset(sys.argv[1])
    if len(sys.argv) > 2:
        _write_profile_json(profile, Path(sys.argv[2]))
