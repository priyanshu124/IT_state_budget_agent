"""
Shadow IT Pre-Filter
======================
Keyword-only pre-filter that runs during the data pipeline. No API cost.

Signal — TAXONOMY KEYWORDS:
    Keywords are loaded only from manually curated config patterns.
    Catches programs that SAY they're IT while keeping matching behavior
    explicit and controllable.

A subprogram is a candidate if any taxonomy keyword matches in
subprogram/program/unit/agency fields.

Usage:
    python -m src.pipeline.shadow_it_prefilter \
        --subprograms data/processed/dim_subprogram.csv \
        --output data/processed/shadow_it_candidates.csv
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List

import polars as pl
from loguru import logger

from src.utils.config import get_config

# ── Signal 1: Taxonomy-Derived Keywords ────────────────────────

"""
TaxonomyKeywordMatcher — field-priority cascade with early exit
================================================================

Matching order (highest → lowest priority):
  1. subprogram_name
  2. program_name
  3. unit_name
  4. agency_name

A keyword match in any field immediately assigns shadow IT and stops.
Earlier fields are stronger signals.

A single keyword list is searched at each cascade level in priority order.
"""

# Field cascade — order is the contract
FIELD_CASCADE: list[str] = [
    "subprogram_name",
    "program_name",
    "unit_name",
    "agency_name",
]

class TaxonomyKeywordMatcher:
    """
    Keyword pre-filter with subprogram → program → unit → agency
    priority cascade. First field with a matching keyword wins.
    """

    def __init__(self):
        cfg = self._load_reference()

        self._patterns: list[tuple[str, re.Pattern]] = []
        self._negatives: list[re.Pattern] = []
        self._override_pat: re.Pattern

        self._compile(cfg)
        logger.info(
            "TaxonomyKeywordMatcher ready — {:d} patterns, {:d} negatives",
            len(self._patterns),
            len(self._negatives),
        )

    # ── Config ────────────────────────────────────────────────────────────────

    @staticmethod
    def _load_reference() -> dict:
        def _dedupe(items: list[str]) -> list[str]:
            seen: set[str] = set()
            ordered: list[str] = []
            for item in items:
                key = item.strip()
                if key and key not in seen:
                    seen.add(key)
                    ordered.append(key)
            return ordered

        def _normalize_manual_keywords(raw_kw: object) -> list[str]:
            """Normalize manual shadow_it_keywords config into a single list.

            Expected format:
              shadow_it_keywords:
                - "..."
                - "..."
            """
            if not isinstance(raw_kw, list):
                return []
            return [str(v) for v in raw_kw if str(v).strip()]

        cfg = get_config()
        patterns = _normalize_manual_keywords(cfg.get("shadow_it_keywords", []))

        return {
            "shadow_it_keywords": _dedupe(patterns),
            "shadow_it_negatives": cfg.get("shadow_it_negatives", []),
        }

    def _compile(self, cfg: dict) -> None:
        kw = cfg.get("shadow_it_keywords", [])
        neg_raw = cfg.get("shadow_it_negatives", [])

        def _build(raw: list[str]) -> list[tuple[str, re.Pattern]]:
            out = []
            # Longer phrases first — "data center" beats "data" within same field
            for p in sorted(set(raw), key=len, reverse=True):
                try:
                    out.append((p, re.compile(p, re.IGNORECASE)))
                except re.error as e:
                    logger.warning("Invalid regex '{}': {}", p, e)
            return out

        self._patterns = _build(kw)

        for p in neg_raw:
            try:
                self._negatives.append(re.compile(p, re.IGNORECASE))
            except re.error as e:
                logger.warning("Invalid negative regex '{}': {}", p, e)

        # Org-unit signal that bypasses negative suppression
        self._override_pat = re.compile(
            r"data office|office of (data|information)|chief information officer",
            re.IGNORECASE,
        )

    # ── Core cascade ──────────────────────────────────────────────────────────

    def _match_record(self, r: dict) -> tuple[str | None, str | None]:
        """
        Walk FIELD_CASCADE. Return (matched_pattern_str, field_name) on first
        hit, or (None, None) if no field matches.
        """
        # Build field strings once
        field_text: dict[str, str] = {
            field: str(r.get(field) or "")
            for field in FIELD_CASCADE
        }

        combined       = " ".join(field_text[f] for f in FIELD_CASCADE)
        name_combined  = " ".join(field_text[f] for f in FIELD_CASCADE)

        # Determine suppression once (applies to all fields)
        suppressed = (
            bool(self._negatives)
            and any(neg.search(combined) for neg in self._negatives)
            and not self._override_pat.search(name_combined)
        )
        if suppressed:
            return None, None

        # ── Walk cascade ──────────────────────────────────────────────────────
        for field in FIELD_CASCADE:
            text = field_text[field]
            if not text:
                continue

            for pat_str, pat in self._patterns:
                if pat.search(text):
                    return pat_str, field

        return None, None

    # ── Public API ────────────────────────────────────────────────────────────

    def match(self, subprograms: list[dict]) -> list[dict]:
        """
        Return subprograms with a shadow-IT keyword match.

        Adds to each matched record:
          _keyword_match  — regex pattern string that fired
          _match_field    — field where it fired
        """
        matched: list[dict] = []

        for r in subprograms:
            kw, field = self._match_record(r)
            if kw:
                r["_keyword_match"] = kw
                r["_match_field"]   = field
                matched.append(r)

        # Log signal breakdown by field
        by_field: dict[str, int] = {}
        for r in matched:
            f = r.get("_match_field", "unknown")
            by_field[f] = by_field.get(f, 0) + 1

        field_summary = ", ".join(
            f"{f}={by_field[f]}"
            for f in FIELD_CASCADE
            if f in by_field
        )
        logger.info(
            "Keyword matches: {:,} / {:,}  |  {}",
            len(matched),
            len(subprograms),
            field_summary,
        )
        return matched


# ── Combined Pre-Filter ───────────────────────────────────────

class ShadowITPreFilter:
    """Keyword-only pre-filter for shadow IT candidates."""

    def __init__(self):
        self.keyword_matcher = TaxonomyKeywordMatcher()

    @staticmethod
    def _resolve_is_it_column(df: pl.DataFrame) -> str | None:
        """Find existing designation column in subprograms input, if present."""
        if "is_it" in df.columns:
            return "is_it"
        if "is_IT" in df.columns:
            return "is_IT"
        return None

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
    ) -> tuple[pl.DataFrame, list[dict], dict]:
        """Keyword-only pre-filter pipeline.

        Args:
            subprograms_path: All deduped subprograms CSV.

        Returns:
            (enriched_df, candidates, stats) — full rows with added shadow-it
            columns, candidate subset, and summary stats.
        """
        sub_path = Path(subprograms_path)

        # Load subprograms
        full_df = pl.read_csv(sub_path, encoding="utf8-lossy")
        print(f"  Loaded {len(full_df):,} subprograms\n")

        # Step 1: Use existing designation columns from subprogram file when available.
        # If the input does not already carry an IT flag, keep every row in scope.
        print(f"  Step 1/3: Filtering known IT rows using existing designation columns")
        is_it_col = self._resolve_is_it_column(full_df)
        if is_it_col:
            normalized_is_it = (
                pl.col(is_it_col)
                .cast(pl.Utf8)
                .str.to_lowercase()
                .is_in(["true", "1", "yes"])
            )
            known_it_df = full_df.filter(normalized_is_it)
            non_it_df = full_df.filter(~normalized_is_it)
        else:
            known_it_df = full_df.head(0)
            non_it_df = full_df

        logger.info(
            "Designation split from existing column '{}': {:,} total -> {:,} known IT, {:,} non-IT",
            is_it_col or "<missing>",
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

        # Taxonomy keyword matching
        print(f"  Step 2/3: Matching against taxonomy-derived keywords")
        keyword_hits = self.keyword_matcher.match(non_it_records)
        keyword_codes = [str(r.get("organization_sub_code", "")) for r in keyword_hits]
        keyword_code_set = set(keyword_codes)
        print(f"  ✓ {len(keyword_code_set):,} subprograms with keyword matches\n")

        # Build candidate list with keyword signal only.
        # This is for reporting and downstream inspection only; the
        # returned/enriched dataset must still include every input row.
        candidates = []
        for r in non_it_records:
            code = str(r.get("organization_sub_code", ""))
            if code not in keyword_code_set:
                continue

            r["_signal_str"] = "keyword"

            candidates.append(r)

        # ── TLDR ───────────────────────────────────────────────
        stats = {
            "total": len(full_df),
            "known_it": len(known_it_df),
            "non_it": len(non_it_records),
            "keyword_candidates": len(keyword_code_set),
            "total_candidates": len(candidates),
        }

        print(f"{'='*60}")
        print(f"  SHADOW IT PRE-FILTER — TLDR")
        print(f"{'='*60}")
        print(f"  Total subprograms:       {stats['total']:,}")
        print(f"  Known IT (excluded):     {stats['known_it']:,}")
        print(f"  Non-IT scanned:          {stats['non_it']:,}")
        print(f"{'─'*60}")
        print(f"  Signal — Taxonomy Keywords:")
        print(f"    Subprograms matched:   {stats['keyword_candidates']:>5}")
        print(f"  Marked shadow IT:        {stats['total_candidates']:>5}")
        print(f"{'─'*60}")
        print(f"  Total candidates:        {stats['total_candidates']:,} → Claude review")
        print(f"  Filtered out:            {stats['non_it'] - stats['total_candidates']:,}")
        print(f"  Reduction:               {(1 - stats['total_candidates'] / max(stats['non_it'], 1)) * 100:.1f}%")
        print(f"{'='*60}")

        # Top candidates
        if candidates:
            print(f"\n  Top 15 candidates (keyword matches):")
            for r in candidates[:15]:
                name = str(r.get("subprogram_name", ""))[:35]
                agency = str(r.get("agency_name", ""))[:20]
                signal = r["_signal_str"]
                kw = r.get("_keyword_match", "")[:15]
                print(
                    f"    [{signal:<15}] {'':>5}  {name:<35}  ({agency})"
                    f"{'  kw=' + kw if kw else ''}"
                )

        print()
        candidate_map = {
            str(r.get("organization_sub_code", "")): r
            for r in candidates
        }

        # Build shadow_it columns in-order using the existing DataFrame to
        # preserve schema and avoid Polars' from-dicts type-inference issues.
        codes = [str(r) for r in full_df.select(pl.col("organization_sub_code")).to_series().to_list()]
        shadow_flags: list[bool] = []
        shadow_reasons: list[str | None] = []
        for code in codes:
            cand = candidate_map.get(code)
            shadow_flags.append(bool(cand))
            if cand:
                shadow_reasons.append(json.dumps({
                    "signal": cand.get("_signal_str"),
                    "keyword_match": cand.get("_keyword_match"),
                    "match_field": cand.get("_match_field"),
                }, ensure_ascii=True))
            else:
                shadow_reasons.append(None)

        enriched_df = full_df.with_columns([
            pl.Series("shadow_it", shadow_flags).cast(pl.Boolean),
            pl.Series("shadow_it_reason", shadow_reasons).cast(pl.Utf8),
        ])

        # If a row is marked shadow IT, set the IT designation and is_it flag.
        is_it_col_name = self._resolve_is_it_column(enriched_df) or "is_it"
        it_designation_col = self._resolve_it_designation_column(enriched_df)

        # Build expressions for is_it column: True where shadow_it, else preserve existing or False
        if is_it_col_name in enriched_df.columns:
            is_it_expr = pl.when(pl.col("shadow_it")).then(pl.lit(True)).otherwise(
                pl.col(is_it_col_name)
                .cast(pl.Utf8)
                .str.to_lowercase()
                .is_in(["true", "1", "yes"]) 
            ).alias(is_it_col_name)
        else:
            is_it_expr = pl.when(pl.col("shadow_it")).then(pl.lit(True)).otherwise(pl.lit(False)).alias(is_it_col_name)

        # Build expressions for it_designation: set to 'shadow_it' where shadow flag, else preserve or null
        if it_designation_col in enriched_df.columns:
            it_designation_expr = pl.when(pl.col("shadow_it")).then(pl.lit("shadow_it")).otherwise(pl.col(it_designation_col)).alias(it_designation_col)
        else:
            it_designation_expr = pl.when(pl.col("shadow_it")).then(pl.lit("shadow_it")).otherwise(pl.lit(None).cast(pl.Utf8)).alias(it_designation_col)

        enriched_df = enriched_df.with_columns([is_it_expr, it_designation_expr])

        # Remove the temporary `shadow_it` boolean column as requested
        if "shadow_it" in enriched_df.columns:
            enriched_df = enriched_df.drop("shadow_it")
        if enriched_df.height != full_df.height:
            raise RuntimeError(
                "Shadow IT enrichment must preserve all input rows; "
                f"expected {full_df.height:,}, got {enriched_df.height:,}."
            )
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
        "--output",
        type=str,
        default="data/processed/subprograms.csv",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Shadow IT Pre-Filter")
    print(f"{'='*60}\n")

    prefilter = ShadowITPreFilter()

    enriched_df, candidates, stats = prefilter.run(args.subprograms)
    prefilter.save_enriched(enriched_df, args.output)

    print(f"  Done. Next step:")
    print(f"    python -m src.agents.shadow_it_detector \\")
    print(f"        --candidates {args.output} \\")
    print(f"        --output data/output/shadow_it_detected.csv\n")


if __name__ == "__main__":
    main()
