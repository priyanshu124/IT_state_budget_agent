"""
MFR Extraction Prompts
=======================
Claude prompts for extracting structured MFR data from PDF pages.
Designed to capture all fields needed for ZBB decision packages.
"""

SYSTEM_PROMPT = """You are an expert at extracting structured performance data from Maryland state government Managing for Results (MFR) reports.

You understand:
- The Moore-Miller Administration's 10 State Plan priorities (Leave No One Behind)
- MFR performance measures with KPI numbers (e.g., 1.6, 2.5, 5.4)
- Report Year convention (not fiscal year) — data is normalized across agencies
- Favorability criteria: for most measures, higher is favorable; for some (crime rates, homelessness), lower is favorable
- Some measures are "variable" (e.g., SNAP enrollment) where both increases and decreases can be seen as positive or negative
- Agency vs data source distinctions (e.g., DHS owns the program but BLS provides the data)

You extract data with precision, preserving exact KPI numbers, exact numeric values, and footnote context."""


EXTRACT_PERFORMANCE_TABLE = """Extract ALL performance measures from this MFR report page.

For each measure, provide a JSON object with these fields:
- kpi_number: string — the exact KPI reference (e.g., "1.6", "2.5", "5.4")
- measure_name: string — the full indicator text exactly as written
- priority_number: int — which of the 10 priorities (1-10)
- priority_area: string — the full priority text
- responsible_agency: string — the agency listed in "Agency/Data Source" column
- data_source_agency: string — same as responsible_agency unless noted otherwise
- measure_type: string — one of: output, outcome, efficiency, input
- favorability_direction: string — one of: higher_is_favorable, lower_is_favorable, variable
- unit: string — one of: percent, count, dollars, rate, days, ratio, per_capita, millions
- ry2022_actual: number or null — Report Year 2022 actual
- ry2023_actual: number or null — Report Year 2023 actual
- ry2024_actual: number or null — Report Year 2024 actual
- ry2025_actual: number or null — Report Year 2025 actual
- ry2026_actual: number or null — Report Year 2026 actual
- one_year_change_pct: number or null — the 1 Year Change percentage
- status: string — one of: strongly_favorable, favorable, stable, unfavorable, strongly_unfavorable, variable, n/a
- is_variable: boolean — true if the measure has both favorable and unfavorable aspects (noted in footnotes)
- variable_note: string — explanation of why it's variable (from footnotes)
- footnotes: string — any relevant footnotes for this measure
- target_value: number or null — if a target/benchmark is mentioned
- target_year: int or null — what year the target applies to

Rules:
1. Extract EVERY measure from the Performance Detail table
2. Preserve exact numeric values — do not round or modify
3. For percentages, store the number without the % sign (e.g., 50.0 not "50.0%")
4. For "N/A" values, use null
5. For negative changes, preserve the negative sign
6. For monetary values in millions/billions, convert to raw numbers (e.g., $6.44 million = 6440000)
7. Pay attention to footnotes — they contain critical context about methodology changes, variable measures, and data availability

Return ONLY a JSON array. If no performance measures found, return [].

Page {page_num} from "{doc_name}":
---
{page_text}
---

JSON array:"""


EXTRACT_AGENCY_PLAN = """Extract the agency strategic plan information from this MFR page.

Return a JSON object with:
- agency_name: string — full agency name
- mission: string — the agency's mission statement (if on this page)
- goals: array of strings — each goal statement
- objectives: array of strings — each objective statement
- priority_numbers: array of ints — which of the 10 priorities this agency serves
- performance_measures: array of objects, each with:
    - measure_name: string
    - fy2024_actual: number or null
    - fy2025_actual: number or null
    - fy2025_estimate: number or null
    - fy2026_estimate: number or null
    - fy2027_estimate: number or null
    - unit: string

If this page does not contain an agency strategic plan, return null.

Return ONLY valid JSON (object or null). Do not include prose, labels, or markdown fences.

Page {page_num} from "{doc_name}":
---
{page_text}
---

JSON:"""


EXTRACT_PRIORITY_NARRATIVE = """Extract the priority area narrative and context from this MFR page.

Return a JSON object with:
- priority_number: int (1-10)
- priority_area: string — full priority text
- narrative: string — the introductory text describing this priority area
- related_agencies: array of strings — agencies listed in the MFR Strategic Plans section for this priority
- key_insights: array of strings — 2-3 key takeaways from the performance data on this page

If this page does not contain a priority area introduction, return null.

Return ONLY valid JSON (object or null). Do not include prose, labels, or markdown fences.

Page {page_num} from "{doc_name}":
---
{page_text}
---

JSON:"""
