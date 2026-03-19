"""
Agent 1b: TBM Resource Tower Extractor
=======================================
Reads a TBM taxonomy PDF and produces a structured YAML config
containing all resource towers, their domains, sub-towers, and definitions.

Same architecture as Agent 1a (cost pool extractor) — sends PDF
natively to Claude, supports --pages for token savings.

This agent runs ONCE per taxonomy version.

Usage:
    python -m src.agents.tower_extractor \
        --pdf path/to/TBM_Taxonomy.pdf \
        --pages 12-20 \
        --output configs/tbm_towers.yaml
"""

import base64
import io
import json
import argparse
from pathlib import Path

import yaml
from loguru import logger

from src.schemas.taxonomy import TBMTaxonomyTowers
from src.agents.prompts.extract_towers import SYSTEM_PROMPT, USER_PROMPT_PDF


class TowerExtractor:
    """Extracts TBM resource towers from a PDF using Claude's native PDF support."""

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

    def _extract_pages(
        self,
        pdf_path: Path,
        start_page: int,
        end_page: int,
    ) -> bytes:
        """Extract a page range from a PDF and return as bytes."""
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError:
            raise ImportError("Install pypdf: pip install pypdf")

        reader = PdfReader(str(pdf_path))
        total_pages = len(reader.pages)

        start_idx = max(0, start_page - 1)
        end_idx = min(total_pages, end_page)

        logger.info(f"Extracting pages {start_page}-{end_page} from {total_pages} total")

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
        """Read a PDF (or page range) and return base64-encoded content."""
        if page_range:
            pdf_bytes = self._extract_pages(pdf_path, *page_range)
            logger.info(f"Trimmed PDF: {len(pdf_bytes) / 1024:.0f} KB")
        else:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            logger.info(f"Full PDF: {len(pdf_bytes) / 1024:.0f} KB")

        return base64.standard_b64encode(pdf_bytes).decode("utf-8")

    def _call_claude_with_pdf(self, pdf_base64: str, document_name: str) -> str:
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

        logger.info(f"Calling Claude ({self.model}) with native PDF for tower extraction...")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        raw_text = response.content[0].text
        usage = response.usage
        logger.info(
            f"Response: {len(raw_text)} chars | "
            f"stop={response.stop_reason} | "
            f"tokens in={usage.input_tokens} out={usage.output_tokens}"
        )

        cost_in = (usage.input_tokens / 1_000_000) * 3.00
        cost_out = (usage.output_tokens / 1_000_000) * 15.00
        logger.info(f"Cost: ${cost_in + cost_out:.4f}")

        return raw_text

    def _parse_response(self, raw_response: str) -> TBMTaxonomyTowers:
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
            result = TBMTaxonomyTowers(**data)
        except Exception as e:
            logger.error(f"Pydantic validation failed: {e}")
            raise ValueError(f"Response doesn't match schema: {e}") from e

        logger.info(
            f"Extracted {len(result.towers)} towers, "
            f"{len(result.get_all_sub_tower_names())} total sub-towers"
        )
        return result

    def extract_from_pdf(
        self,
        pdf_path: str | Path,
        page_range: tuple[int, int] | None = None,
    ) -> TBMTaxonomyTowers:
        """Full pipeline: PDF -> Claude (native) -> validated Pydantic model.

        Args:
            pdf_path: Path to the TBM taxonomy PDF.
            page_range: Optional (start, end) pages (1-indexed, inclusive).
                        E.g. (12, 20) for the resource towers section.
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

    @staticmethod
    def save_yaml(result: TBMTaxonomyTowers, output_path: str | Path) -> Path:
        """Save extracted towers to YAML."""
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
    def load_yaml(yaml_path: str | Path) -> TBMTaxonomyTowers:
        """Load a previously extracted tower config from YAML."""
        yaml_path = Path(yaml_path)
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        metadata = data.get("metadata", {})
        return TBMTaxonomyTowers(
            tbm_version=metadata.get("tbm_version", "unknown"),
            source_document=metadata.get("source_document", "unknown"),
            towers=data.get("towers", []),
        )


def _parse_page_range(s: str) -> tuple[int, int]:
    """Parse '12-20' into (12, 20)."""
    parts = s.split("-")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"Invalid page range: {s}. Use format: 12-20")
    return int(parts[0]), int(parts[1])


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract TBM resource towers from a PDF"
    )
    parser.add_argument("--pdf", type=str, required=True, help="Path to TBM taxonomy PDF")
    parser.add_argument(
        "--pages", type=str, default=None,
        help="Page range, e.g. '12-20'. Reduces token cost."
    )
    parser.add_argument("--output", type=str, default="configs/tbm_towers.yaml")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-20250514")
    args = parser.parse_args()

    import os
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-your"):
        print("ERROR: Set ANTHROPIC_API_KEY in your .env file")
        return

    page_range = _parse_page_range(args.pages) if args.pages else None

    extractor = TowerExtractor(api_key=api_key, model=args.model)
    result = extractor.extract_from_pdf(args.pdf, page_range=page_range)
    output_path = extractor.save_yaml(result, args.output)

    print(f"\n{'='*60}")
    print(f"  TBM Tower Extraction Complete")
    print(f"{'='*60}")
    print(f"  Version:     {result.tbm_version}")
    print(f"  Towers:      {len(result.towers)}")
    print(f"  Sub-Towers:  {len(result.get_all_sub_tower_names())}")
    print(f"  Output:      {output_path}")
    print(f"{'='*60}\n")

    for domain, towers in result.get_towers_by_domain().items():
        print(f"  {domain}:")
        for t in towers:
            tower_obj = next(x for x in result.towers if x.name == t)
            print(f"    {t} ({len(tower_obj.sub_towers)} sub-towers)")


if __name__ == "__main__":
    main()
