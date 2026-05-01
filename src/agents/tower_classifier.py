"""
Agent 3: IT Tower Classifier
==============================
Two-step agent:
  1. Deterministic filter: select only confirmed IT subprograms
     (using is_IT flag from designation classifier output).
  2. Single Claude call: classify all IT subprograms into TBM
     resource towers.

Input format varies by designation (unit_name included):
    - MITDP/ITIF: code|subprogram_name|agency_name|unit_name|program_name
    - F50_AGENCY: code|subprogram_name|agency_name|unit_name|program_name
    - SHADOW_IT:  code|subprogram_name|agency_name|unit_name|program_name|shadow_it_reason

The model must still validate whether each row is truly IT-related even after the deterministic is_it filter.

Usage:
    python -m src.agents.tower_classifier \
        --subprograms data/processed/subprogram.csv \
        --towers data/raw/tbm/it_towers.csv \
        --output configs/tower_classifications.yaml \
        --csv data/output/tower_classifications.csv
"""

import csv
import argparse
from pathlib import Path

import yaml
from loguru import logger

from src.agents.base_agent import BaseAgent
from src.agents.prompts.classify_towers import SYSTEM_PROMPT, USER_PROMPT
from src.utils.tbm_reference import build_tower_reference_text
from src.utils.config import CONFIG, DATA_OUTPUT, DATA_PROCESSED
from src.utils.logging import setup_logging


class TowerClassifier(BaseAgent):
    """Classifies confirmed IT subprograms into TBM resource towers."""

    # Max characters of description to send for classification.
    # 150 chars usually captures the key sentence without wasting tokens.
    F50_DESC_LIMIT = 150

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

    # ── Step 1: Deterministic IT filter ────────────────────────

    @staticmethod
    def _record_code(row: dict) -> str:
        """Return the preferred record identifier for LLM classification."""
        return str(
            row.get("organization_sub_code")
        ).strip()

    @staticmethod
    def _resolve_it_flag_column(rows: list[dict]) -> str:
        """Use exact is_it column from subprograms.csv for IT filtering."""
        if not rows:
            return "is_it"

        if "is_it" not in rows[0]:
            raise ValueError("Subprogram CSV must contain exact column: is_it")

        return "is_it"

    @staticmethod
    def _resolve_designation_column(rows: list[dict]) -> str:
        """Use exact it_designation column from subprograms.csv."""
        if not rows:
            return "it_designation"

        if "it_designation" not in rows[0]:
            raise ValueError("Subprogram CSV must contain exact column: it_designation")

        return "it_designation"

    @staticmethod
    def _designation_format(designation: str) -> str:
        normalized = designation.strip().upper()
        if normalized in {"MITDP", "ITIF"}:
            return "slim"
        if normalized == "SHADOW_IT":
            return "shadow_it"
        return "enriched"

    def _load_it_subprograms(self, subprograms_path: Path) -> list[dict]:
        """Load CSV and return only confirmed IT subprograms."""
        with open(subprograms_path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        total = len(rows)
        it_flag_col = self._resolve_it_flag_column(rows)
        desig_col = self._resolve_designation_column(rows)

        it_rows = [
            r for r in rows
            if str(r.get(it_flag_col, "")).strip().upper() == "TRUE"
        ]

        # Log breakdown by designation
        from collections import Counter
        desig_counts = Counter(r.get(desig_col, "").strip() for r in it_rows)
        logger.info(
            "Loaded {} subprograms, {} confirmed IT using column {}",
            total,
            len(it_rows),
            it_flag_col,
        )
        for d, c in desig_counts.most_common():
            logger.info(f"  {d}: {c}")

        return it_rows

    # ── Step 2: Build payloads ─────────────────────────────────

    def _build_slim_taxonomy(self, towers_path: Path) -> str:
        """Build a compact tower taxonomy string from the raw CSV reference."""
        return build_tower_reference_text(towers_path)

    def _build_records_payload(self, it_rows: list[dict]) -> str:
        """Build pipe-delimited payload exactly as classify_towers prompt expects.

        Each designation gets its own input format so the prompt can reason from the right fields.
        """
        desig_col = self._resolve_designation_column(it_rows)

        def _clean_field(value: str | None) -> str:
            text = str(value or "")
            # Keep one record per line and one field per pipe segment.
            return text.replace("|", " /").replace("\n", " ").replace("\r", " ").strip()

        lines = []
        for r in it_rows:
            code = self._record_code(r)
            name = _clean_field(r.get("subprogram_name"))
            agency = _clean_field(r.get("agency_name"))
            unit = _clean_field(r.get("unit_name", ""))
            program = _clean_field(r.get("program_name", ""))
            desc = _clean_field(r.get("description", "")[:self.F50_DESC_LIMIT])
            reason = _clean_field(r.get("shadow_it_reason", ""))
            design = self._designation_format(r.get(desig_col, ""))

            if design == "slim":
                # Include unit_name + program_name for MITDP/ITIF (slim) format
                lines.append(f"{code}|{name}|{agency}|{unit}|{program}")
            elif design == "shadow_it":
                # Include unit_name and shadow reason only
                lines.append(f"{code}|{name}|{agency}|{unit}|{program}|{reason}")
            else:
                # Enriched records: include unit_name (no description)
                lines.append(f"{code}|{name}|{agency}|{unit}|{program}")

        return "\n".join(lines)

    # ── Step 3: Claude call ────────────────────────────────────

    def _call_claude(self, taxonomy_str: str, records_str: str) -> str:
        """Single API call — all IT subprograms classified at once."""
        user_prompt = USER_PROMPT.format(
            taxonomy=taxonomy_str,
            records=records_str,
        )

        logger.info(f"Calling Claude ({self.model}) — classifying all IT subprograms...")

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
                "call_name": "tower_classifier",
                "model": self.model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": total_tokens,
            }
        )

        cost_in = (usage.input_tokens / 1_000_000) * 3.00
        cost_out = (usage.output_tokens / 1_000_000) * 15.00
        logger.info(f"Cost: ${cost_in + cost_out:.4f}")

        return raw_text

    # ── Step 4: Parse response ─────────────────────────────────

    def _parse_response(
        self,
        raw_response: str,
        it_rows: list[dict],
        expected_count: int,
    ) -> list[dict]:
        """Parse pipe-delimited response and merge with original row data."""
        row_lookup = {self._record_code(r): r for r in it_rows}
        desig_col = self._resolve_designation_column(it_rows)

        results = []
        lines = raw_response.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) < 4:
                logger.warning(f"Skipping malformed line: {line}")
                continue

            code = parts[0].strip()
            tower = parts[1].strip()
            sub_tower = parts[2].strip()

            try:
                confidence = float(parts[3].strip())
            except ValueError:
                logger.warning(f"Bad confidence value in: {line}")
                confidence = 0.5

            original = row_lookup.get(code, {})

            results.append({
                "organization_sub_code": code,
                "subprogram_code": original.get("subprogram_code", ""),
                "subprogram_name": original.get("subprogram_name", ""),
                "agency_name": original.get("agency_name", ""),
                "it_designation": original.get(desig_col, ""),
                "tower": tower,
                "sub_tower": sub_tower,
                "confidence": confidence,
            })

        logger.info(f"Parsed {len(results)} classifications (expected {expected_count})")

        if len(results) < expected_count:
            classified_codes = {r["organization_sub_code"] for r in results}
            all_codes = {self._record_code(r) for r in it_rows}
            missing = all_codes - classified_codes
            logger.warning(f"Missing {len(missing)} codes: {missing}")

        return results

    # ── Main pipeline ──────────────────────────────────────────

    def classify(
        self,
        subprograms_path: str | Path,
        towers_path: str | Path,
    ) -> list[dict]:
        """Full pipeline: CSV → filter IT → Claude → classified results.

        Args:
            subprograms_path: CSV with subprogram data (must have is_IT column).
            towers_path: Raw CSV reference file for TBM towers.
        """
        subprograms_path = Path(subprograms_path)
        towers_path = Path(towers_path)

        # Step 1: Filter to IT only
        it_rows = self._load_it_subprograms(subprograms_path)
        if not it_rows:
            logger.warning("No IT subprograms found")
            return []

        # Step 2: Build payloads
        taxonomy_str = self._build_slim_taxonomy(towers_path)
        records_str = self._build_records_payload(it_rows)

        logger.info(f"Taxonomy: ~{len(taxonomy_str) // 4} tokens")
        logger.info(f"Records: {len(it_rows)} subprograms, ~{len(records_str) // 4} tokens")

        # Step 3: Classify
        raw_response = self._call_claude(taxonomy_str, records_str)

        # Step 4: Parse
        return self._parse_response(raw_response, it_rows, len(it_rows))

    def execute(
        self,
        subprograms_path: str | Path,
        towers_path: str | Path,
    ) -> list[dict]:
        """Base-agent execution entrypoint."""
        return self.classify(subprograms_path, towers_path)

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

    # ── Save / Load ────────────────────────────────────────────

    @staticmethod
    def save_csv(results: list[dict], output_path: str | Path) -> Path:
        """Save classifications as CSV keyed by organization_sub_code."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "organization_sub_code",
            "subprogram_code",
            "subprogram_name",
            "agency_name",
            "it_designation",
            "tower",
            "sub_tower",
            "confidence",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        logger.info(f"Saved {len(results)} classifications to {output_path}")
        return output_path

    @staticmethod
    def load_yaml(yaml_path: str | Path) -> dict[str, dict]:
        """Load cached classifications."""
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        return data.get("classifications", {})


def main():
    """CLI entry point."""
    setup_logging(level="INFO")
    cfg = CONFIG.get("tower_classifier", {}) if isinstance(CONFIG, dict) else {}

    def _resolve_path(cli_value: str | None, cfg_value: str | None, fallback: Path) -> Path:
        chosen = cli_value if cli_value else cfg_value
        if chosen:
            candidate = Path(chosen)
            if candidate.exists():
                return candidate

            fallback_candidate = DATA_PROCESSED / chosen
            if fallback_candidate.exists():
                return fallback_candidate

            if fallback.exists():
                logger.warning(
                    "Configured path '{}' not found. Falling back to '{}'",
                    chosen,
                    fallback,
                )
                return fallback

            return candidate
        return fallback

    parser = argparse.ArgumentParser(
        description="Classify IT subprograms into TBM resource towers"
    )
    parser.add_argument(
        "--subprograms",
        type=str,
        default=cfg.get("subprograms", "data/processed/subprograms.csv"),
        help="Subprogram CSV path (defaults to tower_classifier.subprograms or data/processed/subprograms.csv)",
    )
    parser.add_argument(
        "--towers",
        type=str,
        default=cfg.get("towers", "data/raw/tbm/it_towers.csv"),
        help="Tower reference CSV path (defaults to tower_classifier.towers or data/raw/tbm/it_towers.csv)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=cfg.get("output", "data/output/tower_classifications.csv"),
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="data/output/tower_classifications.csv",
        help="Optional secondary CSV output path; leave blank to skip duplicate write.",
    )
    parser.add_argument("--model", type=str, default=cfg.get("model", "claude-sonnet-4-20250514"))
    args = parser.parse_args()

    import os
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-your"):
        print("ERROR: Set ANTHROPIC_API_KEY in your .env file")
        return

    subprograms_path = _resolve_path(args.subprograms, cfg.get("subprograms"), DATA_PROCESSED / "subprograms.csv")
    towers_path = _resolve_path(args.towers, cfg.get("towers"), Path("data/raw/tbm/it_towers.csv"))

    if not subprograms_path.exists():
        raise FileNotFoundError(
            f"Subprogram file not found: {subprograms_path}. "
            "Set tower_classifier.subprograms in configs/tbm.yaml or pass --subprograms."
        )
    if not towers_path.exists():
        raise FileNotFoundError(
            f"Tower taxonomy file not found: {towers_path}. "
            "Set tower_classifier.towers in configs/tbm.yaml or pass --towers."
        )

    classifier = TowerClassifier(api_key=api_key, model=args.model)
    results = classifier.classify(subprograms_path, towers_path)

    output_path = classifier.save_csv(results, args.output)
    if args.csv and Path(args.csv) != Path(args.output):
        classifier.save_csv(results, args.csv)

    print(f"\n{'='*60}")
    print(f"  IT Tower Classification Complete")
    print(f"{'='*60}")
    print(f"  Classified: {len(results)}")
    print(f"  Output:     {output_path}")
    print(f"{'='*60}\n")

    from collections import Counter
    tower_counts = Counter(r["tower"] for r in results)
    print("Tower Distribution:")
    for tower, count in tower_counts.most_common():
        print(f"  {tower:<25} {count:>4}")

    low = sum(1 for r in results if r["confidence"] < 0.7)
    med = sum(1 for r in results if 0.7 <= r["confidence"] < 0.9)
    high = sum(1 for r in results if r["confidence"] >= 0.9)
    print(f"\nConfidence: high(>=0.9)={high}  med(0.7-0.9)={med}  low(<0.7)={low}")


if __name__ == "__main__":
    main()
