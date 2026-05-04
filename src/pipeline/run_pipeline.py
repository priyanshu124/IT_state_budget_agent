"""Run loader/cleaner, profiler, and dedup steps in one command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from loguru import logger
import polars as pl

import subprocess
import sys

from src.pipeline.data_dedup import dedup_cost_pools, dedup_subprograms
from src.pipeline.data_loader import load_budget_data
from src.pipeline.data_profiler import profile_dataset
from src.utils.config import DATA_PROCESSED, DATA_RAW
from src.utils.data_paths import resolve_input_path
from src.utils.logging import setup_logging



    


def run_pipeline(input_path: str | Path, output_dir: str | Path | None = None, source_name: str | None = None) -> dict[str, Path]:
    """Execute load/clean, profile, and dedup steps and persist artifacts."""
    source_path = resolve_input_path(input_path)

    out_dir = Path(output_dir) if output_dir else DATA_PROCESSED
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = source_path.stem
    cleaned_path = out_dir / f"{stem}_cleaned.parquet"
    profile_path = out_dir / f"{stem}_profile.json"
    subprogram_path = out_dir / "subprograms.csv"
    subobject_path = out_dir / "subobject_codes.csv"

    logger.info(f"Pipeline start: {source_path}")

    # 1) Loader + cleaner
    cleaned_df = load_budget_data(source_path)
    cleaned_df.write_parquet(cleaned_path)
    logger.info(f"Saved cleaned data: {cleaned_path}")

    # 2) Profiler
    profile = profile_dataset(cleaned_df)
    with profile_path.open("w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, default=str)
    logger.info(f"Saved profile: {profile_path}")

    # 3) Dedup outputs
    subprogram_df = dedup_subprograms(cleaned_df)
    subobject_df = dedup_cost_pools(cleaned_df)
    subprogram_df.write_csv(subprogram_path)
    subobject_df.write_csv(subobject_path)
    logger.info(f"Saved subprogram data: {subprogram_path}")
    logger.info(f"Saved subobject data: {subobject_path}")

    logger.info(
        "Pipeline complete | cleaned_rows={} subprogram_rows={} subobject_rows={}",
        cleaned_df.height,
        subprogram_df.height,
        subobject_df.height,
    )

    return {
        "cleaned": cleaned_path,
        "profile": profile_path,
        "subprogram": subprogram_path,
        "subobject": subobject_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run loader(cleaner), profiler, and dedup pipeline"
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Path to input file or raw folder. Defaults to data/raw/budget/ and data/raw/higher_education/",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    )

    args = parser.parse_args()

    setup_logging(level=args.log_level)

    output_dir = DATA_PROCESSED

    if args.input:
        input_path = Path(args.input)
        run_pipeline(input_path, output_dir)
        return

    # No input provided -> load and combine budget and higher_education, then dedup together
    combined_df = None
    loaded_sources = []
    
    for folder_name in ["budget", "higher_education"]:
        sub = DATA_RAW / folder_name
        logger.info(f"Checking folder: {sub} (exists: {sub.exists()})")
        try:
            source_path = resolve_input_path(sub)
            logger.info(f"Loading data from {source_path}")
            df = load_budget_data(source_path)
            loaded_sources.append(folder_name)
            
            if combined_df is None:
                combined_df = df
            else:
                # Use how="diagonal" to handle schema differences (fills missing cols with nulls)
                combined_df = pl.concat([combined_df, df], how="diagonal")
            
            logger.info(f"Loaded {df.height} rows from {folder_name} (schema width: {df.width})")
        except FileNotFoundError as e:
            logger.warning(f"No supported files in {sub}: {e}")
    
    logger.info(f"Loaded sources: {loaded_sources}")
    
    if combined_df is None:
        logger.error("No data loaded from any sources")
        return

    # Save combined cleaned data
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned_path = output_dir / "2027_cleaned.parquet"
    combined_df.write_parquet(cleaned_path)
    logger.info(f"Saved combined cleaned data: {cleaned_path} ({combined_df.height} rows)")

    # Profile combined data
    profile = profile_dataset(combined_df)
    profile_path = output_dir / "2027_combined_profile.json"
    with profile_path.open("w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, default=str)
    logger.info(f"Saved combined profile: {profile_path}")

    # Dedup combined data
    subprogram_df = dedup_subprograms(combined_df)
    subobject_df = dedup_cost_pools(combined_df)
    subprogram_path = output_dir / "subprograms.csv"
    subobject_path = output_dir / "subobject_codes.csv"
    subprogram_df.write_csv(subprogram_path)
    subobject_df.write_csv(subobject_path)
    logger.info(f"Saved subprogram data: {subprogram_path}")
    logger.info(f"Saved subobject data: {subobject_path}")

    logger.info(
        "Pipeline dedup complete | combined_rows={} subprogram_rows={} subobject_rows={}",
        combined_df.height,
        subprogram_df.height,
        subobject_df.height,
    )

    # 4) Apply designation filter
    logger.info("Applying designation filter...")
    subprocess.run(
        [sys.executable, "-m", "src.pipeline.designation_filter"],
        check=True,
    )
    logger.info("Designation filter complete")

    # 5) Apply shadow IT filter
    logger.info("Applying shadow IT filter...")
    subprocess.run(
        [sys.executable, "-m", "src.pipeline.shadow_it_filter"],
        check=True,
    )
    logger.info("Shadow IT filter complete")

    # 6) Apply data enrichment
    logger.info("Applying data enrichment...")
    subprocess.run(
        [sys.executable, "-m", "src.pipeline.data_enrichment"],
        check=True,
    )
    logger.info("Data enrichment complete")

    # 7) Build final enriched output
    logger.info("Building final enriched output...")
    subprocess.run(
        [sys.executable, "-m", "src.pipeline.build_final_enriched"],
        check=True,
    )
    logger.info("Final enriched output complete")

    logger.info("Full pipeline complete")


if __name__ == "__main__":
    main()
