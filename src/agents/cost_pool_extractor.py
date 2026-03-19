"""
Agent 1: TBM Taxonomy Cost Pool Extractor
==========================================
Reads a TBM taxonomy PDF and produces a structured YAML config
containing all cost pools, sub-pools, and their definitions.

Sends the PDF directly to Claude via the document API — no text
extraction, no table parsing, no multi-page alignment issues.
Claude reads the tables natively from the PDF pages.

Supports --pages to send only relevant pages, cutting token cost ~10x.

This agent runs ONCE per taxonomy version. The output YAML becomes
the single source of truth for all downstream agents and classifiers.

Usage:
    python -m src.agents.taxonomy_extractor \
        --pdf path/to/TBM_Taxonomy.pdf \
        --pages 7-11 \
        --output configs/tbm_taxonomy_v5.yaml
"""

import base64
import io
import json
import argparse
from pathlib import Path

import yaml
from loguru import logger

from src.schemas.taxonomy import TBMTaxonomyCostPools
from src.agents.prompts.extract_cost_pools import SYSTEM_PROMPT, USER_PROMPT_PDF
from src.agents.base_agent import BaseAgent
from src.utils.anthropic import AnthropicClient
from src.utils.config import CONFIG, DATA_RAW
from src.utils.logging import setup_logging


class TaxonomyExtractor(BaseAgent):
    """Extracts TBM cost pool taxonomy from a PDF using Claude's native PDF support."""

    def __init__(self):
        self.llm = AnthropicClient()

    def _extract_pages(
        self,
        pdf_path: Path,
        start_page: int,
        end_page: int,
    ) -> bytes:
        """Extract a page range from a PDF and return as bytes.

        Args:
            pdf_path: Source PDF path.
            start_page: First page (1-indexed, inclusive).
            end_page: Last page (1-indexed, inclusive).

        Returns:
            Bytes of the trimmed PDF.
        """
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError:
            raise ImportError(
                "Install pypdf for page extraction: pip install pypdf"
            )

        reader = PdfReader(str(pdf_path))
        total_pages = len(reader.pages)

        # Clamp to valid range
        start_idx = max(0, start_page - 1)
        end_idx = min(total_pages, end_page)

        logger.info(
            f"Extracting pages {start_page}-{end_page} "
            f"from {total_pages} total pages"
        )

        writer = PdfWriter()
        for i in range(start_idx, end_idx):
            writer.add_page(reader.pages[i])

        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def _read_pdf_as_base64(
        self,
        pdf_path: Path,
        page_range: tuple[int, int] | None = None,
    ) -> str:
        """Read a PDF (or page range) and return base64-encoded content.

        Args:
            pdf_path: Path to the PDF file.
            page_range: Optional (start, end) 1-indexed inclusive.
                        If None, sends the full PDF.
        """
        if page_range:
            pdf_bytes = self._extract_pages(pdf_path, *page_range)
            size_kb = len(pdf_bytes) / 1024
            logger.info(f"Trimmed PDF: {size_kb:.0f} KB")
        else:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            size_kb = len(pdf_bytes) / 1024
            logger.info(f"Full PDF: {size_kb:.0f} KB")

        return base64.standard_b64encode(pdf_bytes).decode("utf-8")

    def _call_claude_with_pdf(
        self,
        pdf_base64: str,
        document_name: str,
    ) -> str:
        """Send the PDF directly to Claude and return raw response text."""
        user_content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_base64,
                },
            },
            {
                "type": "text",
                "text": USER_PROMPT_PDF.format(document_name=document_name),
            },
        ]

        logger.info("Calling Claude with native PDF...")

        response = self.llm.llm_call(
            call_name="taxonomy_extractor_pdf",
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        raw_text = response.content[0].text
        usage = response.usage
        logger.info(
            f"Response: {len(raw_text)} chars | "
            f"stop={response.stop_reason} | "
            f"tokens in={usage.input_tokens} out={usage.output_tokens} total={usage.input_tokens + usage.output_tokens}"
        )
        return raw_text

    def _parse_response(self, raw_response: str) -> TBMTaxonomyCostPools:
        """Parse Claude's JSON response into a validated Pydantic model."""
        cleaned = raw_response.strip()

        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}")
            logger.error(f"First 500 chars: {raw_response[:500]}")
            raise ValueError(f"Claude returned invalid JSON: {e}") from e

        try:
            result = TBMTaxonomyCostPools(**data)
        except Exception as e:
            logger.error(f"Pydantic validation failed: {e}")
            raise ValueError(f"Response doesn't match schema: {e}") from e

        logger.info(
            f"Extracted {len(result.cost_pools)} cost pools, "
            f"{len(result.get_all_sub_pool_names())} total sub-pools"
        )
        return result

    def extract_from_pdf(
        self,
        pdf_path: str | Path,
        page_range: tuple[int, int] | None = None,
    ) -> TBMTaxonomyCostPools:
        """Full pipeline: PDF -> Claude (native) -> validated Pydantic model.

        Args:
            pdf_path: Path to the TBM taxonomy PDF.
            page_range: Optional (start, end) pages to send (1-indexed, inclusive).
                        E.g. (7, 11) for the cost pool section.
                        If None, sends the full PDF.

        Returns:
            Validated TBMTaxonomyCostPools model.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        pdf_base64 = self._read_pdf_as_base64(pdf_path, page_range)

        raw_response = self._call_claude_with_pdf(
            pdf_base64=pdf_base64,
            document_name=pdf_path.name,
        )

        return self._parse_response(raw_response)

    def execute(
        self,
        pdf_path: str | Path,
        page_range: tuple[int, int] | None = None,
    ) -> TBMTaxonomyCostPools:
        """Base-agent execution entrypoint."""
        return self.extract_from_pdf(pdf_path, page_range=page_range)

    def get_token_stats(self) -> dict[str, int | list[dict[str, int | str]]]:
        """Expose Anthropic token usage collected by the shared client."""
        return self.llm.get_token_stats()

    def extract_from_text(
        self,
        text: str,
        document_name: str = "TBM Taxonomy",
    ) -> TBMTaxonomyCostPools:
        """Fallback: extract from pre-extracted text instead of PDF."""
        from src.agents.prompts.extract_cost_pools import USER_PROMPT_TEXT

        logger.info("Calling Claude with text input...")

        response = self.llm.llm_call(
            call_name="taxonomy_extractor_text",
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": USER_PROMPT_TEXT.format(
                    document_name=document_name,
                    document_text=text,
                ),
            }],
        )

        raw_text = response.content[0].text
        usage = response.usage
        logger.info(
            f"Response: {len(raw_text)} chars | "
            f"tokens in={usage.input_tokens} out={usage.output_tokens} total={usage.input_tokens + usage.output_tokens}"
        )
        return self._parse_response(raw_text)

    @staticmethod
    def save_yaml(result: TBMTaxonomyCostPools, output_path: str | Path) -> Path:
        """Save extracted taxonomy to YAML."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            yaml.dump(
                result.to_yaml_dict(),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=100,
            )

        logger.info(f"Saved to {output_path}")
        return output_path

    @staticmethod
    def load_yaml(yaml_path: str | Path) -> TBMTaxonomyCostPools:
        """Load a previously extracted taxonomy config from YAML."""
        yaml_path = Path(yaml_path)
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        metadata = data.get("metadata", {})
        return TBMTaxonomyCostPools(
            tbm_version=metadata.get("tbm_version", "unknown"),
            source_document=metadata.get("source_document", "unknown"),
            cost_pools=data.get("cost_pools", []),
        )


def _parse_page_range(s: str) -> tuple[int, int]:
    """Parse '7-11' into (7, 11)."""
    parts = s.split("-")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"Invalid page range: {s}. Use format: 7-11")
    return int(parts[0]), int(parts[1])


def _get_taxonomy_extractor_config() -> dict:
    """Read taxonomy extractor defaults from the main YAML config."""
    cfg = CONFIG.get("taxonomy_extractor", {})
    return cfg if isinstance(cfg, dict) else {}


def _resolve_page_range(value: str | list[int] | tuple[int, int] | None) -> tuple[int, int] | None:
    """Normalize page-range config/CLI input into a (start, end) tuple."""
    if value is None:
        return None
    if isinstance(value, str):
        return _parse_page_range(value)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    raise ValueError("Invalid pages value. Use '7-11' or [7, 11].")


def _resolve_pdf_path(cli_pdf: str | None, cfg_pdf: str | None) -> Path:
    """Resolve taxonomy PDF path from CLI/config or auto-pick from data/raw."""
    pdf_value = cli_pdf or cfg_pdf
    if pdf_value:
        pdf_path = Path(pdf_value)
        if pdf_path.exists():
            return pdf_path

        fallback_path = DATA_RAW / pdf_value
        if fallback_path.exists():
            return fallback_path

        raise FileNotFoundError(
            f"Taxonomy PDF not found: {pdf_value}"
        )

    candidates = sorted(
        p for p in DATA_RAW.glob("*.pdf") if p.is_file()
    )
    if not candidates:
        raise ValueError(
            "No taxonomy PDF found. Set taxonomy_extractor.pdf in configs/tbm.yaml, "
            "pass --pdf, or place a PDF in data/raw/."
        )
    if len(candidates) > 1:
        logger.warning(
            f"Multiple PDFs found in {DATA_RAW}; using {candidates[0].name}"
        )
    return candidates[0]


def main():
    """CLI entry point."""
    setup_logging(level="INFO")
    cfg = _get_taxonomy_extractor_config()

    parser = argparse.ArgumentParser(
        description="Extract TBM cost pool taxonomy from a PDF"
    )
    parser.add_argument("--pdf", type=str, default=cfg.get("pdf"), help="Path to TBM taxonomy PDF")
    parser.add_argument(
        "--pages", type=str, default=cfg.get("pages"),
        help="Page range to extract, e.g. '7-11'. Reduces token cost. If omitted, sends full PDF."
    )
    parser.add_argument("--output", type=str, default=cfg.get("output", "data/output/tbm_taxonomy.yaml"))
    args = parser.parse_args()

    pdf_path = _resolve_pdf_path(args.pdf, cfg.get("pdf"))

    page_range = _resolve_page_range(args.pages)

    extractor = TaxonomyExtractor()
    result = extractor.run(pdf_path, page_range=page_range)
    output_path = extractor.save_yaml(result, args.output)

    print(f"\n{'='*60}")
    print(f"  TBM Taxonomy Extraction Complete")
    print(f"{'='*60}")
    print(f"  Version:    {result.tbm_version}")
    print(f"  Cost Pools: {len(result.cost_pools)}")
    print(f"  Sub-Pools:  {len(result.get_all_sub_pool_names())}")
    print(f"  Output:     {output_path}")
    print(f"{'='*60}\n")

    for cp in result.cost_pools:
        opex = len(cp.opex_sub_pools)
        capex = len(cp.capex_sub_pools)
        print(f"  {cp.name} ({opex} opex, {capex} capex)")

    print(f"\n{'='*60}")
    print("  TOKEN USAGE")
    print(f"{'='*60}")
    token_stats = extractor.llm.get_token_stats()
    for call in token_stats["calls"]:
        print(
            f"  {call['call_name']}: in={call['input_tokens']} "
            f"out={call['output_tokens']} total={call['total_tokens']} "
            f"model={call['model']}"
        )
    print(
        f"  TOTAL: in={token_stats['total_input_tokens']} "
        f"out={token_stats['total_output_tokens']} "
        f"total={token_stats['total_tokens']}"
    )
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
