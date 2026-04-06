"""
Shadow IT Pre-Filter
======================
Two-signal pre-filter that runs during the data pipeline. No API cost.

Signal 1 — SPEND RATIO:
    What percentage of a subprogram's total spend goes to IT subobject codes?
    Uses your existing cost pool mappings to identify IT-specific codes
    (Software & SaaS, Hardware, Telecom, Cross Charges).
    Catches programs that BUY IT regardless of what they're CALLED.

Signal 2 — TAXONOMY KEYWORDS:
    Keywords derived from TBM towers YAML — not hardcoded.
    Generates keyword phrases from tower names, sub-tower names,
    and descriptions. Catches programs that SAY they're IT.

A subprogram is a candidate if EITHER signal fires:
    - IT spend ratio ≥ threshold (default 10%)
    - OR any taxonomy keyword matches in name/program/description

Usage:
    python -m src.pipeline.shadow_it_prefilter \
        --budget data/raw/budget.csv \
        --subprograms data/processed/dim_subprogram.csv \
        --towers configs/tbm_towers.yaml \
    --subobjects data/processed/subobjects.csv \
        --spend-threshold 0.10 \
        --output data/processed/shadow_it_candidates.csv
"""

import argparse
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

import yaml
import polars as pl
from loguru import logger

# ── Signal 1: IT Spend Ratio ──────────────────────────────────

class ITSpendRatioCalculator:
    """Calculate IT spend ratio per subprogram from budget data."""

    # Cost pools that indicate IT spending
    IT_COST_POOLS = {
        "Software & SaaS",
        "Hardware",
        "Telecom",
        "Cloud Services",
    }

    def __init__(self, subobjects_path: str | Path):
        """Load subobjects CSV to identify IT subobject codes by cost_pool."""
        self._it_subobject_codes = self._load_it_codes(subobjects_path)
        logger.info(
            f"IT spend ratio: {len(self._it_subobject_codes)} "
            f"IT subobject codes loaded"
        )

    def _load_it_codes(self, path: Path) -> Set[str]:
        """Extract IT subobject codes from subobjects CSV only."""
        path = Path(path)

        if path.suffix.lower() != ".csv":
            raise ValueError(f"Expected subobjects CSV, got: {path.suffix}")

        subobjects_df = pl.read_csv(path, encoding="utf8-lossy")
        required_cols = {"comptroller_subobject_code", "cost_pool"}
        missing_cols = required_cols - set(subobjects_df.columns)
        if missing_cols:
            raise ValueError(
                f"subobjects CSV missing required columns: {sorted(missing_cols)}"
            )

        codes = (
            subobjects_df
            .filter(pl.col("cost_pool").is_in(list(self.IT_COST_POOLS)))
            .select(
                pl.col("comptroller_subobject_code")
                .cast(pl.Utf8)
                .str.strip_chars()
                .str.zfill(4)
                .alias("comptroller_subobject_code")
            )
            .to_series()
            .to_list()
        )
        return set(codes)

    def compute_ratios(
        self,
        budget_path: str | Path,
        non_it_org_codes: Set[str],
    ) -> Dict[str, Dict]:
        """Compute IT spend ratio for each non-IT subprogram.

        Args:
            budget_path: Raw budget CSV with amount, organization_sub_code,
                         comptroller_subobject_code columns.
            non_it_org_codes: Set of organization_sub_codes that are NOT
                              known IT (output of designation filter).

        Returns:
            Dict keyed by organization_sub_code:
            {
                "it_spend": float,
                "total_spend": float,
                "it_ratio": float,
                "it_codes_used": list[str],
            }
        """
        budget_path = Path(budget_path)
        if budget_path.suffix.lower() == ".parquet":
            budget_df = pl.read_parquet(budget_path)
        else:
            budget_df = pl.read_csv(budget_path, encoding="utf8-lossy")

        # Filter to non-IT subprograms only
        budget_df = budget_df.filter(
            pl.col("organization_sub_code").is_in(list(non_it_org_codes))
        )

        logger.info(f"Computing IT spend ratios for {len(non_it_org_codes):,} subprograms")

        # Aggregate per subprogram
        ratios = {}
        grouped = (
            budget_df
            .group_by("organization_sub_code")
            .agg([
                pl.col("budget").cast(pl.Float64, strict=False).sum().alias("total_spend"),
                pl.col("budget")
                .filter(
                    pl.col("comptroller_subobject_code")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.zfill(4)
                    .is_in(list(self._it_subobject_codes))
                )
                .cast(pl.Float64, strict=False)
                .sum()
                .alias("it_spend"),
                pl.col("comptroller_subobject_code")
                .filter(
                    pl.col("comptroller_subobject_code")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.zfill(4)
                    .is_in(list(self._it_subobject_codes))
                )
                .cast(pl.Utf8)
                .unique()
                .alias("it_codes_used"),
            ])
        )

        for row in grouped.iter_rows(named=True):
            total = row["total_spend"] or 0
            it = row["it_spend"] or 0
            ratio = it / total if total > 0 else 0.0
            codes = row["it_codes_used"] if row["it_codes_used"] else []

            ratios[row["organization_sub_code"]] = {
                "it_spend": it,
                "total_spend": total,
                "it_ratio": ratio,
                "it_codes_used": codes,
            }

        nonzero = sum(1 for v in ratios.values() if v["it_ratio"] > 0)
        logger.info(f"IT spend ratios: {nonzero:,} subprograms with any IT spend")

        return ratios


# ── Signal 2: Taxonomy-Derived Keywords ────────────────────────

class TaxonomyKeywordMatcher:
    """Generate keywords from TBM taxonomy and match against subprogram names."""

    def __init__(self, towers_path: str | Path):
        self._keywords = self._generate_keywords(towers_path)
        # Compile boundary-aware, case-insensitive patterns once.
        self._keyword_patterns = [
            (
                kw,
                re.compile(
                    rf"(?<![A-Za-z0-9]){re.escape(kw)}(?![A-Za-z0-9])",
                    re.IGNORECASE,
                ),
            )
            for kw in sorted(self._keywords, key=len, reverse=True)
        ]
        logger.info(f"Taxonomy keywords: {len(self._keywords)} phrases generated")

    @staticmethod
    def _generate_keywords(towers_path: str | Path) -> List[str]:
        """Generate keyword phrases from TBM towers YAML.

        Extracts meaningful multi-word phrases from tower names,
        sub-tower names, and descriptions. Single common words
        like "data" or "network" are excluded to reduce false positives.
        """
        with open(towers_path, "r") as f:
            data = yaml.safe_load(f)

        keywords = set()

        for tower in data.get("towers", []):
            tower_name = tower["name"].lower()
            keywords.add(tower_name)

            for st in tower.get("sub_towers", []):
                st_name = st["name"].lower()
                keywords.add(st_name)

                # Multi-word sub-tower phrases are good keywords
                if len(st_name.split()) >= 2:
                    keywords.add(st_name)

        # Add general IT terms derived from common TBM vocabulary
        general = [
            "information technology", "information systems",
            "information system", "technology services",
            "technology initiative", "digital transformation",
            "digital equity", "digital services",
            "enterprise technology", "enterprise resource planning",
            "systems integration", "system modernization",
            "technology modernization", "cloud computing",
            "cloud migration", "cloud services",
            "data center", "data warehouse", "data analytics",
            "data processing", "database",
            "cybersecurity", "cyber security", "information security",
            "network infrastructure", "network security",
            "telecommunications", "telecom",
            "software development", "software engineering",
            "web portal", "web services",
            "helpdesk", "help desk", "service desk",
            "case management system", "electronic records",
            "electronic health", "electronic filing",
            "criminal justice information",
            "artificial intelligence", "machine learning",
            "robotic process automation",
        ]
        keywords.update(general)

        # Remove single common words that cause false positives
        false_positive_singles = {
            "data", "network", "security", "application",
            "storage", "compute", "platform", "end user",
        }
        keywords -= false_positive_singles

        return sorted(keywords)

    def match(self, subprograms: list[dict]) -> list[dict]:
        """Find subprograms with taxonomy keyword matches.

        Searches subprogram_name, program_name, and description.
        Returns matched records with _keyword_match field added.
        """
        matched = []

        for r in subprograms:
            name = str(r.get("subprogram_name", "") or "")
            prog = str(r.get("program_name", "") or "")
            desc = str(r.get("description", "") or "")[:200]
            combined = f"{name} {prog} {desc}"

            for kw, pattern in self._keyword_patterns:
                if pattern.search(combined):
                    r["_keyword_match"] = kw
                    matched.append(r)
                    break

        logger.info(f"Keyword matches: {len(matched)} from {len(subprograms)}")
        return matched


# ── Combined Pre-Filter ───────────────────────────────────────

class ShadowITPreFilter:
    """Combined pre-filter: designation filter + spend ratio + keywords."""

    DEFAULT_SPEND_THRESHOLD = 0.10  # 10% IT spend ratio

    def __init__(
        self,
        towers_path: str | Path,
        subobjects_path: str | Path,
        spend_threshold: float = DEFAULT_SPEND_THRESHOLD,
    ):
        self.spend_calculator = ITSpendRatioCalculator(subobjects_path)
        self.keyword_matcher = TaxonomyKeywordMatcher(towers_path)
        self.spend_threshold = spend_threshold

    @staticmethod
    def _resolve_is_it_column(df: pl.DataFrame) -> str:
        """Find existing designation column in subprograms input."""
        if "is_it" in df.columns:
            return "is_it"
        if "is_IT" in df.columns:
            return "is_IT"
        raise ValueError(
            "subprograms CSV must already contain designation column 'is_it' or 'is_IT'."
        )

    @staticmethod
    def _resolve_it_designation_column(df: pl.DataFrame) -> str:
        """Find existing IT designation column or provide a default name."""
        if "it_designation" in df.columns:
            return "it_designation"
        if "IT_designination" in df.columns:
            return "IT_designination"
        return "it_designation"

    def run(
        self,
        subprograms_path: str | Path,
        budget_path: str | Path,
    ) -> tuple[pl.DataFrame, list[dict], dict]:
        """Full pre-filter pipeline.

        Args:
            subprograms_path: All deduped subprograms CSV.
            budget_path: Raw budget CSV with amounts.

        Returns:
            (enriched_df, candidates, stats) — full rows with added shadow-it columns,
            candidate subset, and summary stats.
        """
        sub_path = Path(subprograms_path)
        budget_path = Path(budget_path)

        # Load subprograms
        full_df = pl.read_csv(sub_path, encoding="utf8-lossy")
        print(f"  Loaded {len(full_df):,} subprograms\n")

        # Step 1: Use existing designation columns from subprogram file
        print(f"  Step 1/3: Filtering known IT rows using existing designation columns")
        is_it_col = self._resolve_is_it_column(full_df)
        normalized_is_it = (
            pl.col(is_it_col)
            .cast(pl.Utf8)
            .str.to_lowercase()
            .is_in(["true", "1", "yes"])
        )
        known_it_df = full_df.filter(normalized_is_it)
        non_it_df = full_df.filter(~normalized_is_it)

        logger.info(
            "Designation split from existing column '{}': {:,} total -> {:,} known IT, {:,} non-IT",
            is_it_col,
            len(full_df),
            len(known_it_df),
            len(non_it_df),
        )
        print(f"  ✓ Removed {len(known_it_df):,} known IT")
        print(f"  ✓ {len(non_it_df):,} non-IT subprograms remain\n")

        if non_it_df.is_empty():
            empty_enriched = full_df.with_columns([
                pl.lit(None).cast(pl.Utf8).alias("shadow_it_reason"),
            ])
            return empty_enriched, [], {"known_it": len(known_it_df), "non_it": 0}

        non_it_records = non_it_df.to_dicts()

        # Step 2: Taxonomy keyword matching (required first gate)
        print(f"  Step 2/3: Matching against taxonomy-derived keywords")
        keyword_hits = self.keyword_matcher.match(non_it_records)
        keyword_codes = set(str(r.get("organization_sub_code", "")) for r in keyword_hits)
        print(f"  ✓ {len(keyword_codes):,} subprograms with keyword matches\n")

        # Step 3: IT spend ratio over keyword-matched rows only
        print(f"  Step 3/3: Computing IT spend ratios for keyword-matched rows")
        ratios = (
            self.spend_calculator.compute_ratios(budget_path, keyword_codes)
            if keyword_codes
            else {}
        )

        ratio_pass_codes = {
            code
            for code, ratio_data in ratios.items()
            if ratio_data.get("it_ratio", 0) >= self.spend_threshold
        }
        keyword_low_ratio = {
            code
            for code in keyword_codes
            if ratios.get(code, {}).get("it_ratio", 0) < self.spend_threshold
        }
        print(
            f"  ✓ {len(ratio_pass_codes):,} keyword-matched rows with "
            f"IT spend ratio ≥{self.spend_threshold*100:.0f}%"
        )
        print(
            f"  ✓ {len(keyword_low_ratio):,} keyword-matched rows below threshold (not marked)\n"
        )

        # Final candidates must satisfy BOTH: keyword match + spend threshold.
        candidate_codes = ratio_pass_codes

        # Build candidate list with signals
        candidates = []
        for r in non_it_records:
            code = str(r.get("organization_sub_code", ""))
            if code not in candidate_codes:
                continue

            ratio_data = ratios.get(code, {})
            r["_it_spend"] = ratio_data.get("it_spend", 0)
            r["_total_spend"] = ratio_data.get("total_spend", 0)
            r["_it_ratio"] = ratio_data.get("it_ratio", 0)
            r["_it_codes_used"] = ratio_data.get("it_codes_used", [])
            r["_signal_str"] = "keyword+spend_ratio"

            candidates.append(r)

        # Sort by IT ratio descending
        candidates.sort(
            key=lambda r: r["_it_ratio"],
            reverse=True,
        )

        # ── TLDR ───────────────────────────────────────────────
        stats = {
            "total": len(full_df),
            "known_it": len(known_it_df),
            "non_it": len(non_it_records),
            "keyword_candidates": len(keyword_codes),
            "ratio_pass_after_keyword": len(ratio_pass_codes),
            "keyword_below_threshold": len(keyword_low_ratio),
            "total_candidates": len(candidates),
        }

        print(f"{'='*60}")
        print(f"  SHADOW IT PRE-FILTER — TLDR")
        print(f"{'='*60}")
        print(f"  Total subprograms:       {stats['total']:,}")
        print(f"  Known IT (excluded):     {stats['known_it']:,}")
        print(f"  Non-IT scanned:          {stats['non_it']:,}")
        print(f"{'─'*60}")
        print(f"  Signal 1 — Taxonomy Keywords (required):")
        print(f"    Subprograms matched:   {stats['keyword_candidates']:>5}")
        print(f"  Signal 2 — IT Spend Ratio on keyword matches (≥{self.spend_threshold*100:.0f}%):")
        print(f"    Subprograms matched:   {stats['ratio_pass_after_keyword']:>5}")
        print(f"{'─'*60}")
        print(f"  Keyword but low ratio:   {stats['keyword_below_threshold']:>5}  (not marked)")
        print(f"  Marked shadow IT:        {stats['total_candidates']:>5}")
        print(f"{'─'*60}")
        print(f"  Total candidates:        {stats['total_candidates']:,} → Claude review")
        print(f"  Filtered out:            {stats['non_it'] - stats['total_candidates']:,}")
        print(f"  Reduction:               {(1 - stats['total_candidates'] / max(stats['non_it'], 1)) * 100:.1f}%")
        print(f"{'='*60}")

        # Top candidates
        if candidates:
            print(f"\n  Top 15 candidates (keyword + ratio threshold):")
            for r in candidates[:15]:
                name = str(r.get("subprogram_name", ""))[:35]
                agency = str(r.get("agency_name", ""))[:20]
                ratio = r["_it_ratio"]
                signal = r["_signal_str"]
                kw = r.get("_keyword_match", "")[:15]
                print(
                    f"    [{signal:<15}] {ratio:>5.1%}  {name:<35}  ({agency})"
                    f"{'  kw=' + kw if kw else ''}"
                )

        print()
        candidate_map = {
            str(r.get("organization_sub_code", "")): r
            for r in candidates
        }

        designation_col = self._resolve_it_designation_column(full_df)

        enriched_rows = []
        for row in full_df.to_dicts():
            code = str(row.get("organization_sub_code", ""))
            cand = candidate_map.get(code)

            if cand:
                row[is_it_col] = True
                row[designation_col] = "shadow_it"
                row["shadow_it_reason"] = json.dumps(
                    {
                        "signal": cand.get("_signal_str"),
                        "it_ratio": cand.get("_it_ratio"),
                        "it_spend": cand.get("_it_spend"),
                        "total_spend": cand.get("_total_spend"),
                        "keyword_match": cand.get("_keyword_match"),
                        "it_codes_used": cand.get("_it_codes_used", []),
                    },
                    ensure_ascii=True,
                )
            else:
                row["shadow_it_reason"] = None

            enriched_rows.append(row)

        enriched_df = pl.DataFrame(enriched_rows)
        return enriched_df, candidates, stats

    # ── Save ───────────────────────────────────────────────────

    @staticmethod
    def save_enriched(enriched_df: pl.DataFrame, output_path: str | Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            enriched_df.write_csv(output_path)
            saved_path = output_path
        except OSError as exc:
            # Common on Windows when CSV is open in Excel or editor preview.
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            fallback = output_path.with_name(f"{output_path.stem}_{stamp}{output_path.suffix}")
            logger.warning(
                "Could not write to {} ({}). Writing fallback output to {}",
                output_path,
                exc,
                fallback,
            )
            enriched_df.write_csv(fallback)
            saved_path = fallback

        candidate_rows = (
            enriched_df.filter(pl.col("shadow_it_reason").is_not_null()).height
            if enriched_df.height and "shadow_it_reason" in enriched_df.columns
            else 0
        )
        print(
            f"  Saved {enriched_df.height:,} rows (with {candidate_rows:,} shadow-IT candidates)"
            f" → {saved_path}"
        )
        return saved_path


def main():
    parser = argparse.ArgumentParser(description="Shadow IT pre-filter")
    parser.add_argument(
        "--subprograms",
        type=str,
        default="data/processed/subprograms.csv",
        help="All deduped subprograms CSV",
    )
    parser.add_argument(
        "--budget",
        type=str,
        default="data/processed/budget_cleaned.parquet",
        help="Budget input with amounts (parquet or csv)",
    )
    parser.add_argument(
        "--subobjects",
        type=str,
        default="data/processed/subobjects.csv",
        help="Subobjects CSV with cost_pool mapping",
    )
    parser.add_argument(
        "--towers",
        type=str,
        default="data/output/tbm_towers.yaml",
        help="TBM towers YAML",
    )
    parser.add_argument("--spend-threshold", type=float, default=0.10, help="IT spend ratio threshold (default 0.10)")
    parser.add_argument(
        "--output",
        type=str,
        default="data/processed/subprograms.csv",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Shadow IT Pre-Filter")
    print(f"{'='*60}\n")

    prefilter = ShadowITPreFilter(
        towers_path=args.towers,
        subobjects_path=args.subobjects,
        spend_threshold=args.spend_threshold,
    )

    enriched_df, candidates, stats = prefilter.run(args.subprograms, args.budget)
    prefilter.save_enriched(enriched_df, args.output)

    print(f"  Done. Next step:")
    print(f"    python -m src.agents.shadow_it_detector \\")
    print(f"        --candidates {args.output} \\")
    print(f"        --output data/output/shadow_it_detected.csv\n")


if __name__ == "__main__":
    main()
