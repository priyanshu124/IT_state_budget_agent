from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import polars as pl
from loguru import logger

from src.pipeline.it_programs_config import load_runtime_config
from src.utils.config import CONFIG_DIR, DATA_PROCESSED


class DesignationFilter:
    """Filters and annotates known IT-designated subprograms."""

    def __init__(self, config: dict[str, Any]):
        it_programs = config.get("it_programs", {})
        fields = it_programs.get("fields", {})
        self._program_name_col = str(fields.get("program_name", "program_name"))
        self._agency_code_col = str(fields.get("agency_code", "agency_code"))
        self._match_text_cols = [
            str(col)
            for col in fields.get(
                "match_fields",
                ["program_name", "subprogram_name"],
            )
            if col
        ]
        self._designations = self._load_designations(config)

        logger.info(
            "DesignationFilter loaded {} designations: {}",
            len(self._designations),
            [d.get("label", d["id"]) for d in self._designations],
        )

    @staticmethod
    def _load_designations(config: dict[str, Any]) -> list[dict[str, Any]]:
        raw = config.get("it_programs", {}).get("designations", [])
        return [
            {
                **d,
                "patterns_lower": [p.lower() for p in d["patterns"]],
            }
            for d in raw
        ]

    def _text_match_expr(self, pattern: str) -> pl.Expr:
        """Build a case-insensitive contains expression across configured text fields."""

        match = pl.lit(False)
        for col in self._match_text_cols:
            match = match | (
                pl.col(col)
                .cast(pl.Utf8, strict=False)
                .fill_null("")
                .str.to_lowercase()
                .str.contains(pattern, literal=True)
            )
        return match

    def _designation_match_expr(
        self,
        designation: dict[str, Any],
    ) -> pl.Expr:
        """Build a Polars boolean expression for one designation rule."""
        match = pl.lit(False)
        if designation.get("match_field") == "agency_code":
            for code in designation["patterns"]:
                match = match | (pl.col(self._agency_code_col) == code)
            return match

        for pattern in designation["patterns_lower"]:
            match = match | self._text_match_expr(pattern)

        if designation.get("agency_code_guard"):
            match = match & (pl.col(self._agency_code_col) == designation["agency_code_guard"])

        return match

    def apply_designations(self, df: pl.DataFrame) -> pl.DataFrame:
        """Annotate all rows with designation columns while keeping all input columns."""
        if df.is_empty():
            return df.with_columns([
                pl.lit(False).alias("is_it"),
                pl.lit(None).cast(pl.Utf8).alias("it_designation"),
            ])

        it_designation_expr = pl.lit(None).cast(pl.Utf8)
        any_match_expr = pl.lit(False)
        for designation in self._designations:
            dmatch = self._designation_match_expr(designation)
            any_match_expr = any_match_expr | dmatch

        # First match in config order wins.
        for designation in reversed(self._designations):
            dmatch = self._designation_match_expr(designation)
            it_designation_expr = (
                pl.when(dmatch)
                .then(pl.lit(str(designation.get("id", ""))))
                .otherwise(it_designation_expr)
            )

        return df.with_columns([
            any_match_expr.alias("is_it"),
            it_designation_expr.alias("it_designation"),
        ])

    def filter_non_it(self, df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Split DataFrame into non-IT rows and known IT rows."""
        if df.is_empty():
            annotated = self.apply_designations(df)
            return annotated, annotated.clear()

        annotated = self.apply_designations(df)
        known_it_df = annotated.filter(pl.col("is_it"))
        non_it_df = annotated.filter(~pl.col("is_it"))

        logger.info(
            "Designation filter: {:,} total -> {:,} known IT, {:,} non-IT",
            len(df),
            len(known_it_df),
            len(non_it_df),
        )

        return non_it_df, known_it_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Run designation-only IT tagging")
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Input subprogram CSV. If omitted, uses data/processed/subprograms.csv when present, otherwise data/processed/subprogram.csv",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Optional config YAML with it_programs.designations. Defaults to merged configs.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DATA_PROCESSED / "subprograms.csv"),
        help="Output CSV path. Defaults to overwriting data/processed/subprograms.csv",
    )
    args = parser.parse_args()

    if args.input:
        input_path = Path(args.input)
    else:
        preferred = DATA_PROCESSED / "subprograms.csv"
        fallback = DATA_PROCESSED / "subprogram.csv"
        input_path = preferred if preferred.exists() else fallback

    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}. Pass --input explicitly."
        )

    config = load_runtime_config(args.config)
    df = pl.read_csv(input_path, encoding="utf8-lossy")

    designation_filter = DesignationFilter(config)
    enriched_df = designation_filter.apply_designations(df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    enriched_df.write_csv(output_path)

    it_rows = int(enriched_df["is_it"].sum()) if enriched_df.height else 0
    print(
        f"Saved designation output: {len(enriched_df):,} rows "
        f"({it_rows:,} flagged IT) -> {output_path}"
    )


if __name__ == "__main__":
    main()
