"""
MFR Extraction Pipeline
========================
Extracts Maryland MFR performance data from PDFs into DuckDB,
structured for Zero-Based Budgeting analysis.

Pipeline:
  1. PDF → page-level text extraction (pdfplumber)
  2. Page classification (performance table vs agency plan vs narrative)
  3. Claude extraction → structured JSON
  4. Validation & normalization
  5. DuckDB loading with ZBB-ready views

Usage:
    # Single PDF
    python -m src.pipeline.mfr.mfr_extractor --pdf data/mfr/2026-MFR-Report.pdf --db mbtsa_work.duckdb

    # Directory of PDFs
    python -m src.pipeline.mfr.mfr_extractor --dir data/mfr/ --db mbtsa_work.duckdb

    # With custom model
    python -m src.pipeline.mfr.mfr_extractor --pdf data/mfr/2026-MFR-Report.pdf --db mbtsa_work.duckdb --model claude-sonnet-4-20250514
"""

import os
import json
import re
import csv
import argparse
from pathlib import Path
from dataclasses import asdict
from typing import Any, Optional

import duckdb
import structlog
from tqdm import tqdm

from src.pipeline.mfr.mfr_models import (
    MFRMeasure, MFRAgencyPlan, STATE_PLAN_PRIORITIES,
)

_PROMPTS_AVAILABLE = True
try:
    from src.agents.prompts.mfr_extraction import (  # type: ignore[import-not-found]
        SYSTEM_PROMPT,
        EXTRACT_PERFORMANCE_TABLE,
        EXTRACT_AGENCY_PLAN,
        EXTRACT_PRIORITY_NARRATIVE,
    )
except ModuleNotFoundError:
    # Keep pdf-only mode functional even if prompt assets are absent.
    SYSTEM_PROMPT = ""
    EXTRACT_PERFORMANCE_TABLE = ""
    EXTRACT_AGENCY_PLAN = ""
    EXTRACT_PRIORITY_NARRATIVE = ""
    _PROMPTS_AVAILABLE = False

log = structlog.get_logger()


class AnthropicQuotaError(RuntimeError):
    """Raised when Anthropic rejects requests due to exhausted credits."""


def _is_quota_error(message: str) -> bool:
    """Detect known Anthropic insufficient-credit errors from exception text."""
    msg = (message or "").lower()
    return (
        "credit balance is too low" in msg
        or ("insufficient" in msg and "credit" in msg)
        or "purchase credits" in msg
    )


# ══════════════════════════════════════════════════════════════
# STEP 1: PDF TEXT EXTRACTION
# ══════════════════════════════════════════════════════════════

def extract_pages(pdf_path: str) -> list[dict]:
    """Extract text and tables from each PDF page with page numbers."""
    try:
        import pdfplumber
    except ImportError:
        log.error("Install pdfplumber: pip install pdfplumber --break-system-packages")
        raise

    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""

            # Extract tables as structured text
            table_text = ""
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    if row:
                        cells = [str(cell or "").strip() for cell in row]
                        table_text += " | ".join(cells) + "\n"

            combined = f"{text}\n\n--- TABLES ---\n{table_text}".strip() if table_text else text

            pages.append({
                "page_num": i,
                "text": text,
                "table_text": table_text,
                "tables": tables,
                "combined": combined,
                "char_count": len(combined),
            })

    log.info("pdf_extracted", path=pdf_path, pages=len(pages),
             total_chars=sum(p["char_count"] for p in pages))
    return pages


# ══════════════════════════════════════════════════════════════
# STEP 2: PAGE CLASSIFICATION
# ══════════════════════════════════════════════════════════════

def classify_page(page: dict) -> str:
    """Classify page type for routing to correct extraction prompt.

    Returns: 'performance_table', 'agency_plan', 'priority_narrative',
             'toc', 'skip'
    """
    text = page["combined"].lower()
    char_count = page["char_count"]

    # Skip near-empty pages
    if char_count < 80:
        return "skip"

    # Table of contents / title pages
    if "table of contents" in text or "annual performance report" in text[:200]:
        return "skip"

    # Executive summary
    if "executive summary" in text[:100]:
        return "skip"

    # Performance Detail tables (the main data)
    if "performance detail" in text or ("kpi" in text and ("report years" in text or "1 year change" in text)):
        return "performance_table"

    # Also catch tables with KPI numbers like "1.1", "2.5"
    kpi_pattern = re.findall(r'\b\d+\.\d+\b', text[:500])
    if len(kpi_pattern) >= 3 and any(kw in text for kw in ["actual", "indicator", "agency"]):
        return "performance_table"

    # Priority area introductions
    if "leave no one behind by" in text[:200]:
        return "priority_narrative"

    # Agency strategic plans
    if any(kw in text for kw in ["mission", "goal 1", "obj. 1", "objective 1"]):
        if any(kw in text for kw in ["strategic plan", "performance measures"]):
            return "agency_plan"

    # MFR Strategic Plans list
    if "mfr strategic plans" in text:
        return "priority_narrative"

    # Pages with measure-like content
    if any(kw in text for kw in ["favorable", "unfavorable", "stable", "1 year change"]):
        return "performance_table"

    return "skip"


# ══════════════════════════════════════════════════════════════
# STEP 3: CLAUDE EXTRACTION
# ══════════════════════════════════════════════════════════════

def call_claude(
    prompt: str,
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 8192,
) -> str:
    """Call Claude API and return raw text response."""
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        err_text = str(e)
        if _is_quota_error(err_text):
            raise AnthropicQuotaError(err_text) from e
        raise

    return response.content[0].text.strip()


def parse_json_response(raw: str) -> Any:
    """Parse JSON from Claude response, tolerating light wrapper text."""
    text = (raw or "").strip()

    # Prefer fenced content when present anywhere in the response.
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Common case: model returns `null` with a trailing explanation.
    if re.match(r"^(null|none)\b", text, flags=re.IGNORECASE):
        return None

    # First attempt: strict parse of the full response.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: extract and decode the first JSON object/array from wrapper text.
    decoder = json.JSONDecoder()
    start_positions = [i for i, ch in enumerate(text) if ch in "[{"]

    for start in start_positions:
        try:
            value, _ = decoder.raw_decode(text[start:])
            return value
        except json.JSONDecodeError:
            continue

    # Last chance: find a null token embedded in text.
    if re.search(r"\bnull\b", text, flags=re.IGNORECASE):
        return None

    # Raise original parse error to preserve visibility when recovery is impossible.
    return json.loads(text)


def _normalize_space(text: str) -> str:
    """Normalize whitespace and common dash variants for stable parsing."""
    cleaned = (text or "").replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", cleaned).strip()


def _looks_like_value_cell(cell: str) -> bool:
    """Heuristic check for table value cells (numbers, percent, currency, N/A)."""
    raw = _normalize_space(cell).lower()
    if not raw:
        return False
    if raw in {"n/a", "na", "-", "--", "---"}:
        return True
    if bool(re.search(r"\d", raw)):
        return True
    return False


def _parse_numeric_cell(cell: str) -> Optional[float]:
    """Parse a numeric table cell into float; return None for N/A-like values."""
    raw = _normalize_space(cell)
    if not raw:
        return None

    lower = raw.lower()
    if lower in {"n/a", "na", "-", "--", "---", "none"}:
        return None

    normalized = raw.replace(",", "").replace("$", "").replace("%", "")
    normalized = normalized.replace("(", "-").replace(")", "")
    normalized = normalized.strip()

    try:
        return float(normalized)
    except ValueError:
        return None


def _extract_source_agency(measure_name: str) -> tuple[str, str]:
    """Extract trailing '(Agency)' token from measure label when present."""
    name = _normalize_space(measure_name)
    match = re.search(r"\(([^()]{2,120})\)\s*$", name)
    if not match:
        return name, ""

    source_agency = _normalize_space(match.group(1))
    base_name = _normalize_space(name[:match.start()])
    return base_name, source_agency


def _infer_unit(measure_name: str) -> str:
    """Infer a coarse unit from measure name text."""
    txt = measure_name.lower()
    if "percent" in txt or "percentage" in txt or "%" in txt:
        return "percent"
    if "$" in txt or "dollar" in txt or "funding" in txt or "amount" in txt:
        return "dollars"
    if "rate" in txt:
        return "rate"
    if "days" in txt or "length of stay" in txt:
        return "days"
    return "count"


def _extract_agency_hierarchy_measures_pdf_only(
    pages: list[dict],
    doc_name: str,
    agency_filter: Optional[str] = None,
    max_pages: Optional[int] = None,
) -> list[dict]:
    """Extract goal/objective/measure/year rows using deterministic PDF parsing only."""
    rows: list[dict] = []

    current_agency = ""
    current_goal_number: Optional[int] = None
    current_goal_text = ""
    current_objective_number = ""
    current_objective_text = ""
    active_years: list[int] = []

    def _append_row(
        measure_name_raw: str,
        year_cells: list[str],
        years: list[int],
        source_page: int,
    ):
        nonlocal rows

        measure_name_raw = _normalize_space(measure_name_raw)
        if not measure_name_raw:
            return

        if measure_name_raw.lower().startswith("performance measures"):
            return

        agency_name = current_agency or "UNKNOWN_AGENCY"
        if agency_filter and agency_filter.lower() not in agency_name.lower():
            return

        measure_name, data_source_agency = _extract_source_agency(measure_name_raw)
        year_values = {year: _parse_numeric_cell(cell) for year, cell in zip(years, year_cells)}

        if not any(val is not None for val in year_values.values()) and not any(
            _normalize_space(cell).lower() in {"n/a", "na"} for cell in year_cells
        ):
            return

        rows.append({
            "agency_name": agency_name,
            "goal_number": current_goal_number,
            "goal_text": current_goal_text,
            "objective_number": current_objective_number,
            "objective_text": current_objective_text,
            "measure_name": measure_name,
            "data_source_agency": data_source_agency,
            "unit": _infer_unit(measure_name),
            "year_values": year_values,
            "source_doc": doc_name,
            "source_page": source_page,
        })

    pages_to_parse = pages[:max_pages] if max_pages is not None else pages

    for page in tqdm(pages_to_parse, desc=f"PDF-only hierarchy parse for {doc_name}"):
        text = page.get("text", "")
        lines = [_normalize_space(line) for line in text.splitlines() if _normalize_space(line)]
        pending_line_name = ""

        for line in lines:
            lower_line = line.lower()

            # Agency heading appears at the top of each section/page.
            if re.match(r"^(maryland\s+department\s+of\s+.+|department\s+of\s+.+|office\s+of\s+.+)$", line, re.IGNORECASE):
                if "http://" not in line.lower() and "https://" not in line.lower():
                    current_agency = line

            goal_match = re.match(r"^Goal\s+(\d+)\.\s*(.+)$", line, re.IGNORECASE)
            if goal_match:
                current_goal_number = int(goal_match.group(1))
                current_goal_text = _normalize_space(goal_match.group(2))
                continue

            obj_match = re.match(r"^Obj\.?\s*([0-9]+\.[0-9]+)\s*(?:\((?:continued|Continued)\))?\s*(.*)$", line)
            if obj_match:
                current_objective_number = obj_match.group(1)
                obj_text = _normalize_space(obj_match.group(2))
                if obj_text:
                    current_objective_text = obj_text
                continue

            if lower_line.startswith("notes"):
                active_years = []
                pending_line_name = ""
                continue

            header_year_tokens = re.findall(r"\b(20\d{2})\b", line)
            if header_year_tokens and ("act" in lower_line or "est" in lower_line):
                parsed_years: list[int] = []
                for y in header_year_tokens:
                    yi = int(y)
                    if 2018 <= yi <= 2035 and yi not in parsed_years:
                        parsed_years.append(yi)
                if parsed_years:
                    active_years = parsed_years
                    pending_line_name = ""
                    continue

            if active_years:
                # Skip standard footer/noise lines.
                if lower_line.startswith("http://") or lower_line.startswith("https://"):
                    continue
                if re.match(r"^D\d+", line):
                    continue
                if re.fullmatch(r"\d+", line):
                    continue
                if lower_line.startswith("maryland department of"):
                    continue

                tokens = line.split()
                if len(tokens) >= len(active_years):
                    value_tokens = tokens[-len(active_years):]
                    if all(_looks_like_value_cell(token) for token in value_tokens):
                        name_part = _normalize_space(" ".join(tokens[:-len(active_years)]))
                        measure_name_raw = _normalize_space(f"{pending_line_name} {name_part}")
                        pending_line_name = ""
                        _append_row(measure_name_raw, value_tokens, active_years, page["page_num"])
                        continue

                if not lower_line.startswith("performance measures"):
                    pending_line_name = _normalize_space(f"{pending_line_name} {line}")

        for table in page.get("tables", []) or []:
            years: list[int] = []
            pending_name = ""

            for row in table:
                cells = [_normalize_space(str(cell or "")) for cell in row]
                if not any(cells):
                    continue

                joined = _normalize_space(" ".join(cells))
                if not joined:
                    continue

                year_tokens = re.findall(r"\b(20\d{2})\b", joined)
                if year_tokens and ("act" in joined.lower() or "est" in joined.lower() or "performance measures" in joined.lower()):
                    years = []
                    for y in year_tokens:
                        yi = int(y)
                        if 2018 <= yi <= 2035 and yi not in years:
                            years.append(yi)
                    pending_name = ""
                    continue

                if not years:
                    continue

                if len(cells) < len(years) + 1:
                    # Wrapped measure-name fragment.
                    fragment = _normalize_space(" ".join(cells))
                    if fragment and "performance measures" not in fragment.lower():
                        pending_name = _normalize_space(f"{pending_name} {fragment}")
                    continue

                value_cells = cells[-len(years):]
                has_values = any(_looks_like_value_cell(cell) for cell in value_cells)
                name_part = _normalize_space(" ".join(cell for cell in cells[:-len(years)] if cell))

                if not has_values:
                    if name_part and name_part.lower() != "performance measures":
                        pending_name = _normalize_space(f"{pending_name} {name_part}")
                    continue

                measure_name_raw = _normalize_space(f"{pending_name} {name_part}")
                pending_name = ""

                _append_row(measure_name_raw, value_cells, years, page["page_num"])

    # Deduplicate rows from mixed table/text parsing paths.
    deduped: dict[tuple, dict] = {}
    for row in rows:
        key = (
            row.get("agency_name", ""),
            row.get("goal_number"),
            row.get("objective_number", ""),
            row.get("measure_name", ""),
            row.get("source_doc", ""),
            tuple(sorted(row.get("year_values", {}).items())),
        )
        deduped[key] = row

    rows = list(deduped.values())

    log.info("pdf_only_hierarchy_extracted", doc=doc_name, measures=len(rows))
    return rows


def extract_performance_measures(
    pages: list[dict],
    doc_name: str,
    api_key: str,
    model: str,
    max_pages: Optional[int] = None,
) -> list[MFRMeasure]:
    """Extract performance measures from classified pages."""
    measures = []

    perf_pages = [p for p in pages if classify_page(p) == "performance_table"]
    if max_pages is not None:
        perf_pages = perf_pages[:max_pages]
    log.info("performance_pages_found", count=len(perf_pages), doc=doc_name)

    for page in tqdm(perf_pages, desc=f"Extracting measures from {doc_name}"):
        prompt = EXTRACT_PERFORMANCE_TABLE.format(
            page_num=page["page_num"],
            doc_name=doc_name,
            page_text=page["combined"][:6000],  # Stay within context limits
        )

        try:
            raw = call_claude(prompt, api_key, model)
            data = parse_json_response(raw)

            if not data or not isinstance(data, list):
                continue

            for m in data:
                measure = MFRMeasure(
                    kpi_number=str(m.get("kpi_number", "")),
                    measure_name=m.get("measure_name", ""),
                    priority_number=_safe_int(m.get("priority_number"), 0),
                    priority_area=m.get("priority_area", ""),
                    responsible_agency=m.get("responsible_agency", ""),
                    data_source_agency=m.get("data_source_agency", m.get("responsible_agency", "")),
                    measure_type=m.get("measure_type", "outcome"),
                    favorability_direction=m.get("favorability_direction", "higher_is_favorable"),
                    unit=m.get("unit", ""),
                    ry2022_actual=_safe_float(m.get("ry2022_actual")),
                    ry2023_actual=_safe_float(m.get("ry2023_actual")),
                    ry2024_actual=_safe_float(m.get("ry2024_actual")),
                    ry2025_actual=_safe_float(m.get("ry2025_actual")),
                    ry2026_actual=_safe_float(m.get("ry2026_actual")),
                    one_year_change_pct=_safe_float(m.get("one_year_change_pct")),
                    status=m.get("status", "n/a"),
                    is_variable=bool(m.get("is_variable", False)),
                    variable_note=m.get("variable_note", ""),
                    footnotes=m.get("footnotes", ""),
                    target_value=_safe_float(m.get("target_value")),
                    target_year=_safe_int(m.get("target_year")),
                    source_doc=doc_name,
                    source_page=page["page_num"],
                )

                # Compute 5-year trend
                measure.five_year_trend = _compute_trend(measure)

                if measure.measure_name:
                    measures.append(measure)

            log.info("page_extracted", page=page["page_num"], measures=len(data))

        except AnthropicQuotaError as e:
            log.error("anthropic_quota_exhausted", phase="measures", page=page["page_num"], error=str(e))
            raise
        except json.JSONDecodeError as e:
            log.warning("json_error", page=page["page_num"], error=str(e))
        except Exception as e:
            log.error("extraction_error", page=page["page_num"], error=str(e))

    log.info("measures_extracted", doc=doc_name, total=len(measures))
    return measures


def extract_agency_plans(
    pages: list[dict],
    doc_name: str,
    api_key: str,
    model: str,
    max_pages: Optional[int] = None,
) -> list[MFRAgencyPlan]:
    """Extract agency strategic plans from classified pages."""
    plans = []

    plan_pages = [p for p in pages if classify_page(p) == "agency_plan"]
    if max_pages is not None:
        plan_pages = plan_pages[:max_pages]
    log.info("agency_plan_pages_found", count=len(plan_pages), doc=doc_name)

    for page in tqdm(plan_pages, desc=f"Extracting agency plans from {doc_name}"):
        prompt = EXTRACT_AGENCY_PLAN.format(
            page_num=page["page_num"],
            doc_name=doc_name,
            page_text=page["combined"][:6000],
        )

        try:
            raw = call_claude(prompt, api_key, model)
            data = parse_json_response(raw)

            if not data or not isinstance(data, dict):
                continue

            plan = MFRAgencyPlan(
                agency_name=data.get("agency_name", ""),
                priority_numbers=data.get("priority_numbers", []),
                mission=data.get("mission", ""),
                goals=data.get("goals", []),
                objectives=data.get("objectives", []),
                source_doc=doc_name,
                source_page_start=page["page_num"],
                source_page_end=page["page_num"],
            )

            if plan.agency_name:
                plans.append(plan)

        except AnthropicQuotaError as e:
            log.error("anthropic_quota_exhausted", phase="agency_plans", page=page["page_num"], error=str(e))
            raise
        except Exception as e:
            log.warning("plan_extraction_error", page=page["page_num"], error=str(e))

    log.info("agency_plans_extracted", doc=doc_name, total=len(plans))
    return plans


def extract_priority_narratives(
    pages: list[dict],
    doc_name: str,
    api_key: str,
    model: str,
    max_pages: Optional[int] = None,
) -> list[dict]:
    """Extract priority area narratives and related agency lists."""
    narratives = []

    narr_pages = [p for p in pages if classify_page(p) == "priority_narrative"]
    if max_pages is not None:
        narr_pages = narr_pages[:max_pages]
    log.info("narrative_pages_found", count=len(narr_pages), doc=doc_name)

    for page in tqdm(narr_pages, desc=f"Extracting narratives from {doc_name}"):
        prompt = EXTRACT_PRIORITY_NARRATIVE.format(
            page_num=page["page_num"],
            doc_name=doc_name,
            page_text=page["combined"][:6000],
        )

        try:
            raw = call_claude(prompt, api_key, model)
            data = parse_json_response(raw)

            if data and isinstance(data, dict):
                data["source_doc"] = doc_name
                data["source_page"] = page["page_num"]
                narratives.append(data)

        except AnthropicQuotaError as e:
            log.error("anthropic_quota_exhausted", phase="priority_narratives", page=page["page_num"], error=str(e))
            raise
        except Exception as e:
            log.warning("narrative_error", page=page["page_num"], error=str(e))

    return narratives


# ══════════════════════════════════════════════════════════════
# STEP 4: VALIDATION & NORMALIZATION
# ══════════════════════════════════════════════════════════════

def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        if isinstance(val, str):
            val = val.replace(",", "").replace("$", "").replace("%", "").strip()
            if val.lower() in ("", "n/a", "-", "—", "none"):
                return None
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val, default=None) -> Optional[int]:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _compute_trend(m: MFRMeasure) -> str:
    """Compute 5-year trend from available actuals."""
    vals = [v for v in [m.ry2022_actual, m.ry2023_actual, m.ry2024_actual,
                        m.ry2025_actual, m.ry2026_actual] if v is not None]
    if len(vals) < 2:
        return "insufficient_data"

    first, last = vals[0], vals[-1]
    if first == 0:
        return "new_measure"

    change = (last - first) / abs(first) * 100

    if m.favorability_direction == "higher_is_favorable":
        if change > 10: return "strongly_improving"
        if change > 3: return "improving"
        if change > -3: return "stable"
        if change > -10: return "declining"
        return "strongly_declining"
    elif m.favorability_direction == "lower_is_favorable":
        if change < -10: return "strongly_improving"
        if change < -3: return "improving"
        if change < 3: return "stable"
        if change < 10: return "declining"
        return "strongly_declining"
    else:
        return "variable"


def validate_measures(measures: list[MFRMeasure]) -> list[MFRMeasure]:
    """Validate and deduplicate extracted measures."""
    seen = set()
    validated = []

    for m in measures:
        # Deduplicate by KPI number + source doc
        key = (m.kpi_number, m.source_doc)
        if key in seen:
            continue
        seen.add(key)

        # Validate priority number
        if m.priority_number < 1 or m.priority_number > 10:
            # Try to infer from KPI number
            try:
                m.priority_number = int(m.kpi_number.split(".")[0])
            except (ValueError, IndexError):
                pass

        # Fill priority area from lookup
        if not m.priority_area and m.priority_number in STATE_PLAN_PRIORITIES:
            m.priority_area = STATE_PLAN_PRIORITIES[m.priority_number]

        validated.append(m)

    log.info("validation_complete", input=len(measures), output=len(validated),
             deduped=len(measures) - len(validated))
    return validated


# ══════════════════════════════════════════════════════════════
# STEP 5: DUCKDB LOADING
# ══════════════════════════════════════════════════════════════

def load_measures_to_duckdb(measures: list[MFRMeasure], db_path: str):
    """Load MFR measures into DuckDB with ZBB-ready schema."""
    con = duckdb.connect(db_path)

    # Ensure schema exists
    con.execute("CREATE SCHEMA IF NOT EXISTS main_marts")

    # Drop and recreate for clean loads
    con.execute("DROP TABLE IF EXISTS main_marts.fct_mfr_performance")

    con.execute("""
        CREATE TABLE main_marts.fct_mfr_performance (
            -- Identity
            kpi_number VARCHAR,
            measure_name VARCHAR,
            priority_number INTEGER,
            priority_area VARCHAR,

            -- Agencies
            responsible_agency VARCHAR,
            data_source_agency VARCHAR,

            -- Classification
            measure_type VARCHAR,
            favorability_direction VARCHAR,
            unit VARCHAR,

            -- Report Year Actuals
            ry2022_actual DOUBLE,
            ry2023_actual DOUBLE,
            ry2024_actual DOUBLE,
            ry2025_actual DOUBLE,
            ry2026_actual DOUBLE,

            -- Computed
            one_year_change_pct DOUBLE,
            status VARCHAR,
            five_year_trend VARCHAR,

            -- Targets (for ZBB)
            target_value DOUBLE,
            target_year INTEGER,
            target_description VARCHAR,

            -- Citation
            source_doc VARCHAR,
            source_page INTEGER,
            footnotes VARCHAR,

            -- ZBB flags
            is_variable BOOLEAN,
            variable_note VARCHAR
        )
    """)

    for m in measures:
        con.execute("""
            INSERT INTO main_marts.fct_mfr_performance VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, [
            m.kpi_number, m.measure_name, m.priority_number, m.priority_area,
            m.responsible_agency, m.data_source_agency,
            m.measure_type, m.favorability_direction, m.unit,
            m.ry2022_actual, m.ry2023_actual, m.ry2024_actual, m.ry2025_actual, m.ry2026_actual,
            m.one_year_change_pct, m.status, m.five_year_trend,
            m.target_value, m.target_year, m.target_description,
            m.source_doc, m.source_page, m.footnotes,
            m.is_variable, m.variable_note,
        ])

    count = con.execute("SELECT COUNT(*) FROM main_marts.fct_mfr_performance").fetchone()[0]
    log.info("measures_loaded", db=db_path, count=count)
    con.close()


def load_agency_plans_to_duckdb(plans: list[MFRAgencyPlan], db_path: str):
    """Load agency plans into DuckDB for ZBB justification narratives."""
    con = duckdb.connect(db_path)

    con.execute("DROP TABLE IF EXISTS main_marts.dim_mfr_agency_plans")
    con.execute("""
        CREATE TABLE main_marts.dim_mfr_agency_plans (
            agency_name VARCHAR,
            priority_numbers VARCHAR,
            mission VARCHAR,
            goals VARCHAR,
            objectives VARCHAR,
            source_doc VARCHAR,
            source_page_start INTEGER,
            source_page_end INTEGER
        )
    """)

    for p in plans:
        con.execute("""
            INSERT INTO main_marts.dim_mfr_agency_plans VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            p.agency_name,
            json.dumps(p.priority_numbers),
            p.mission,
            json.dumps(p.goals),
            json.dumps(p.objectives),
            p.source_doc,
            p.source_page_start,
            p.source_page_end,
        ])

    count = con.execute("SELECT COUNT(*) FROM main_marts.dim_mfr_agency_plans").fetchone()[0]
    log.info("agency_plans_loaded", db=db_path, count=count)
    con.close()


def load_narratives_to_duckdb(narratives: list[dict], db_path: str):
    """Load priority narratives for ZBB context."""
    con = duckdb.connect(db_path)

    con.execute("DROP TABLE IF EXISTS main_marts.dim_mfr_priority_narratives")
    con.execute("""
        CREATE TABLE main_marts.dim_mfr_priority_narratives (
            priority_number INTEGER,
            priority_area VARCHAR,
            narrative VARCHAR,
            related_agencies VARCHAR,
            key_insights VARCHAR,
            source_doc VARCHAR,
            source_page INTEGER
        )
    """)

    for n in narratives:
        con.execute("""
            INSERT INTO main_marts.dim_mfr_priority_narratives VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            n.get("priority_number"),
            n.get("priority_area", ""),
            n.get("narrative", ""),
            json.dumps(n.get("related_agencies", [])),
            json.dumps(n.get("key_insights", [])),
            n.get("source_doc", ""),
            n.get("source_page", 0),
        ])

    con.close()


def load_agency_hierarchy_to_duckdb(rows: list[dict], db_path: str):
    """Load PDF-only extracted agency hierarchy measures into DuckDB."""
    con = duckdb.connect(db_path)
    con.execute("CREATE SCHEMA IF NOT EXISTS main_marts")

    con.execute("DROP TABLE IF EXISTS main_marts.fct_mfr_agency_hierarchy_measures")
    con.execute("""
        CREATE TABLE main_marts.fct_mfr_agency_hierarchy_measures (
            agency_name VARCHAR,
            goal_number INTEGER,
            goal_text VARCHAR,
            objective_number VARCHAR,
            objective_text VARCHAR,
            measure_name VARCHAR,
            data_source_agency VARCHAR,
            unit VARCHAR,
            report_year INTEGER,
            actual_value DOUBLE,
            source_doc VARCHAR,
            source_page INTEGER
        )
    """)

    for row in rows:
        for report_year, actual_value in sorted(row["year_values"].items()):
            con.execute("""
                INSERT INTO main_marts.fct_mfr_agency_hierarchy_measures VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                row.get("agency_name", ""),
                row.get("goal_number"),
                row.get("goal_text", ""),
                row.get("objective_number", ""),
                row.get("objective_text", ""),
                row.get("measure_name", ""),
                row.get("data_source_agency", ""),
                row.get("unit", ""),
                report_year,
                actual_value,
                row.get("source_doc", ""),
                row.get("source_page", 0),
            ])

    con.execute("""
        CREATE OR REPLACE VIEW main_marts.v_mfr_agency_latest_measures AS
        WITH ranked AS (
            SELECT
                agency_name,
                goal_number,
                goal_text,
                objective_number,
                objective_text,
                measure_name,
                data_source_agency,
                unit,
                report_year,
                actual_value,
                source_doc,
                source_page,
                ROW_NUMBER() OVER (
                    PARTITION BY agency_name, goal_number, objective_number, measure_name
                    ORDER BY report_year DESC
                ) AS rn
            FROM main_marts.fct_mfr_agency_hierarchy_measures
        )
        SELECT
            agency_name,
            goal_number,
            goal_text,
            objective_number,
            objective_text,
            measure_name,
            data_source_agency,
            unit,
            report_year,
            actual_value,
            source_doc,
            source_page
        FROM ranked
        WHERE rn = 1
    """)

    count = con.execute("SELECT COUNT(*) FROM main_marts.fct_mfr_agency_hierarchy_measures").fetchone()[0]
    log.info("agency_hierarchy_loaded", db=db_path, count=count)
    con.close()


def export_agency_hierarchy_to_csv(rows: list[dict], output_path: str):
    """Export PDF-only hierarchy rows to long-form CSV."""
    fieldnames = [
        "agency_name",
        "goal_number",
        "goal_text",
        "objective_number",
        "objective_text",
        "measure_name",
        "data_source_agency",
        "unit",
        "report_year",
        "actual_value",
        "source_doc",
        "source_page",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            for report_year, actual_value in sorted(row["year_values"].items()):
                writer.writerow({
                    "agency_name": row.get("agency_name", ""),
                    "goal_number": row.get("goal_number"),
                    "goal_text": row.get("goal_text", ""),
                    "objective_number": row.get("objective_number", ""),
                    "objective_text": row.get("objective_text", ""),
                    "measure_name": row.get("measure_name", ""),
                    "data_source_agency": row.get("data_source_agency", ""),
                    "unit": row.get("unit", ""),
                    "report_year": report_year,
                    "actual_value": actual_value,
                    "source_doc": row.get("source_doc", ""),
                    "source_page": row.get("source_page", 0),
                })

    log.info("agency_hierarchy_csv_exported", path=output_path, rows=len(rows))


def create_zbb_views(db_path: str):
    """Create analytical views that power ZBB analysis."""
    con = duckdb.connect(db_path)

    # ── View 1: Time series (unpivoted) for trend charts ──────
    con.execute("""
        CREATE OR REPLACE VIEW main_marts.v_mfr_time_series AS
        SELECT kpi_number, measure_name, priority_number, priority_area,
               responsible_agency, measure_type, favorability_direction, unit,
               status, source_doc, source_page,
               report_year, actual_value
        FROM main_marts.fct_mfr_performance
        UNPIVOT (
            actual_value FOR report_year IN (
                ry2022_actual AS "2022",
                ry2023_actual AS "2023",
                ry2024_actual AS "2024",
                ry2025_actual AS "2025",
                ry2026_actual AS "2026"
            )
        )
        WHERE actual_value IS NOT NULL
    """)

    # ── View 2: Agency performance summary (for ZBB scoring) ──
    con.execute("""
        CREATE OR REPLACE VIEW main_marts.v_mfr_agency_scorecard AS
        SELECT
            responsible_agency as agency_name,
            COUNT(*) as total_measures,
            SUM(CASE WHEN status IN ('strongly_favorable', 'favorable') THEN 1 ELSE 0 END) as favorable,
            SUM(CASE WHEN status = 'stable' THEN 1 ELSE 0 END) as stable,
            SUM(CASE WHEN status IN ('strongly_unfavorable', 'unfavorable') THEN 1 ELSE 0 END) as unfavorable,
            ROUND(SUM(CASE WHEN status IN ('strongly_favorable', 'favorable') THEN 1 ELSE 0 END)
                * 100.0 / NULLIF(COUNT(*), 0), 1) as favorable_pct,
            ROUND(SUM(CASE WHEN status IN ('strongly_unfavorable', 'unfavorable') THEN 1 ELSE 0 END)
                * 100.0 / NULLIF(COUNT(*), 0), 1) as unfavorable_pct
        FROM main_marts.fct_mfr_performance
        WHERE status NOT IN ('n/a', 'variable')
        GROUP BY responsible_agency
    """)

    # ── View 3: Priority scorecard (for Governor's office) ────
    con.execute("""
        CREATE OR REPLACE VIEW main_marts.v_mfr_priority_scorecard AS
        SELECT
            priority_number,
            priority_area,
            COUNT(*) as total_measures,
            SUM(CASE WHEN status IN ('strongly_favorable', 'favorable') THEN 1 ELSE 0 END) as favorable,
            SUM(CASE WHEN status = 'stable' THEN 1 ELSE 0 END) as stable,
            SUM(CASE WHEN status IN ('strongly_unfavorable', 'unfavorable') THEN 1 ELSE 0 END) as unfavorable,
            ROUND(SUM(CASE WHEN status IN ('strongly_favorable', 'favorable') THEN 1 ELSE 0 END)
                * 100.0 / NULLIF(COUNT(*), 0), 1) as favorable_pct
        FROM main_marts.fct_mfr_performance
        WHERE status NOT IN ('n/a', 'variable')
        GROUP BY priority_number, priority_area
        ORDER BY priority_number
    """)

    # ── View 4: ZBB decision unit candidates ──────────────────
    # Joins MFR performance with budget data to identify
    # programs that need ZBB review (high spend + poor outcomes)
    con.execute("""
        CREATE OR REPLACE VIEW main_marts.v_zbb_review_candidates AS
        SELECT
            m.responsible_agency as agency_name,
            m.priority_area,
            m.kpi_number,
            m.measure_name,
            m.status,
            m.five_year_trend,
            m.one_year_change_pct,
            m.ry2025_actual as prior_year_actual,
            m.ry2026_actual as current_year_actual,
            m.favorability_direction,
            m.source_doc,
            m.source_page,
            CASE
                WHEN m.status IN ('strongly_unfavorable', 'unfavorable')
                    AND m.five_year_trend IN ('declining', 'strongly_declining')
                    THEN 'HIGH — declining outcomes, needs ZBB review'
                WHEN m.status IN ('strongly_unfavorable', 'unfavorable')
                    THEN 'MEDIUM — unfavorable status, monitor closely'
                WHEN m.status = 'stable'
                    AND m.five_year_trend IN ('declining', 'strongly_declining')
                    THEN 'MEDIUM — stable but declining trend'
                WHEN m.status IN ('strongly_favorable', 'favorable')
                    THEN 'LOW — performing well'
                ELSE 'ASSESS — insufficient data'
            END as zbb_review_priority
        FROM main_marts.fct_mfr_performance m
        WHERE m.status NOT IN ('n/a', 'variable')
        ORDER BY
            CASE
                WHEN m.status IN ('strongly_unfavorable', 'unfavorable') THEN 1
                WHEN m.status = 'stable' THEN 2
                ELSE 3
            END,
            m.one_year_change_pct ASC NULLS LAST
    """)

    log.info("zbb_views_created")
    con.close()


def export_to_csv(measures: list[MFRMeasure], output_path: str):
    """Export measures to CSV for review before loading."""
    if not measures:
        return

    fieldnames = list(asdict(measures[0]).keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in measures:
            writer.writerow(asdict(m))

    log.info("csv_exported", path=output_path, rows=len(measures))


# ══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Extract MFR performance data from Maryland budget PDFs for ZBB analysis"
    )
    parser.add_argument("--pdf", type=str, help="Path to a single MFR PDF")
    parser.add_argument("--dir", type=str, help="Directory of MFR PDFs")
    parser.add_argument("--db", type=str, default="mbtsa_work.duckdb", help="DuckDB path")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-20250514")
    parser.add_argument("--csv-out", type=str, help="Export CSV before loading (for review)")
    parser.add_argument("--pdf-only", action="store_true", help="Use deterministic PDF parsing only (zero Claude calls)")
    parser.add_argument("--agency", type=str, help="Optional agency-name filter for --pdf-only extraction")
    parser.add_argument("--skip-plans", action="store_true", help="Skip agency plan extraction")
    parser.add_argument("--skip-narratives", action="store_true", help="Skip priority narrative extraction")
    parser.add_argument(
        "--performance-only",
        action="store_true",
        help="Only extract performance measures (implies --skip-plans and --skip-narratives)",
    )
    parser.add_argument(
        "--max-pages-per-type",
        type=int,
        help="Limit Claude calls per extraction type for each PDF",
    )
    parser.add_argument("--dry-run", action="store_true", help="Extract but don't load to DB")
    args = parser.parse_args()

    if args.performance_only:
        args.skip_plans = True
        args.skip_narratives = True

    if args.max_pages_per_type is not None and args.max_pages_per_type < 1:
        parser.error("--max-pages-per-type must be >= 1")

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not args.pdf_only and not _PROMPTS_AVAILABLE:
        log.error("Missing src.agents.prompts.mfr_extraction module; use --pdf-only or restore prompt file")
        return

    if not args.pdf_only and not api_key:
        log.error("Set ANTHROPIC_API_KEY environment variable")
        return

    # Collect PDF files
    pdf_files = []
    if args.pdf:
        pdf_files.append(Path(args.pdf))
    elif args.dir:
        pdf_files = sorted(Path(args.dir).glob("*.pdf"))
    else:
        parser.error("Provide --pdf or --dir")

    all_measures = []
    all_plans = []
    all_narratives = []
    all_hierarchy_rows = []

    for pdf_path in pdf_files:
        log.info("processing_pdf", file=str(pdf_path))

        # Step 1: Extract pages
        pages = extract_pages(str(pdf_path))

        # Step 2+3: Classify and extract
        doc_name = pdf_path.stem

        if args.pdf_only:
            max_pages = args.max_pages_per_type
            parsed_rows = _extract_agency_hierarchy_measures_pdf_only(
                pages,
                doc_name,
                agency_filter=args.agency,
                max_pages=max_pages,
            )
            all_hierarchy_rows.extend(parsed_rows)
            log.info(
                "claude_call_plan",
                doc=doc_name,
                performance_calls=0,
                narrative_calls=0,
                plan_calls=0,
                total_calls=0,
                mode="pdf_only",
            )
            continue

        page_types = [classify_page(p) for p in pages]
        perf_candidates = sum(1 for t in page_types if t == "performance_table")
        narr_candidates = sum(1 for t in page_types if t == "priority_narrative")
        plan_candidates = sum(1 for t in page_types if t == "agency_plan")

        max_pages = args.max_pages_per_type
        perf_calls = min(perf_candidates, max_pages) if max_pages else perf_candidates
        narr_calls = 0 if args.skip_narratives else (min(narr_candidates, max_pages) if max_pages else narr_candidates)
        plan_calls = 0 if args.skip_plans else (min(plan_candidates, max_pages) if max_pages else plan_candidates)

        log.info(
            "claude_call_plan",
            doc=doc_name,
            performance_calls=perf_calls,
            narrative_calls=narr_calls,
            plan_calls=plan_calls,
            total_calls=perf_calls + narr_calls + plan_calls,
        )

        try:
            measures = extract_performance_measures(
                pages,
                doc_name,
                api_key,
                args.model,
                max_pages=max_pages,
            )
            all_measures.extend(measures)

            if not args.skip_narratives:
                narratives = extract_priority_narratives(
                    pages,
                    doc_name,
                    api_key,
                    args.model,
                    max_pages=max_pages,
                )
                all_narratives.extend(narratives)

            if not args.skip_plans:
                plans = extract_agency_plans(
                    pages,
                    doc_name,
                    api_key,
                    args.model,
                    max_pages=max_pages,
                )
                all_plans.extend(plans)
        except AnthropicQuotaError:
            log.error("stopping_extraction_due_to_quota", doc=doc_name)
            break

    # Step 4: Validate
    if args.pdf_only:
        if args.csv_out:
            export_agency_hierarchy_to_csv(all_hierarchy_rows, args.csv_out)

        if not args.dry_run and all_hierarchy_rows:
            load_agency_hierarchy_to_duckdb(all_hierarchy_rows, args.db)

        log.info(
            "pipeline_complete",
            pdf_only=True,
            hierarchy_rows=len(all_hierarchy_rows),
            agency_filter=args.agency or "",
            pdfs=len(pdf_files),
        )
        return

    all_measures = validate_measures(all_measures)

    # Optional CSV export for review
    if args.csv_out:
        export_to_csv(all_measures, args.csv_out)

    # Step 5: Load to DuckDB
    if not args.dry_run and all_measures:
        load_measures_to_duckdb(all_measures, args.db)
        if all_plans:
            load_agency_plans_to_duckdb(all_plans, args.db)
        if all_narratives:
            load_narratives_to_duckdb(all_narratives, args.db)
        create_zbb_views(args.db)

    log.info("pipeline_complete",
             measures=len(all_measures),
             plans=len(all_plans),
             narratives=len(all_narratives),
             pdfs=len(pdf_files))


if __name__ == "__main__":
    main()
