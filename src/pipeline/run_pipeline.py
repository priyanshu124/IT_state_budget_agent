"""Run loader/cleaner, profiler, and dedup steps in one command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from loguru import logger

from src.pipeline.data_depdup import latest_subprogram_subobject
from src.pipeline.data_loader import load_budget_data
from src.pipeline.data_profiler import profile_dataset
from src.utils.config import DATA_PROCESSED, DATA_RAW
from src.utils.logging import setup_logging



    


def run_pipeline(input_path: str | Path, output_dir: str | Path | None = None) -> dict[str, Path]:
    """Execute load/clean, profile, and dedup steps and persist artifacts."""
    source_path = Path(input_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Input file not found: {source_path}")

    out_dir = Path(output_dir) if output_dir else DATA_PROCESSED
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = source_path.stem
    cleaned_path = out_dir / f"{stem}_cleaned.parquet"
    profile_path = out_dir / f"{stem}_profile.json"
    dim_path = out_dir / f"{stem}_dim.parquet"

    logger.info(f"Pipeline start: {source_path}")

    # 1) Loader + cleaner
    cleaned_df = load_budget_data(source_path)
    cleaned_df.write_parquet(cleaned_path)
    logger.info(f"Saved cleaned data: {cleaned_path}")

    # 2) Profiler
    profile_dataset(cleaned_df)
    logger.info(f"Saved profile: {profile_path}")

    # 3) Dedup for dim data
    dim_df = latest_subprogram_subobject(cleaned_df)
    dim_df.write_parquet(dim_path)
    logger.info(f"Saved dim data: {dim_path}")

    logger.info(
        "Pipeline complete | cleaned_rows={} dim_rows={} dim_cols={}",
        cleaned_df.height,
        dim_df.height,
        dim_df.width,
    )

    return {
        "cleaned": cleaned_path,
        "profile": profile_path,
        "dim": dim_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run loader(cleaner), profiler, and dedup pipeline"
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Path to input file. Defaults to data/raw/budget.csv",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    )

    args = parser.parse_args()
    input_path = Path(args.input) if args.input else (DATA_RAW / "budget.csv")
    output_dir = DATA_PROCESSED

    setup_logging(level=args.log_level)
    run_pipeline(input_path, output_dir)


if __name__ == "__main__":
    main()
