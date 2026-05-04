import polars as pl
from pathlib import Path
import argparse
from loguru import logger

from src.utils.config import DATA_DIR, DATA_PROCESSED
from src.utils.logging import setup_logging

SUBPROGRAM_KEY = "organization_sub_code"
COST_POOL_KEY = "comptroller_subobject_code"


def _read_table(path: str | Path) -> pl.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    if path.suffix.lower() == ".csv":
        return pl.read_csv(path)
    if path.suffix.lower() == ".parquet":
        return pl.read_parquet(path)
    raise ValueError("Unsupported file format; use .csv or .parquet")


def _write_outputs(df: pl.DataFrame, out_stem: str | Path) -> tuple[Path, Path]:
    out_stem = Path(out_stem)
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    csv_path = out_stem.with_suffix(".csv")
    parquet_path = out_stem.with_suffix(".parquet")

    try:
        df.write_csv(csv_path)
    except OSError:
        csv_path = out_stem.with_name(out_stem.stem + "_final.csv")
        logger.warning("CSV locked; writing fallback {}", csv_path)
        df.write_csv(csv_path)

    try:
        df.write_parquet(parquet_path)
    except OSError:
        parquet_path = out_stem.with_name(out_stem.stem + "_final.parquet")
        logger.warning("Parquet locked; writing fallback {}", parquet_path)
        df.write_parquet(parquet_path)

    return csv_path, parquet_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build final enriched budget by joining processed subprograms and subobject codes"
    )
    parser.add_argument(
        "--budget",
        type=str,
        default=str(DATA_PROCESSED / "2027_cleaned.parquet"),
        help="Original budget dataset (.parquet/.csv)",
    )
    parser.add_argument(
        "--subprograms",
        type=str,
        default=str(DATA_PROCESSED / "subprograms.csv"),
        help="Processed subprograms (.csv/.parquet) with classification columns",
    )
    parser.add_argument(
        "--subobjects",
        type=str,
        default=str(DATA_PROCESSED / "subobject_codes.csv"),
        help="Processed subobject codes (.csv/.parquet) with cost_pool columns",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DATA_DIR / "output" / "final_budget_enriched"),
        help="Output path stem (no suffix); writes .csv and .parquet",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Log level",
    )

    args = parser.parse_args()
    setup_logging(level=args.log_level)

    budget_path = Path(args.budget)
    if not budget_path.exists():
        # try to find a likely cleaned budget file in processed
        cand = list(Path(DATA_PROCESSED).glob("*.parquet"))
        cand = [p for p in cand if "budget" in p.name.lower() or "cleaned" in p.name.lower()]
        if cand:
            budget_path = cand[0]
            logger.warning("Budget input not found; using fallback: {}", budget_path)
        else:
            raise FileNotFoundError(
                f"Budget file not found: {args.budget}. Place cleaned budget under {DATA_PROCESSED} or pass --budget"
            )
    budget = _read_table(budget_path)
    subprograms = _read_table(args.subprograms)
    subobjects = _read_table(args.subobjects)

    # Normalize keys to Utf8 for stable joins
    budget = budget.with_columns(
        pl.col(SUBPROGRAM_KEY).cast(pl.Utf8), pl.col(COST_POOL_KEY).cast(pl.Utf8)
    )
    subprograms = subprograms.with_columns(pl.col(SUBPROGRAM_KEY).cast(pl.Utf8))
    subobjects = subobjects.with_columns(pl.col(COST_POOL_KEY).cast(pl.Utf8))

    # Keep organization_sub_code aligned with organization_code when the sub-code is null.
    # This preserves R30-style rows through the final join and keeps the join key stable.
    budget = budget.with_columns(
        pl.when(pl.col(SUBPROGRAM_KEY).is_null())
        .then(pl.col("organization_code"))
        .otherwise(pl.col(SUBPROGRAM_KEY))
        .alias(SUBPROGRAM_KEY)
    )
    subprograms = subprograms.with_columns(
        pl.when(pl.col(SUBPROGRAM_KEY).is_null())
        .then(pl.col("organization_code"))
        .otherwise(pl.col(SUBPROGRAM_KEY))
        .alias(SUBPROGRAM_KEY)
    )

    # Pad comptroller_subobject_code to 4 characters on both sides before join
    budget = budget.with_columns(
        pl.col(COST_POOL_KEY).cast(pl.Utf8).str.pad_start(4, "0").alias(COST_POOL_KEY)
    )
    subobjects = subobjects.with_columns(
        pl.col(COST_POOL_KEY).cast(pl.Utf8).str.pad_start(4, "0").alias(COST_POOL_KEY)
    )

    # Drop from budget any columns that will be provided by processed files (except keys)
    proc_cols = set(subprograms.columns) | set(subobjects.columns)
    budget_drop = [c for c in budget.columns if (c in proc_cols and c not in {SUBPROGRAM_KEY, COST_POOL_KEY})]
    if budget_drop:
        budget = budget.drop(budget_drop)

    # Left join processed values into budget (processed columns take precedence)
    merged = budget.join(subprograms, on=SUBPROGRAM_KEY, how="left")
    merged = merged.join(subobjects, on=COST_POOL_KEY, how="left")

    # Ensure comptroller_subobject_code remains padded to 4 characters in final output
    if COST_POOL_KEY in merged.columns:
        merged = merged.with_columns(
            pl.col(COST_POOL_KEY).cast(pl.Utf8).str.pad_start(4, "0").alias(COST_POOL_KEY)
        )

    csv_path, parquet_path = _write_outputs(merged, args.output)

    logger.info(
        "Final enriched budget written: csv={} parquet={} rows={} cols={}",
        csv_path,
        parquet_path,
        merged.height,
        merged.width,
    )


if __name__ == "__main__":
    main()
