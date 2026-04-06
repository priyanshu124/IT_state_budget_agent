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
        --taxonomy configs/tbm_taxonomy_v5.yaml \
        --output configs/cost_pool_mappings.yaml

    # Or from code:
    from src.agents.cost_pool_mapper import CostPoolMapper
    mapper = CostPoolMapper(api_key="sk-ant-...")
    result = mapper.map_from_csv("data/raw/subobject_codes.csv", "configs/tbm_taxonomy_v5.yaml")
    mapper.save_yaml(result, "configs/cost_pool_mappings.yaml")
"""

import csv
import json
import argparse
from pathlib import Path

import yaml
from loguru import logger

from src.agents.base_agent import BaseAgent
from src.agents.prompts.map_cost_pools import SYSTEM_PROMPT, USER_PROMPT
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
        """Build a minimal taxonomy string — just pool and sub-pool names."""
        with open(taxonomy_path, "r") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict) or "cost_pools" not in data:
            if isinstance(data, dict) and "towers" in data:
                raise ValueError(
                    f"Expected cost-pool taxonomy YAML but got towers YAML: {taxonomy_path}. "
                    "Use data/output/tbm_taxonomy.yaml (from cost_pool_extractor), not a towers file."
                )
            raise ValueError(
                f"Invalid taxonomy YAML format in {taxonomy_path}: missing top-level 'cost_pools' key."
            )

        lines = []
        for cp in data["cost_pools"]:
            lines.append(cp["name"])
            for sp in cp.get("opex_sub_pools", []):
                lines.append(f"  - {sp['name']}")
            for sp in cp.get("capex_sub_pools", []):
                lines.append(f"  - {sp['name']} (CapEx)")
        return "\n".join(lines)

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

    def _parse_response(self, raw_response: str, expected_count: int) -> list[dict]:
        """Parse pipe-delimited response into list of mapping dicts."""
        mappings = []
        lines = raw_response.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) < 3:
                logger.warning(f"Skipping malformed line: {line}")
                continue

            mapping = {
                "comptroller_subobject_code": parts[0].strip(),
                "cost_pool": parts[1].strip(),
                "cost_sub_pool": parts[2].strip(),
            }
            mappings.append(mapping)

        logger.info(f"Parsed {len(mappings)} mappings (expected {expected_count})")

        if len(mappings) < expected_count:
            logger.warning(
                f"Missing {expected_count - len(mappings)} mappings — "
                f"may need a follow-up call for missing codes"
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
            taxonomy_path: YAML taxonomy config (output of Agent 1).

        Returns:
            List of dicts with code, cost_pool, cost_sub_pool.
        """
        codes_path = Path(codes_path)
        taxonomy_path = Path(taxonomy_path)

        taxonomy_str = self._build_slim_taxonomy(taxonomy_path)
        codes_str, count = self._build_codes_payload(codes_path)

        logger.info(f"Mapping {count} subobject codes to TBM cost pools")

        raw_response = self._call_claude(taxonomy_str, codes_str)
        return self._parse_response(raw_response, count)

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
    def save_yaml(mappings: list[dict], output_path: str | Path) -> Path:
        """Save mappings as a YAML lookup file.

        Output format:
            mappings:
              "858":
                cost_pool: "Software & SaaS"
                cost_sub_pool: "Licensing"
              "101":
                cost_pool: "Staffing"
                cost_sub_pool: "Internal Labor"
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert list to dict keyed by code for fast lookup
        lookup = {}
        for m in mappings:
            lookup[m["comptroller_subobject_code"]] = {
                "cost_pool": m["cost_pool"],
                "cost_sub_pool": m["cost_sub_pool"],
            }

        with open(output_path, "w") as f:
            yaml.dump(
                {"mappings": lookup},
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=100,
            )

        logger.info(f"Saved {len(lookup)} mappings to {output_path}")
        return output_path

    @staticmethod
    def load_yaml(yaml_path: str | Path) -> dict[str, dict]:
        """Load cached mappings. Returns dict keyed by subobject code."""
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        return data.get("mappings", {})


def main():
    """CLI entry point."""
    setup_logging(level="INFO")
    parser = argparse.ArgumentParser(
        description="Map subobject codes to TBM cost pools"
    )
    parser.add_argument("--codes", type=str, default='data/processed/subobjects.csv', help="CSV with subobject codes")
    parser.add_argument("--taxonomy", type=str, default='data/output/tbm_taxonomy.yaml', help="TBM taxonomy YAML")
    parser.add_argument("--output", type=str, default="configs/cost_pool_mappings.yaml")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-20250514")
    args = parser.parse_args()

    import os
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-your"):
        print("ERROR: Set ANTHROPIC_API_KEY in your .env file")
        return

    mapper = CostPoolMapper(api_key=api_key, model=args.model)
    mappings = mapper.run(args.codes, args.taxonomy)
    output_path = mapper.save_yaml(mappings, args.output)

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
