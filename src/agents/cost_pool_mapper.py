"""
Agent 2: Cost Pool Mapper
=========================
Maps accounting subobject codes to TBM cost pools using Claude.

Sends all codes in a single API call using pipe-delimited format
for minimum token cost. Output is parsed and cached as a YAML
mapping file for deterministic reuse in all future pipeline runs.

Usage:
    python -m src.agents.cost_pool_mapper \
        --codes data/raw/subobject_codes.csv \
        --taxonomy data/raw/tbm/cost_pools.csv \
        --output data/output/cost_pool_mappings.csv

    # Or from code:
    from src.agents.cost_pool_mapper import CostPoolMapper
    mapper = CostPoolMapper(api_key="sk-ant-...")
    result = mapper.map_from_csv("data/raw/subobject_codes.csv", "data/raw/tbm/cost_pools.csv")
    mapper.save_csv(result, "data/output/cost_pool_mappings.csv")
"""

import csv
import argparse
from collections import OrderedDict
from pathlib import Path

from loguru import logger

from src.agents.base_agent import BaseAgent
from src.agents.prompts.map_cost_pools import SYSTEM_PROMPT, USER_PROMPT
from src.utils.config import CONFIG
from src.utils.tbm_reference import build_cost_pool_reference_text, resolve_reference_path
from src.utils.logging import setup_logging


class CostPoolMapper(BaseAgent):
    """Maps subobject codes to TBM cost pools via a single Claude call."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 16384,
    ):
        try:
            import anthropic
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self._token_calls: list[dict[str, int | str]] = []

    def _build_slim_taxonomy(self, taxonomy_path: Path) -> str:
        """Build a compact taxonomy string directly from the raw cost pool CSV."""
        return build_cost_pool_reference_text(taxonomy_path)

    @staticmethod
    def _load_valid_cost_pool_pairs(
        taxonomy_path: Path,
    ) -> tuple[list[tuple[str, str]], OrderedDict[str, list[str]]]:
        """Load valid (cost_pool, cost_sub_pool) pairs from raw TBM CSV."""
        with open(resolve_reference_path(taxonomy_path), encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))

        pairs: list[tuple[str, str]] = []
        pool_to_subpools: OrderedDict[str, list[str]] = OrderedDict()
        seen = set()

        for row in rows:
            pool = str(row.get("Cost Pool", "")).strip()
            sub_pool = str(row.get("Cost Sub-Pool", "")).strip()
            if not pool or not sub_pool:
                continue
            if pool.upper() == "RETIRED" or sub_pool.upper() == "RETIRED":
                continue

            key = (pool.lower(), sub_pool.lower())
            if key in seen:
                continue
            seen.add(key)

            pairs.append((pool, sub_pool))
            pool_to_subpools.setdefault(pool, []).append(sub_pool)

        return pairs, pool_to_subpools

    @staticmethod
    def _normalize_to_taxonomy(
        cost_pool: str,
        cost_sub_pool: str,
        valid_pairs: list[tuple[str, str]],
        pool_to_subpools: OrderedDict[str, list[str]],
    ) -> tuple[str, str, bool]:
        """Normalize model output to exact taxonomy names from CSV."""
        pool_raw = str(cost_pool or "").strip()
        sub_raw = str(cost_sub_pool or "").strip()

        pool_l = pool_raw.lower()
        sub_l = sub_raw.lower()

        # Exact pair match (case-insensitive)
        for pool, sub in valid_pairs:
            if pool.lower() == pool_l and sub.lower() == sub_l:
                return pool, sub, True

        # Pool matches, sub-pool fuzzy by case-insensitive exact value
        for pool, subpools in pool_to_subpools.items():
            if pool.lower() == pool_l:
                for sub in subpools:
                    if sub.lower() == sub_l:
                        return pool, sub, True
                # Keep pool and default sub-pool from this pool if invalid
                return pool, subpools[0], False

        # If sub-pool uniquely matches anywhere, use its canonical pool
        sub_matches = [(pool, sub) for pool, sub in valid_pairs if sub.lower() == sub_l]
        if len(sub_matches) == 1:
            return sub_matches[0][0], sub_matches[0][1], False

        # Deterministic fallback to first taxonomy pair
        if valid_pairs:
            return valid_pairs[0][0], valid_pairs[0][1], False

        return pool_raw, sub_raw, False

    def _build_codes_payload(self, codes_path: Path) -> tuple[str, int]:
        """Build pipe-delimited payload from CSV. Returns (payload, count)."""
        with open(codes_path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        lines = []
        for r in rows:
            code = r["comptroller_subobject_code"]
            name = r["comptroller_subobject_name"]
            obj = r["object_name"]
            lines.append(f"{code}|{name}|{obj}")

        return "\n".join(lines), len(lines)

    def _call_claude(self, taxonomy_str: str, codes_str: str) -> str:
        """Single API call — send all codes, get all mappings back."""
        user_prompt = USER_PROMPT.format(
            taxonomy=taxonomy_str,
            codes=codes_str,
        )

        logger.info(f"Calling Claude ({self.model}) — single pass for all codes...")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_text = response.content[0].text
        usage = response.usage
        total_tokens = usage.input_tokens + usage.output_tokens
        logger.info(
            f"Response: {len(raw_text)} chars | "
            f"stop={response.stop_reason} | "
            f"tokens in={usage.input_tokens} out={usage.output_tokens} total={total_tokens}"
        )

        self._token_calls.append(
            {
                "call_name": "cost_pool_mapper",
                "model": self.model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": total_tokens,
            }
        )

        cost_in = (usage.input_tokens / 1_000_000) * 3.00
        cost_out = (usage.output_tokens / 1_000_000) * 15.00
        logger.info(f"Cost: ${cost_in + cost_out:.4f} (in=${cost_in:.4f} out=${cost_out:.4f})")

        return raw_text

    def _parse_response(
        self,
        raw_response: str,
        expected_count: int,
        valid_pairs: list[tuple[str, str]],
        pool_to_subpools: OrderedDict[str, list[str]],
    ) -> list[dict]:
        """Parse pipe-delimited response into list of mapping dicts."""
        mappings = []
        lines = raw_response.strip().split("\n")
        corrected = 0

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) < 3:
                logger.warning(f"Skipping malformed line: {line}")
                continue

            normalized_pool, normalized_sub_pool, was_valid = self._normalize_to_taxonomy(
                parts[1].strip(),
                parts[2].strip(),
                valid_pairs,
                pool_to_subpools,
            )
            if not was_valid:
                corrected += 1

            mapping = {
                "comptroller_subobject_code": parts[0].strip(),
                "cost_pool": normalized_pool,
                "cost_sub_pool": normalized_sub_pool,
            }
            mappings.append(mapping)

        logger.info(f"Parsed {len(mappings)} mappings (expected {expected_count})")

        if len(mappings) < expected_count:
            logger.warning(
                f"Missing {expected_count - len(mappings)} mappings — "
                f"may need a follow-up call for missing codes"
            )

        if corrected:
            logger.warning(
                "Normalized {} mapping(s) to valid TBM CSV pool/sub-pool values",
                corrected,
            )

        return mappings

    def map_from_csv(
        self,
        codes_path: str | Path,
        taxonomy_path: str | Path,
    ) -> list[dict]:
        """Full pipeline: CSV + taxonomy → Claude → parsed mappings.

        Args:
            codes_path: CSV with comptroller_subobject_code, comptroller_subobject_name, object_name.
            taxonomy_path: Raw CSV reference file for TBM cost pools.

        Returns:
            List of dicts with code, cost_pool, cost_sub_pool.
        """
        codes_path = Path(codes_path)
        taxonomy_path = Path(taxonomy_path)
        taxonomy_path = resolve_reference_path(taxonomy_path)

        taxonomy_str = self._build_slim_taxonomy(taxonomy_path)
        valid_pairs, pool_to_subpools = self._load_valid_cost_pool_pairs(taxonomy_path)
        codes_str, count = self._build_codes_payload(codes_path)

        logger.info(f"Mapping {count} subobject codes to TBM cost pools")

        raw_response = self._call_claude(taxonomy_str, codes_str)
        return self._parse_response(raw_response, count, valid_pairs, pool_to_subpools)

    def execute(
        self,
        codes_path: str | Path,
        taxonomy_path: str | Path,
    ) -> list[dict]:
        """Base-agent execution entrypoint."""
        return self.map_from_csv(codes_path, taxonomy_path)

    def get_token_stats(self) -> dict[str, int | list[dict[str, int | str]]]:
        """Return aggregated token usage for all calls in this run."""
        total_input = sum(int(call["input_tokens"]) for call in self._token_calls)
        total_output = sum(int(call["output_tokens"]) for call in self._token_calls)
        return {
            "calls": self._token_calls,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
        }

    @staticmethod
    def save_csv(mappings: list[dict], output_path: str | Path) -> Path:
        """Save mappings as a CSV file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = ["comptroller_subobject_code", "cost_pool", "cost_sub_pool"]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(mappings)

        logger.info(f"Saved {len(mappings)} mappings to {output_path}")
        return output_path


def main():
    """CLI entry point."""
    setup_logging(level="INFO")
    cfg = CONFIG.get("cost_pool_mapper", {}) if isinstance(CONFIG, dict) else {}
    parser = argparse.ArgumentParser(
        description="Map subobject codes to TBM cost pools"
    )
    parser.add_argument("--codes", type=str, default="data/processed/subobject_codes.csv", help="CSV with subobject codes")
    parser.add_argument("--taxonomy", type=str, default=cfg.get("taxonomy", 'data/raw/tbm/cost_pools.csv'), help="Raw TBM cost-pool CSV reference")
    parser.add_argument("--output", type=str, default=cfg.get("output", "data/output/cost_pool_mappings.csv"))
    parser.add_argument("--model", type=str, default=cfg.get("model", "claude-sonnet-4-20250514"))
    args = parser.parse_args()

    import os
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-your"):
        print("ERROR: Set ANTHROPIC_API_KEY in your .env file")
        return

    codes_path = Path(args.codes)
    if not codes_path.exists():
        print(f"ERROR: Subobject codes file not found: {args.codes}")
        print("Hint: expected data/processed/subobject_codes.csv")
        return

    mapper = CostPoolMapper(api_key=api_key, model=args.model)
    mappings = mapper.run(codes_path, resolve_reference_path(args.taxonomy))
    output_path = mapper.save_csv(mappings, args.output)

    print(f"\n{'='*60}")
    print(f"  Cost Pool Mapping Complete")
    print(f"{'='*60}")
    print(f"  Codes mapped: {len(mappings)}")
    print(f"  Output:       {output_path}")
    print(f"{'='*60}\n")

    # Show distribution
    from collections import Counter
    pool_counts = Counter(m["cost_pool"] for m in mappings)
    print("Distribution:")
    for pool, count in pool_counts.most_common():
        print(f"  {pool:<25} {count:>4}")


if __name__ == "__main__":
    main()
